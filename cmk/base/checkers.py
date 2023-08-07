#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

"""Concrete implementation of checkers functionality."""

from __future__ import annotations

import functools
import itertools
import logging
from collections.abc import Iterable, Iterator, Mapping, Sequence
from functools import partial
from typing import Callable, Final

import cmk.utils.resulttype as result
import cmk.utils.tty as tty
from cmk.utils.agentdatatype import AgentRawData
from cmk.utils.check_utils import unwrap_parameters
from cmk.utils.cpu_tracking import CPUTracker, Snapshot
from cmk.utils.exceptions import OnError
from cmk.utils.hostaddress import HostAddress, HostName
from cmk.utils.log import console
from cmk.utils.piggyback import PiggybackTimeSettings
from cmk.utils.sectionname import SectionMap, SectionName

from cmk.snmplib import SNMPRawData

from cmk.fetchers import Fetcher, get_raw_data, Mode
from cmk.fetchers.filecache import FileCache, FileCacheOptions, MaxAge

from cmk.checkengine.check_table import ConfiguredService
from cmk.checkengine.checking import CheckPlugin, CheckPluginName
from cmk.checkengine.checkresults import (
    ActiveCheckResult,
    MetricTuple,
    ServiceCheckResult,
    state_markers,
)
from cmk.checkengine.discovery import AutocheckEntry, DiscoveryPlugin, HostLabelPlugin
from cmk.checkengine.error_handling import ExitSpec
from cmk.checkengine.fetcher import SourceInfo
from cmk.checkengine.inventory import InventoryPlugin, InventoryPluginName
from cmk.checkengine.parser import HostSections, NO_SELECTION, parse_raw_data, SectionNameCollection
from cmk.checkengine.sectionparser import SectionPlugin
from cmk.checkengine.submitters import ServiceState
from cmk.checkengine.summarize import summarize

import cmk.base.api.agent_based.register as agent_based_register
import cmk.base.api.agent_based.register._config as _api
import cmk.base.config as config
from cmk.base.api.agent_based import cluster_mode, plugin_contexts, value_store
from cmk.base.api.agent_based.checking_classes import CheckPlugin as CheckPluginAPI
from cmk.base.api.agent_based.checking_classes import consume_check_results
from cmk.base.api.agent_based.checking_classes import Result as CheckFunctionResult
from cmk.base.api.agent_based.checking_classes import State
from cmk.base.api.agent_based.value_store import ValueStoreManager
from cmk.base.config import ConfigCache
from cmk.base.sources import make_parser, make_sources, Source

__all__ = [
    "CheckPluginMapper",
    "CMKFetcher",
    "CMKParser",
    "CMKSummarizer",
    "DiscoveryPluginMapper",
    "HostLabelPluginMapper",
    "InventoryPluginMapper",
    "SectionPluginMapper",
]


def _fetch_all(
    sources: Iterable[Source], *, simulation: bool, file_cache_options: FileCacheOptions, mode: Mode
) -> Sequence[tuple[SourceInfo, result.Result[AgentRawData | SNMPRawData, Exception], Snapshot,]]:
    console.verbose("%s+%s %s\n", tty.yellow, tty.normal, "Fetching data".upper())
    return [
        _do_fetch(
            source.source_info(),
            source.file_cache(simulation=simulation, file_cache_options=file_cache_options),
            source.fetcher(),
            mode=mode,
        )
        for source in sources
    ]


def _do_fetch(
    source_info: SourceInfo,
    file_cache: FileCache,
    fetcher: Fetcher,
    *,
    mode: Mode,
) -> tuple[SourceInfo, result.Result[AgentRawData | SNMPRawData, Exception], Snapshot,]:
    console.vverbose(f"  Source: {source_info}\n")
    with CPUTracker() as tracker:
        raw_data = get_raw_data(file_cache, fetcher, mode)
    return source_info, raw_data, tracker.duration


class CMKParser:
    def __init__(
        self,
        config_cache: ConfigCache,
        *,
        selected_sections: SectionNameCollection,
        keep_outdated: bool,
        logger: logging.Logger,
    ) -> None:
        self.config_cache: Final = config_cache
        self.selected_sections: Final = selected_sections
        self.keep_outdated: Final = keep_outdated
        self.logger: Final = logger

    def __call__(
        self,
        fetched: Iterable[
            tuple[
                SourceInfo,
                result.Result[AgentRawData | SNMPRawData, Exception],
            ]
        ],
    ) -> Sequence[tuple[SourceInfo, result.Result[HostSections, Exception]]]:
        """Parse fetched data."""
        console.vverbose("%s+%s %s\n", tty.yellow, tty.normal, "Parse fetcher results".upper())
        output: list[tuple[SourceInfo, result.Result[HostSections, Exception]]] = []
        # Special agents can produce data for the same check_plugin_name on the same host, in this case
        # the section lines need to be extended
        for source, raw_data in fetched:
            source_result = parse_raw_data(
                make_parser(
                    self.config_cache,
                    source,
                    checking_sections=self.config_cache.make_checking_sections(
                        source.hostname, selected_sections=NO_SELECTION
                    ),
                    keep_outdated=self.keep_outdated,
                    logger=self.logger,
                ),
                raw_data,
                selection=self.selected_sections,
            )
            output.append((source, source_result))
        return output


class CMKSummarizer:
    def __init__(
        self,
        config_cache: ConfigCache,
        host_name: HostName,
        *,
        override_non_ok_state: ServiceState | None = None,
    ) -> None:
        self.config_cache: Final = config_cache
        self.host_name: Final = host_name
        self.override_non_ok_state: Final = override_non_ok_state

    def __call__(
        self,
        host_sections: Iterable[tuple[SourceInfo, result.Result[HostSections, Exception]]],
    ) -> Iterable[ActiveCheckResult]:
        return [
            _summarize_host_sections(
                host_sections,
                source,
                override_non_ok_state=self.override_non_ok_state,
                exit_spec=self.config_cache.exit_code_spec(source.hostname, source.ident),
                time_settings=self.config_cache.get_piggybacked_hosts_time_settings(
                    piggybacked_hostname=source.hostname
                ),
                is_piggyback=self.config_cache.is_piggyback_host(self.host_name),
            )
            for source, host_sections in host_sections
        ]


def _summarize_host_sections(
    host_sections: result.Result[HostSections, Exception],
    source: SourceInfo,
    *,
    override_non_ok_state: ServiceState | None = None,
    exit_spec: ExitSpec,
    time_settings: PiggybackTimeSettings,
    is_piggyback: bool,
) -> ActiveCheckResult:
    return ActiveCheckResult.from_subresults(
        *(
            ActiveCheckResult(
                s.state
                if (s.state == 0 or override_non_ok_state is None)
                else override_non_ok_state,
                f"[{source.ident}] {s.summary}" if idx == 0 else s.summary,
                s.details,
                s.metrics,
            )
            for idx, s in enumerate(
                summarize(
                    source.hostname,
                    source.ipaddress,
                    host_sections,
                    exit_spec=exit_spec,
                    time_settings=time_settings,
                    is_piggyback=is_piggyback,
                    fetcher_type=source.fetcher_type,
                )
            )
        )
    )


class CMKFetcher:
    def __init__(
        self,
        config_cache: ConfigCache,
        *,
        # alphabetically sorted
        file_cache_options: FileCacheOptions,
        force_snmp_cache_refresh: bool,
        mode: Mode,
        on_error: OnError,
        selected_sections: SectionNameCollection,
        simulation_mode: bool,
        max_cachefile_age: MaxAge | None = None,
    ) -> None:
        self.config_cache: Final = config_cache
        self.file_cache_options: Final = file_cache_options
        self.force_snmp_cache_refresh: Final = force_snmp_cache_refresh
        self.mode: Final = mode
        self.on_error: Final = on_error
        self.selected_sections: Final = selected_sections
        self.simulation_mode: Final = simulation_mode
        self.max_cachefile_age: Final = max_cachefile_age

    def __call__(
        self, host_name: HostName, *, ip_address: HostAddress | None
    ) -> Sequence[
        tuple[
            SourceInfo,
            result.Result[AgentRawData | SNMPRawData, Exception],
            Snapshot,
        ]
    ]:
        nodes = self.config_cache.nodes_of(host_name)
        if nodes is None:
            # In case of keepalive we always have an ipaddress (can be 0.0.0.0 or :: when
            # address is unknown). When called as non keepalive ipaddress may be None or
            # is already an address (2nd argument)
            hosts = [
                (host_name, ip_address or config.lookup_ip_address(self.config_cache, host_name))
            ]
        else:
            hosts = [(node, config.lookup_ip_address(self.config_cache, node)) for node in nodes]

        return _fetch_all(
            itertools.chain.from_iterable(
                make_sources(
                    host_name_,
                    ip_address_,
                    ConfigCache.address_family(host_name),
                    config_cache=self.config_cache,
                    force_snmp_cache_refresh=(
                        self.force_snmp_cache_refresh if nodes is None else False
                    ),
                    selected_sections=self.selected_sections if nodes is None else NO_SELECTION,
                    on_scan_error=self.on_error if nodes is None else OnError.RAISE,
                    simulation_mode=self.simulation_mode,
                    file_cache_options=self.file_cache_options,
                    file_cache_max_age=self.max_cachefile_age
                    or self.config_cache.max_cachefile_age(host_name),
                )
                for host_name_, ip_address_ in hosts
            ),
            simulation=self.simulation_mode,
            file_cache_options=self.file_cache_options,
            mode=self.mode,
        )


class SectionPluginMapper(SectionMap[SectionPlugin]):
    # We should probably not tap into the private `register._config` module but
    # the data we need doesn't seem to be available elsewhere.  Anyway, this is
    # an *immutable* Mapping so we are actually on the safe side.

    def __getitem__(self, __key: SectionName) -> SectionPlugin:
        plugin = _api.get_section_plugin(__key)
        return SectionPlugin(
            supersedes=plugin.supersedes,
            parse_function=plugin.parse_function,
            parsed_section_name=plugin.parsed_section_name,
        )

    def __iter__(self) -> Iterator[SectionName]:
        return iter(
            frozenset(_api.registered_agent_sections) | frozenset(_api.registered_snmp_sections)
        )

    def __len__(self) -> int:
        return len(
            frozenset(_api.registered_agent_sections) | frozenset(_api.registered_snmp_sections)
        )


class HostLabelPluginMapper(SectionMap[HostLabelPlugin]):
    def __init__(self, *, config_cache: ConfigCache) -> None:
        super().__init__()
        self.config_cache: Final = config_cache

    def __getitem__(self, __key: SectionName) -> HostLabelPlugin:
        plugin = _api.get_section_plugin(__key)
        return HostLabelPlugin(
            function=plugin.host_label_function,
            parameters=partial(
                config.get_plugin_parameters,
                config_cache=self.config_cache,
                default_parameters=plugin.host_label_default_parameters,
                ruleset_name=plugin.host_label_ruleset_name,
                ruleset_type=plugin.host_label_ruleset_type,
                rules_getter_function=agent_based_register.get_host_label_ruleset,
            ),
        )

    def __iter__(self) -> Iterator[SectionName]:
        return iter(
            frozenset(_api.registered_agent_sections) | frozenset(_api.registered_snmp_sections)
        )

    def __len__(self) -> int:
        return len(
            frozenset(_api.registered_agent_sections) | frozenset(_api.registered_snmp_sections)
        )


class CheckPluginMapper(Mapping[CheckPluginName, CheckPlugin]):
    # See comment to SectionPluginMapper.
    def __init__(self, config_cache: ConfigCache, value_store_manager: ValueStoreManager):
        self.config_cache: Final = config_cache
        self.value_store_manager: Final = value_store_manager

    def __getitem__(self, __key: CheckPluginName) -> CheckPlugin:
        plugin = _api.get_check_plugin(__key)
        if plugin is None:
            raise KeyError(__key)

        def check_function(
            host_name: HostName, service: ConfiguredService
        ) -> Callable[..., ServiceCheckResult]:
            return _get_check_function(
                plugin, self.config_cache, host_name, service, self.value_store_manager
            )

        return CheckPlugin(
            sections=plugin.sections,
            function=check_function,
            default_parameters=plugin.check_default_parameters,
            ruleset_name=plugin.check_ruleset_name,
        )

    def __iter__(self) -> Iterator[CheckPluginName]:
        return iter(_api.registered_check_plugins)

    def __len__(self) -> int:
        return len(_api.registered_check_plugins)


def _get_check_function(
    plugin: CheckPluginAPI,
    config_cache: ConfigCache,
    host_name: HostName,
    service: ConfiguredService,
    value_store_manager: value_store.ValueStoreManager,
) -> Callable[..., ServiceCheckResult]:
    assert plugin.name == service.check_plugin_name
    check_function = (
        cluster_mode.get_cluster_check_function(
            *config_cache.get_clustered_service_configuration(host_name, service.description),
            plugin=plugin,
            service_id=service.id(),
            value_store_manager=value_store_manager,
        )
        if config_cache.is_cluster(host_name)
        else plugin.check_function
    )

    @functools.wraps(check_function)
    def __check_function(*args: object, **kw: object) -> ServiceCheckResult:
        with plugin_contexts.current_service(
            service.check_plugin_name, service.description
        ), value_store_manager.namespace(service.id()):
            return _aggregate_results(consume_check_results(check_function(*args, **kw)))

    return __check_function


def _aggregate_results(
    subresults: tuple[Sequence[MetricTuple], Sequence[CheckFunctionResult]]
) -> ServiceCheckResult:
    # Impedance matching part of `get_check_function()`.
    perfdata, results = subresults
    needs_marker = len(results) > 1
    summaries: list[str] = []
    details: list[str] = []
    status = State.OK

    def _add_state_marker(result_str: str, state_marker: str) -> str:
        return result_str if state_marker in result_str else result_str + state_marker

    for result_ in results:
        status = State.worst(status, result_.state)
        state_marker = state_markers[int(result_.state)] if needs_marker else ""
        if result_.summary:
            summaries.append(
                _add_state_marker(
                    result_.summary,
                    state_marker,
                )
            )
        details.append(
            _add_state_marker(
                result_.details,
                state_marker,
            )
        )

    # Empty list? Check returned nothing
    if not details:
        return ServiceCheckResult.item_not_found()

    if not summaries:
        count = len(details)
        summaries.append(
            "Everything looks OK - %d detail%s available" % (count, "" if count == 1 else "s")
        )
    all_text = [", ".join(summaries)] + details
    return ServiceCheckResult(int(status), "\n".join(all_text).strip(), perfdata)


class DiscoveryPluginMapper(Mapping[CheckPluginName, DiscoveryPlugin]):
    # See comment to SectionPluginMapper.
    def __init__(self, *, config_cache: ConfigCache) -> None:
        super().__init__()
        self.config_cache: Final = config_cache

    def __getitem__(self, __key: CheckPluginName) -> DiscoveryPlugin:
        # `get_check_plugin()` is not an error.  Both check plugins and
        # discovery are declared together in the check API.
        plugin = _api.get_check_plugin(__key)
        if plugin is None:
            raise KeyError(__key)

        def __discovery_function(
            check_plugin_name: CheckPluginName, *args: object, **kw: object
        ) -> Iterable[AutocheckEntry]:
            # Deal with impededance mismatch between check API and check engine.
            yield from (
                AutocheckEntry(
                    check_plugin_name=check_plugin_name,
                    item=service.item,
                    parameters=unwrap_parameters(service.parameters),
                    service_labels={label.name: label.value for label in service.labels},
                )
                for service in plugin.discovery_function(*args, **kw)
            )

        return DiscoveryPlugin(
            sections=plugin.sections,
            service_name=plugin.service_name,
            function=__discovery_function,
            parameters=partial(
                config.get_plugin_parameters,
                config_cache=self.config_cache,
                default_parameters=plugin.discovery_default_parameters,
                ruleset_name=plugin.discovery_ruleset_name,
                ruleset_type=plugin.discovery_ruleset_type,
                rules_getter_function=agent_based_register.get_discovery_ruleset,
            ),
        )

    def __iter__(self) -> Iterator[CheckPluginName]:
        return iter(_api.registered_check_plugins)

    def __len__(self) -> int:
        return len(_api.registered_check_plugins)


class InventoryPluginMapper(Mapping[InventoryPluginName, InventoryPlugin]):
    # See comment to SectionPluginMapper.
    def __getitem__(self, __key: InventoryPluginName) -> InventoryPlugin:
        plugin = _api.registered_inventory_plugins[__key]
        return InventoryPlugin(
            sections=plugin.sections,
            function=plugin.inventory_function,
            ruleset_name=plugin.inventory_ruleset_name,
        )

    def __iter__(self) -> Iterator[InventoryPluginName]:
        return iter(_api.registered_inventory_plugins)

    def __len__(self) -> int:
        return len(_api.registered_inventory_plugins)
