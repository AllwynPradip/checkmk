#!/usr/bin/env python3
# Copyright (C) 2019 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.
"""This module is the main entry point for the inventory tree creation/deletion of hosts.

CL:
- 'cmk -i[i] ...' is intended to be a kind of preview and does not store any trees.
- 'cmk --inventory-as-check ...' is the related command of the HW/SW Inventory service,
    ie. a tree is created, stored and compared to the old one if it exists,
    if and only if there are NO errors while executing inventory plugins.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Collection, Container, Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

import cmk.utils.debug
import cmk.utils.paths
import cmk.utils.tty as tty
from cmk.utils.check_utils import ActiveCheckResult
from cmk.utils.cpu_tracking import Snapshot
from cmk.utils.exceptions import OnError
from cmk.utils.log import console
from cmk.utils.structured_data import RawIntervalsFromConfig, StructuredDataNode, UpdateResult
from cmk.utils.type_defs import (
    AgentRawData,
    HostKey,
    HostName,
    InventoryPluginName,
    result,
    SourceType,
)

from cmk.snmplib.type_defs import SNMPRawData

from cmk.core_helpers.host_sections import HostSections
from cmk.core_helpers.type_defs import Mode, NO_SELECTION, SectionNameCollection, SourceInfo

import cmk.base.api.agent_based.register as agent_based_register
import cmk.base.config as config
import cmk.base.section as section
from cmk.base.agent_based.data_provider import (
    make_broker,
    parse_messages,
    ParsedSectionsBroker,
    SourceResults,
    store_piggybacked_sections,
)
from cmk.base.agent_based.utils import (
    check_parsing_errors,
    get_section_kwargs,
    summarize_host_sections,
)
from cmk.base.api.agent_based.inventory_classes import Attributes, TableRow
from cmk.base.config import HostConfig
from cmk.base.sources import fetch_all, make_sources

from ._tree_aggregator import ItemsOfInventoryPlugin, RealHostTreeUpdater

__all__ = [
    "inventorize_status_data_of_real_host",
    "check_inventory_tree",
]


class FetchedDataResult(NamedTuple):
    parsed_sections_broker: ParsedSectionsBroker
    source_results: SourceResults
    parsing_errors: Sequence[str]
    processing_failed: bool
    no_data_or_files: bool


@dataclass(frozen=True)
class CheckInventoryTreeResult:
    processing_failed: bool
    no_data_or_files: bool
    check_result: ActiveCheckResult
    inventory_tree: StructuredDataNode
    update_result: UpdateResult


def check_inventory_tree(
    host_name: HostName,
    *,
    host_config: HostConfig,
    selected_sections: SectionNameCollection,
    run_plugin_names: Container[InventoryPluginName],
    parameters: config.HWSWInventoryParameters,
    old_tree: StructuredDataNode,
) -> CheckInventoryTreeResult:
    config_cache = config.get_config_cache()
    if config_cache.is_cluster(host_name):
        inventory_tree = _inventorize_cluster(nodes=config_cache.nodes_of(host_name) or [])
        return CheckInventoryTreeResult(
            processing_failed=False,
            no_data_or_files=False,
            check_result=ActiveCheckResult.from_subresults(
                *_check_trees(
                    parameters=parameters,
                    inventory_tree=inventory_tree,
                    status_data_tree=StructuredDataNode(),
                    old_tree=old_tree,
                ),
            ),
            inventory_tree=inventory_tree,
            update_result=UpdateResult(save_tree=False, reason=""),
        )

    fetched_data_result = _fetch_real_host_data(
        host_name,
        host_config=host_config,
        selected_sections=selected_sections,
    )

    trees, update_result = _inventorize_real_host(
        now=int(time.time()),
        items_of_inventory_plugins=list(
            _collect_inventory_plugin_items(
                host_name,
                host_config=host_config,
                parsed_sections_broker=fetched_data_result.parsed_sections_broker,
                run_plugin_names=run_plugin_names,
            )
        ),
        raw_intervals_from_config=config_cache.inv_retention_intervals(host_name),
        old_tree=old_tree,
    )

    return CheckInventoryTreeResult(
        processing_failed=fetched_data_result.processing_failed,
        no_data_or_files=fetched_data_result.no_data_or_files,
        check_result=ActiveCheckResult.from_subresults(
            *_check_fetched_data_or_trees(
                parameters=parameters,
                fetched_data_result=fetched_data_result,
                inventory_tree=trees.inventory,
                status_data_tree=trees.status_data,
                old_tree=old_tree,
            ),
            *summarize_host_sections(
                source_results=fetched_data_result.source_results,
                # Do not use source states which would overwrite "State when inventory fails" in the
                # ruleset "Do hardware/software Inventory". These are handled by the "Check_MK" service
                override_non_ok_state=parameters.fail_status,
                exit_spec_cb=config_cache.exit_code_spec,
                time_settings_cb=lambda hostname: config_cache.get_piggybacked_hosts_time_settings(
                    piggybacked_hostname=hostname,
                ),
                is_piggyback=host_config.is_piggyback_host,
            ),
            *check_parsing_errors(
                errors=fetched_data_result.parsing_errors,
                error_state=parameters.fail_status,
            ),
        ),
        inventory_tree=trees.inventory,
        update_result=update_result,
    )


#   .--cluster inventory---------------------------------------------------.
#   |                         _           _                                |
#   |                     ___| |_   _ ___| |_ ___ _ __                     |
#   |                    / __| | | | / __| __/ _ \ '__|                    |
#   |                   | (__| | |_| \__ \ ||  __/ |                       |
#   |                    \___|_|\__,_|___/\__\___|_|                       |
#   |                                                                      |
#   |             _                      _                                 |
#   |            (_)_ ____   _____ _ __ | |_ ___  _ __ _   _               |
#   |            | | '_ \ \ / / _ \ '_ \| __/ _ \| '__| | | |              |
#   |            | | | | \ V /  __/ | | | || (_) | |  | |_| |              |
#   |            |_|_| |_|\_/ \___|_| |_|\__\___/|_|   \__, |              |
#   |                                                  |___/               |
#   '----------------------------------------------------------------------'


def _inventorize_cluster(*, nodes: list[HostName]) -> StructuredDataNode:
    inventory_tree = StructuredDataNode()

    _add_cluster_property_to(inventory_tree=inventory_tree, is_cluster=True)

    if nodes:
        node = inventory_tree.setdefault_node(
            ("software", "applications", "check_mk", "cluster", "nodes")
        )
        node.table.add_key_columns(["name"])
        node.table.add_rows([{"name": node_name} for node_name in nodes])

    return inventory_tree


# .
#   .--real host data------------------------------------------------------.
#   |                   _   _               _         _       _            |
#   |    _ __ ___  __ _| | | |__   ___  ___| |_    __| | __ _| |_ __ _     |
#   |   | '__/ _ \/ _` | | | '_ \ / _ \/ __| __|  / _` |/ _` | __/ _` |    |
#   |   | | |  __/ (_| | | | | | | (_) \__ \ |_  | (_| | (_| | || (_| |    |
#   |   |_|  \___|\__,_|_| |_| |_|\___/|___/\__|  \__,_|\__,_|\__\__,_|    |
#   |                                                                      |
#   '----------------------------------------------------------------------'


def _fetch_real_host_data(
    host_name: HostName,
    *,
    host_config: HostConfig,
    selected_sections: SectionNameCollection,
) -> FetchedDataResult:
    ipaddress = config.lookup_ip_address(host_config)
    config_cache = config.get_config_cache()

    fetched: Sequence[
        tuple[SourceInfo, result.Result[AgentRawData | SNMPRawData, Exception], Snapshot]
    ] = fetch_all(
        make_sources(
            host_name,
            ipaddress,
            ip_lookup=lambda host_name: config.lookup_ip_address(
                config_cache.make_host_config(host_name)
            ),
            selected_sections=selected_sections,
            force_snmp_cache_refresh=False,
            on_scan_error=OnError.RAISE,
            simulation_mode=config.simulation_mode,
            missing_sys_description=config.get_config_cache().in_binary_hostlist(
                host_name, config.snmp_without_sys_descr
            ),
            file_cache_max_age=config_cache.max_cachefile_age(host_name),
        ),
        mode=(Mode.INVENTORY if selected_sections is NO_SELECTION else Mode.FORCE_SECTIONS),
    )
    host_sections, results = parse_messages(
        ((f[0], f[1]) for f in fetched),
        selected_sections=selected_sections,
        logger=logging.getLogger("cmk.base.inventory"),
    )
    store_piggybacked_sections(host_sections)
    broker = make_broker(host_sections)

    parsing_errors = broker.parsing_errors()
    return FetchedDataResult(
        parsed_sections_broker=broker,
        source_results=results,
        parsing_errors=parsing_errors,
        processing_failed=(
            _sources_failed(host_section for _source, host_section in results)
            or bool(parsing_errors)
        ),
        no_data_or_files=_no_data_or_files(host_name, host_sections.values()),
    )


def _sources_failed(
    host_sections: Iterable[result.Result[HostSections, Exception]],
) -> bool:
    """Check if data sources of a host failed

    If a data source failed, we may have incomlete data. In that case we
    may not write it to disk because that would result in a flapping state
    of the tree, which would blow up the inventory history (in terms of disk usage).
    """
    # If a result is not OK, that means the corresponding sections have not been added.
    return any(not host_section.is_ok() for host_section in host_sections)


def _no_data_or_files(host_name: HostName, host_sections: Iterable[HostSections]) -> bool:
    if any(host_sections):
        return False

    if Path(cmk.utils.paths.inventory_output_dir, str(host_name)).exists():
        return False

    if Path(cmk.utils.paths.status_data_dir, str(host_name)).exists():
        return False

    if (archive := Path(cmk.utils.paths.inventory_archive_dir, str(host_name))).exists() and any(
        archive.iterdir()
    ):
        return False

    return True


# .
#   .--real host inventory-------------------------------------------------.
#   |                              _   _               _                   |
#   |               _ __ ___  __ _| | | |__   ___  ___| |_                 |
#   |              | '__/ _ \/ _` | | | '_ \ / _ \/ __| __|                |
#   |              | | |  __/ (_| | | | | | | (_) \__ \ |_                 |
#   |              |_|  \___|\__,_|_| |_| |_|\___/|___/\__|                |
#   |                                                                      |
#   |             _                      _                                 |
#   |            (_)_ ____   _____ _ __ | |_ ___  _ __ _   _               |
#   |            | | '_ \ \ / / _ \ '_ \| __/ _ \| '__| | | |              |
#   |            | | | | \ V /  __/ | | | || (_) | |  | |_| |              |
#   |            |_|_| |_|\_/ \___|_| |_|\__\___/|_|   \__, |              |
#   |                                                  |___/               |
#   '----------------------------------------------------------------------'


#   ---inventorize real host------------------------------------------------


def _inventorize_real_host(
    *,
    now: int,
    items_of_inventory_plugins: Collection[ItemsOfInventoryPlugin],
    raw_intervals_from_config: RawIntervalsFromConfig,
    old_tree: StructuredDataNode,
) -> tuple[InventoryTrees, UpdateResult]:
    section.section_step("Create inventory or status data tree")

    trees = _create_trees_from_inventory_plugin_items(items_of_inventory_plugins)

    section.section_step("May update inventory tree")

    tree_updater = RealHostTreeUpdater(raw_intervals_from_config)
    tree_updater.may_add_cache_info(now=now, items_of_inventory_plugins=items_of_inventory_plugins)
    update_result = tree_updater.may_update(
        now=now,
        inventory_tree=trees.inventory,
        previous_tree=old_tree,
    )

    if not trees.inventory.is_empty():
        _add_cluster_property_to(inventory_tree=trees.inventory, is_cluster=False)

    return trees, update_result


#   ---do status data inventory---------------------------------------------


def inventorize_status_data_of_real_host(
    host_name: HostName,
    *,
    host_config: HostConfig,
    parsed_sections_broker: ParsedSectionsBroker,
    run_plugin_names: Container[InventoryPluginName],
) -> StructuredDataNode:
    return _create_trees_from_inventory_plugin_items(
        _collect_inventory_plugin_items(
            host_name,
            host_config=host_config,
            parsed_sections_broker=parsed_sections_broker,
            run_plugin_names=run_plugin_names,
        )
    ).status_data


# .
#   .--inventory plugin items----------------------------------------------.
#   |             _                      _                                 |
#   |            (_)_ ____   _____ _ __ | |_ ___  _ __ _   _               |
#   |            | | '_ \ \ / / _ \ '_ \| __/ _ \| '__| | | |              |
#   |            | | | | \ V /  __/ | | | || (_) | |  | |_| |              |
#   |            |_|_| |_|\_/ \___|_| |_|\__\___/|_|   \__, |              |
#   |                                                  |___/               |
#   |              _             _         _ _                             |
#   |        _ __ | |_   _  __ _(_)_ __   (_) |_ ___ _ __ ___  ___         |
#   |       | '_ \| | | | |/ _` | | '_ \  | | __/ _ \ '_ ` _ \/ __|        |
#   |       | |_) | | |_| | (_| | | | | | | | ||  __/ | | | | \__ \        |
#   |       | .__/|_|\__,_|\__, |_|_| |_| |_|\__\___|_| |_| |_|___/        |
#   |       |_|            |___/                                           |
#   '----------------------------------------------------------------------'


def _collect_inventory_plugin_items(
    host_name: HostName,
    *,
    host_config: HostConfig,
    parsed_sections_broker: ParsedSectionsBroker,
    run_plugin_names: Container[InventoryPluginName],
) -> Iterator[ItemsOfInventoryPlugin]:
    section.section_step("Executing inventory plugins")

    class_mutex: dict[tuple[str, ...], str] = {}
    for inventory_plugin in agent_based_register.iter_all_inventory_plugins():
        if inventory_plugin.name not in run_plugin_names:
            continue

        for source_type in (SourceType.HOST, SourceType.MANAGEMENT):
            if not (
                kwargs := get_section_kwargs(
                    parsed_sections_broker,
                    HostKey(host_name, source_type),
                    inventory_plugin.sections,
                )
            ):
                console.vverbose(
                    f" {tty.yellow}{tty.bold}{inventory_plugin.name}{tty.normal}:"
                    f" skipped (no data)\n"
                )
                continue

            # Inventory functions can optionally have a second argument: parameters.
            # These are configured via rule sets (much like check parameters).
            if inventory_plugin.inventory_ruleset_name is not None:
                kwargs = {
                    **kwargs,
                    "params": host_config.inventory_parameters(
                        inventory_plugin.inventory_ruleset_name
                    ),
                }

            try:
                inventory_plugin_items = [
                    _parse_inventory_plugin_item(
                        item,
                        class_mutex.setdefault(tuple(item.path), item.__class__.__name__),
                    )
                    for item in inventory_plugin.inventory_function(**kwargs)
                ]
            except Exception as exception:
                # TODO(ml): What is the `if cmk.utils.debug.enabled()` actually good for?
                if cmk.utils.debug.enabled():
                    raise

                console.warning(
                    f" {tty.red}{tty.bold}{inventory_plugin.name}{tty.normal}:"
                    f" failed: {exception}\n"
                )
                continue

            yield ItemsOfInventoryPlugin(
                items=inventory_plugin_items,
                raw_cache_info=parsed_sections_broker.get_cache_info(inventory_plugin.sections),
            )

            console.verbose(f" {tty.green}{tty.bold}{inventory_plugin.name}{tty.normal}: ok\n")


def _parse_inventory_plugin_item(item: object, expected_class_name: str) -> Attributes | TableRow:
    if not isinstance(item, (Attributes, TableRow)):
        # can't happen, inventory results are filtered
        raise NotImplementedError()

    if item.__class__.__name__ != expected_class_name:
        raise TypeError(
            f"Cannot create {item.__class__.__name__} at path {item.path}:"
            f" this is a {expected_class_name} node."
        )

    return item


# .
#   .--creating trees------------------------------------------------------.
#   |                       _   _               _                          |
#   |    ___ _ __ ___  __ _| |_(_)_ __   __ _  | |_ _ __ ___  ___  ___     |
#   |   / __| '__/ _ \/ _` | __| | '_ \ / _` | | __| '__/ _ \/ _ \/ __|    |
#   |  | (__| | |  __/ (_| | |_| | | | | (_| | | |_| | |  __/  __/\__ \    |
#   |   \___|_|  \___|\__,_|\__|_|_| |_|\__, |  \__|_|  \___|\___||___/    |
#   |                                   |___/                              |
#   '----------------------------------------------------------------------'


@dataclass(frozen=True)
class InventoryTrees:
    inventory: StructuredDataNode
    status_data: StructuredDataNode


def _create_trees_from_inventory_plugin_items(
    items_of_inventory_plugins: Iterable[ItemsOfInventoryPlugin],
) -> InventoryTrees:
    inventory_tree = StructuredDataNode()
    status_data_tree = StructuredDataNode()

    for items_of_inventory_plugin in items_of_inventory_plugins:
        for item in items_of_inventory_plugin.items:
            if isinstance(item, Attributes):
                if item.inventory_attributes:
                    node = inventory_tree.setdefault_node(tuple(item.path))
                    node.attributes.add_pairs(item.inventory_attributes)

                if item.status_attributes:
                    node = status_data_tree.setdefault_node(tuple(item.path))
                    node.attributes.add_pairs(item.status_attributes)

            elif isinstance(item, TableRow):
                # do this always, it sets key_columns!
                node = inventory_tree.setdefault_node(tuple(item.path))
                node.table.add_key_columns(sorted(item.key_columns))
                node.table.add_rows([{**item.key_columns, **item.inventory_columns}])

                if item.status_columns:
                    node = status_data_tree.setdefault_node(tuple(item.path))
                    node.table.add_key_columns(sorted(item.key_columns))
                    node.table.add_rows([{**item.key_columns, **item.status_columns}])

    return InventoryTrees(
        inventory=inventory_tree,
        status_data=status_data_tree,
    )


# .
#   .--cluster properties--------------------------------------------------.
#   |                         _           _                                |
#   |                     ___| |_   _ ___| |_ ___ _ __                     |
#   |                    / __| | | | / __| __/ _ \ '__|                    |
#   |                   | (__| | |_| \__ \ ||  __/ |                       |
#   |                    \___|_|\__,_|___/\__\___|_|                       |
#   |                                                                      |
#   |                                           _   _                      |
#   |           _ __  _ __ ___  _ __   ___ _ __| |_(_) ___  ___            |
#   |          | '_ \| '__/ _ \| '_ \ / _ \ '__| __| |/ _ \/ __|           |
#   |          | |_) | | | (_) | |_) |  __/ |  | |_| |  __/\__ \           |
#   |          | .__/|_|  \___/| .__/ \___|_|   \__|_|\___||___/           |
#   |          |_|             |_|                                         |
#   '----------------------------------------------------------------------'


def _add_cluster_property_to(*, inventory_tree: StructuredDataNode, is_cluster: bool) -> None:
    node = inventory_tree.setdefault_node(("software", "applications", "check_mk", "cluster"))
    node.attributes.add_pairs({"is_cluster": is_cluster})


# .
#   .--checks--------------------------------------------------------------.
#   |                         _               _                            |
#   |                     ___| |__   ___  ___| | _____                     |
#   |                    / __| '_ \ / _ \/ __| |/ / __|                    |
#   |                   | (__| | | |  __/ (__|   <\__ \                    |
#   |                    \___|_| |_|\___|\___|_|\_\___/                    |
#   |                                                                      |
#   '----------------------------------------------------------------------'


def _check_fetched_data_or_trees(
    *,
    parameters: config.HWSWInventoryParameters,
    fetched_data_result: FetchedDataResult,
    inventory_tree: StructuredDataNode,
    status_data_tree: StructuredDataNode,
    old_tree: StructuredDataNode,
) -> Iterator[ActiveCheckResult]:
    if fetched_data_result.no_data_or_files:
        yield ActiveCheckResult(0, "No data yet, please be patient")
        return

    if fetched_data_result.processing_failed:
        yield ActiveCheckResult(parameters.fail_status, "Cannot update tree")

    yield from _check_trees(
        parameters=parameters,
        inventory_tree=inventory_tree,
        status_data_tree=status_data_tree,
        old_tree=old_tree,
    )


def _check_trees(
    *,
    parameters: config.HWSWInventoryParameters,
    inventory_tree: StructuredDataNode,
    status_data_tree: StructuredDataNode,
    old_tree: StructuredDataNode,
) -> Iterator[ActiveCheckResult]:
    if inventory_tree.is_empty() and status_data_tree.is_empty():
        yield ActiveCheckResult(0, "Found no data")
        return

    yield ActiveCheckResult(0, f"Found {inventory_tree.count_entries()} inventory entries")

    swp_table = inventory_tree.get_table(("software", "packages"))
    if swp_table is not None and swp_table.is_empty() and parameters.sw_missing:
        yield ActiveCheckResult(parameters.sw_missing, "software packages information is missing")

    if not _tree_nodes_are_equal(old_tree, inventory_tree, "software"):
        yield ActiveCheckResult(parameters.sw_changes, "software changes")

    if not _tree_nodes_are_equal(old_tree, inventory_tree, "hardware"):
        yield ActiveCheckResult(parameters.hw_changes, "hardware changes")

    if not status_data_tree.is_empty():
        yield ActiveCheckResult(0, f"Found {status_data_tree.count_entries()} status entries")


def _tree_nodes_are_equal(
    old_tree: StructuredDataNode,
    inv_tree: StructuredDataNode,
    edge: str,
) -> bool:
    old_node = old_tree.get_node((edge,))
    inv_node = inv_tree.get_node((edge,))
    if old_node is None:
        return inv_node is None

    if inv_node is None:
        return False

    return old_node.is_equal(inv_node)
