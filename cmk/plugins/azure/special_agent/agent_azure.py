#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.
"""
Special agent azure: Monitoring Azure cloud applications with Checkmk

Resources and resourcegroups are all treated lowercase because of:
https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/frequently-asked-questions#are-resource-group-names-case-sensitive
"""

from __future__ import annotations

import asyncio
import datetime
import enum
import json
import logging
import re
import string
import sys
from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping, Sequence
from enum import Enum
from multiprocessing import Lock
from pathlib import Path
from typing import Any, Literal, Required, TypedDict, TypeVar

import requests

from cmk.plugins.azure.special_agent.azure_api_client import (
    ApiError,
    ApiErrorAuthorizationRequestDenied,
    ApiErrorMissingData,
    ApiLoginFailed,
    BaseAsyncApiClient,
    get_graph_authority_urls,
    get_mgmt_authority_urls,
    NoConsumptionAPIError,
)
from cmk.special_agents.v0_unstable.agent_common import special_agent_main
from cmk.special_agents.v0_unstable.argument_parsing import Args, create_default_argument_parser
from cmk.special_agents.v0_unstable.misc import DataCache
from cmk.utils import password_store
from cmk.utils.http_proxy_config import deserialize_http_proxy_config
from cmk.utils.paths import tmp_dir

T = TypeVar("T")
GroupLabels = Mapping[str, Mapping[str, str]]

LOGGER = logging.getLogger("agent_azure")

AZURE_CACHE_FILE_PATH = tmp_dir / "agents" / "agent_azure"

NOW = datetime.datetime.now(tz=datetime.UTC)

SUPPORTED_FLEXIBLE_DATABASE_SERVER_RESOURCE_TYPES = frozenset(
    {
        "Microsoft.DBforMySQL/flexibleServers",
        "Microsoft.DBforPostgreSQL/flexibleServers",
    }
)

ALL_METRICS: dict[str, list[tuple[str, str, str]]] = {
    # to add a new metric, just add a made up name, run the
    # agent, and you'll get a error listing available metrics!
    # key: list of (name(s), interval, aggregation, filter)
    # NB: Azure API won't have requests with more than 20 metric names at once
    # Also remember to add the service to the WATO rule:
    # cmk/gui/plugins/wato/special_agents/azure.py
    "Microsoft.Network/virtualNetworkGateways": [
        ("AverageBandwidth,P2SBandwidth", "PT5M", "average"),
        ("TunnelIngressBytes", "PT5M", "count"),
        ("TunnelEgressBytes", "PT5M", "count"),
        ("TunnelIngressPacketDropCount", "PT5M", "count"),
        ("TunnelEgressPacketDropCount", "PT5M", "count"),
        ("P2SConnectionCount", "PT1M", "maximum"),
    ],
    "Microsoft.Sql/servers/databases": [
        (
            "storage_percent,deadlock,cpu_percent,dtu_consumption_percent,"
            "connection_successful,connection_failed",
            "PT1M",
            "average",
        ),
    ],
    "Microsoft.Storage/storageAccounts": [
        (
            "UsedCapacity,Ingress,Egress,Transactions",
            "PT1H",
            "total",
        ),
        (
            "SuccessServerLatency,SuccessE2ELatency,Availability",
            "PT1H",
            "average",
        ),
    ],
    "Microsoft.Web/sites": [
        ("CpuTime,AverageResponseTime,Http5xx", "PT1M", "total"),
    ],
    "Microsoft.DBforMySQL/servers": [
        (
            "cpu_percent,memory_percent,io_consumption_percent,serverlog_storage_percent,"
            "storage_percent,active_connections",
            "PT1M",
            "average",
        ),
        (
            "connections_failed,network_bytes_ingress,network_bytes_egress",
            "PT1M",
            "total",
        ),
        (
            "seconds_behind_master",
            "PT1M",
            "maximum",
        ),
    ],
    "Microsoft.DBforMySQL/flexibleServers": [
        (
            # NOTE: the "serverlog_storage_percent" metric may soon be phased out of the MySQL
            # flexible server as it is no longer mentioned in the documentation and is not present
            # in PostgreSQL flexible server documentation.
            "cpu_percent,memory_percent,io_consumption_percent,serverlog_storage_percent,"
            "storage_percent,active_connections",
            "PT1M",
            "average",
        ),
        (
            "aborted_connections,network_bytes_ingress,network_bytes_egress",
            "PT1M",
            "total",
        ),
        (
            "replication_lag",
            "PT1M",
            "maximum",
        ),
    ],
    "Microsoft.DBforPostgreSQL/servers": [
        (
            "cpu_percent,memory_percent,io_consumption_percent,serverlog_storage_percent,"
            "storage_percent,active_connections",
            "PT1M",
            "average",
        ),
        (
            "connections_failed,network_bytes_ingress,network_bytes_egress",
            "PT1M",
            "total",
        ),
        (
            "pg_replica_log_delay_in_seconds",
            "PT1M",
            "maximum",
        ),
    ],
    "Microsoft.DBforPostgreSQL/flexibleServers": [
        (
            "cpu_percent,memory_percent,disk_iops_consumed_percentage,storage_percent,active_connections",
            "PT1M",
            "average",
        ),
        (
            "connections_failed,network_bytes_ingress,network_bytes_egress",
            "PT1M",
            "total",
        ),
        (
            "physical_replication_delay_in_seconds",
            "PT1M",
            "maximum",
        ),
    ],
    "Microsoft.Network/trafficmanagerprofiles": [
        (
            "QpsByEndpoint",
            "PT1M",
            "total",
        ),
        (
            "ProbeAgentCurrentEndpointStateByProfileResourceId",
            "PT1M",
            "maximum",
        ),
    ],
    "Microsoft.Network/loadBalancers": [
        (
            "ByteCount",
            "PT1M",
            "total",
        ),
        (
            "AllocatedSnatPorts,UsedSnatPorts,VipAvailability,DipAvailability",
            "PT1M",
            "average",
        ),
    ],
    "Microsoft.Network/applicationGateways": [
        ("HealthyHostCount", "PT1M", "average"),
        ("FailedRequests", "PT1M", "count"),
    ],
    "Microsoft.Compute/virtualMachines": [
        (
            "Percentage CPU,CPU Credits Consumed,CPU Credits Remaining,Available Memory Bytes,Disk Read Operations/Sec,Disk Write Operations/Sec",
            "PT1M",
            "average",
        ),
        (
            "Network In Total,Network Out Total,Disk Read Bytes,Disk Write Bytes",
            "PT1M",
            "total",
        ),
    ],
}

OPTIONAL_METRICS: Mapping[str, Sequence[str]] = {
    "Microsoft.Sql/servers/databases": [
        "storage_percent",
        "deadlock",
        "dtu_consumption_percent",
    ],
    "Microsoft.DBforMySQL/servers": ["seconds_behind_master"],
    "Microsoft.DBforMySQL/flexibleServers": ["replication_lag"],
    "Microsoft.DBforPostgreSQL/servers": ["pg_replica_log_delay_in_seconds"],
    "Microsoft.DBforPostgreSQL/flexibleServers": ["physical_replication_delay_in_seconds"],
    "Microsoft.Network/loadBalancers": ["AllocatedSnatPorts", "UsedSnatPorts"],
    "Microsoft.Compute/virtualMachines": [
        "CPU Credits Consumed",
        "CPU Credits Remaining",
    ],
}


class FetchedResource(Enum):
    """Available Azure resources, with section name, for API fetching"""

    virtual_machines = ("Microsoft.Compute/virtualMachines", "virtualmachines")
    vaults = ("Microsoft.RecoveryServices/vaults", "vaults")
    app_gateways = ("Microsoft.Network/applicationGateways", "applicationgateways")
    load_balancers = ("Microsoft.Network/loadBalancers", "loadbalancers")
    virtual_network_gateways = (
        "Microsoft.Network/virtualNetworkGateways",
        "virtualnetworkgateways",
    )

    def __init__(self, resource_type, section_name):
        self.resource_type = resource_type
        self.section_name = section_name

    @property
    def section(self):
        return self.section_name

    @property
    def type(self):
        return self.resource_type


BULK_QUERIED_RESOURCES = {
    FetchedResource.virtual_machines.type,
    FetchedResource.app_gateways.type,
    FetchedResource.load_balancers.type,
}


class TagsImportPatternOption(enum.Enum):
    ignore_all = "IGNORE_ALL"
    import_all = "IMPORT_ALL"


TagsOption = str | Literal[TagsImportPatternOption.ignore_all, TagsImportPatternOption.import_all]


def _chunks(list_: Sequence[T], length: int = 50) -> Sequence[Sequence[T]]:
    return [list_[i : i + length] for i in range(0, len(list_), length)]


def parse_arguments(argv: Sequence[str] | None) -> Args:
    parser = create_default_argument_parser(description=__doc__)
    parser.add_argument(
        "--dump-config",
        action="store_true",
        help="""Dump parsed configuration and exit""",
    )
    parser.add_argument(
        "--timeout",
        default=10,
        type=int,
        help="""Timeout for individual processes in seconds (default 10)""",
    )
    parser.add_argument(
        "--piggyback_vms",
        default="grouphost",
        choices=["grouphost", "self"],
        help="""Send VM piggyback data to group host (default) or the VM iteself""",
    )

    group_subscription = parser.add_mutually_exclusive_group(required=False)
    group_subscription.add_argument(
        "--subscription",
        dest="subscriptions",
        action="append",
        default=[],
        help="Azure subscription IDs",
    )
    group_subscription.add_argument(
        "--all-subscriptions",
        action="store_true",
        help="Monitor all available Azure subscriptions",
    )

    # REQUIRED
    parser.add_argument("--client", required=True, help="Azure client ID")
    parser.add_argument("--tenant", required=True, help="Azure tenant ID")
    parser.add_argument("--secret", required=True, help="Azure authentication secret")
    parser.add_argument(
        "--cache-id",
        required="--connection-test" not in sys.argv,
        help="Unique id for this special agent configuration",
    )

    parser.add_argument(
        "--proxy",
        type=str,
        default=None,
        metavar="PROXY",
        help=(
            "HTTP proxy used to connect to the Azure API. If not set, the environment settings "
            "will be used."
        ),
    )

    # CONSTRAIN DATA TO REQUEST
    parser.add_argument(
        "--require-tag",
        default=[],
        metavar="TAG",
        action="append",
        help="""Only monitor resources that have the specified TAG.
              To require multiple tags, provide the option more than once.""",
    )
    parser.add_argument(
        "--require-tag-value",
        default=[],
        metavar=("TAG", "VALUE"),
        nargs=2,
        action="append",
        help="""Only monitor resources that have the specified TAG set to VALUE.
             To require multiple tags, provide the option more than once.""",
    )
    parser.add_argument(
        "--explicit-config",
        default=[],
        nargs="*",
        help="""list of arguments providing the configuration in <key>=<value> format.
             If omitted, all groups and all resources of the services specified in --services are
             fetched.
             If specified, every 'group=<name>' argument starts a new group configuration,
             and every 'resource=<name>' arguments specifies a resource.""",
    )
    parser.add_argument(
        "--services",
        default=[],
        nargs="*",
        help="List of services to monitor",
    )
    parser.add_argument(
        "--authority",
        default="global",
        choices=["global", "china"],
        required=True,
        help="Authority to be used",
    )

    group_import_tags = parser.add_mutually_exclusive_group()
    group_import_tags.add_argument(
        "--ignore-all-tags",
        action="store_const",
        const=TagsImportPatternOption.ignore_all,
        dest="tag_key_pattern",
        help="By default, all Azure tags are written to the agent output, validated to meet the "
        "Checkmk label requirements and added as host labels to their respective piggyback host "
        "and/or as service labels to the respective service using the syntax "
        "'cmk/azure/tag/{key}:{value}'. With this option you can disable the import of Azure "
        "tags.",
    )
    group_import_tags.add_argument(
        "--import-matching-tags-as-labels",
        dest="tag_key_pattern",
        help="You can restrict the imported tags by specifying a pattern which the agent searches "
        "for in the key of the tag.",
    )
    group_import_tags.set_defaults(tag_key_pattern=TagsImportPatternOption.import_all)

    parser.add_argument(
        "--connection-test",
        action="store_true",
        help="Run a connection test through the Management API only. No further agent code is "
        "executed.",
    )

    # I'm not sure this is still needed
    if argv is None:
        password_store.replace_passwords()
        argv = sys.argv[1:]

    args = parser.parse_args(argv)
    return args


# The following *Config objects provide a Configuration instance as described in
# CMK-513 (comment-12620).
# For now the passed commandline arguments are used to create it.


class GroupConfig:
    def __init__(self, name: str) -> None:
        super().__init__()
        if not name:
            raise ValueError("falsey group name: %r" % name)
        self.name = name
        self.resources: list = []

    @property
    def fetchall(self):
        return not self.resources

    def add_key(self, key: str, value: str) -> None:
        if key == "resources":
            self.resources = value.split(",")
            return
        raise ValueError("unknown config key: %s" % key)

    def __str__(self) -> str:
        if self.fetchall:
            return "[%s]\n  <fetchall>" % self.name
        return "[%s]\n" % self.name + "\n".join("resource: %s" % r for r in self.resources)


class ExplicitConfig:
    def __init__(self, raw_list: Sequence[str]) -> None:
        super().__init__()
        self.groups: dict = {}
        self.current_group = None
        for item in raw_list:
            if "=" not in item:
                raise ValueError("must be in <key>=<value> format: %r" % item)
            key, value = item.split("=", 1)
            self.add_key(key, value)

    @property
    def fetchall(self) -> bool:
        return not self.groups

    def add_key(self, key: str, value: str) -> None:
        if key == "group":
            group_name = value.lower()
            self.current_group = self.groups.setdefault(group_name, GroupConfig(group_name))
            return
        if self.current_group is None:
            raise RuntimeError("missing arg: group=<name>")
        self.current_group.add_key(key, value)

    def is_configured(self, resource: AzureResource) -> bool:
        if self.fetchall:
            return True
        group_config = self.groups.get(resource.info["group"].lower())
        if group_config is None:
            return False
        if group_config.fetchall:
            return True
        return resource.info["name"] in group_config.resources

    def __str__(self) -> str:
        if self.fetchall:
            return "[<fetchall>]"
        return "\n".join(str(group) for group in self.groups.values())


class TagBasedConfig:
    def __init__(self, required: Sequence[str], key_values: Sequence[Sequence[str]]) -> None:
        super().__init__()
        self._required = required
        self._values = key_values

    def is_configured(self, resource: AzureResource) -> bool:
        if not all(k in resource.tags for k in self._required):
            return False
        for key, val in self._values:
            if resource.tags.get(key) != val:
                return False
        return True

    def __str__(self) -> str:
        lines = []
        if self._required:
            lines.append("required tags: %s" % ", ".join(self._required))
        for key, val in self._values:
            lines.append(f"required value for {key!r}: {val!r}")
        return "\n".join(lines)


class Selector:
    def __init__(self, args: Args) -> None:
        super().__init__()
        self._explicit_config = ExplicitConfig(raw_list=args.explicit_config)
        self._tag_based_config = TagBasedConfig(args.require_tag, args.require_tag_value)

    def do_monitor(self, resource: AzureResource) -> bool:
        if not self._explicit_config.is_configured(resource):
            return False
        if not self._tag_based_config.is_configured(resource):
            return False
        return True

    def __str__(self) -> str:
        lines = [
            "Explicit configuration:\n  %s" % str(self._explicit_config).replace("\n", "\n  "),
            "Tag based configuration:\n  %s" % str(self._tag_based_config).replace("\n", "\n  "),
        ]
        return "\n".join(lines)


class Section:
    LOCK = Lock()

    def __init__(
        self,
        name: str,
        piggytargets: Iterable[str],
        separator: int,
        options: Sequence[str],
    ) -> None:
        super().__init__()
        self._sep = chr(separator)
        self._piggytargets = list(piggytargets)
        self._cont: list = []
        section_options = ":".join(["sep(%d)" % separator, *options])
        self._title = f"<<<{name.replace('-', '_')}:{section_options}>>>\n"

    def _formatline(self, tokens):
        return self._sep.join(map(str, tokens)) + "\n"

    def add(self, info):
        if not info:
            return
        if isinstance(info[0], list | tuple):  # we got a list of lines
            for row in info:
                self._cont.append(self._formatline(row))
        else:  # assume one single line
            self._cont.append(self._formatline(info))

    def write(self, write_empty: bool = False) -> None:
        if not (write_empty or self._cont):
            return
        with self.LOCK:
            for piggytarget in self._piggytargets:
                sys.stdout.write(f"<<<<{piggytarget}>>>>\n")
                sys.stdout.write(self._title)
                sys.stdout.writelines(self._cont)
            sys.stdout.write("<<<<>>>>\n")
            sys.stdout.flush()

    def __repr__(self) -> str:
        return (
            f"Section(\n"
            f"    title={self._title},\n"
            f"    piggytargets={self._piggytargets},\n"
            f"    separator={self._sep},\n"
            f"    content={self._cont}"
            f")"
        )

    def __eq__(self, value):
        if not isinstance(value, Section):
            return False
        return (
            self._title == value._title
            and self._piggytargets == value._piggytargets
            and self._sep == value._sep
            and self._cont == value._cont
        )


class AzureSection(Section):
    def __init__(
        self, name: str, piggytargets: Iterable[str] = ("",), separator: int = 124
    ) -> None:
        super().__init__("azure_%s" % name, piggytargets, separator=separator, options=[])


class LabelsSection(Section):
    def __init__(self, piggytarget: str) -> None:
        super().__init__("azure_labels", [piggytarget], separator=0, options=[])


class IssueCollector:
    def __init__(self) -> None:
        super().__init__()
        self._list: list[tuple[str, str]] = []

    def add(self, issue_type: str, issued_by: str, issue_msg: str) -> None:
        issue = {"type": issue_type, "issued_by": issued_by, "msg": issue_msg}
        self._list.append(("issue", json.dumps(issue)))

    def dumpinfo(self) -> list[tuple[str, str]]:
        return self._list

    def __len__(self) -> int:
        return len(self._list)


def create_metric_dict(metric, aggregation, interval_id):
    name = metric["name"]["value"]
    metric_dict = {
        "name": name,
        "aggregation": aggregation,
        "value": None,
        "unit": metric["unit"].lower(),
        "timestamp": None,
        "interval_id": interval_id,
        "interval": None,
    }

    timeseries = metric.get("timeseries")
    if not timeseries:
        return None

    for measurement in reversed(timeseries):
        dataset = measurement.get("data", ())
        if not dataset:
            continue

        try:
            metric_dict["interval"] = str(
                datetime.datetime.strptime(dataset[-1]["timeStamp"], "%Y-%m-%dT%H:%M:%SZ")
                - datetime.datetime.strptime(dataset[-2]["timeStamp"], "%Y-%m-%dT%H:%M:%SZ")
            )
        except (IndexError, TypeError):
            pass

        for data in reversed(dataset):
            LOGGER.debug("data: %s", data)
            metric_dict["value"] = data.get(aggregation)
            if metric_dict["value"] is not None:
                metric_dict["timestamp"] = data["timeStamp"]
                return metric_dict

    return None


def get_attrs_from_uri(uri: str) -> Mapping[str, str]:
    """The uri contains info on subscription, resource group, provider."""
    attrs = {}
    segments = uri.split("/")
    for idx, segment in enumerate(segments):
        if segment in ("subscriptions", "providers"):
            attrs[segment[:-1]] = segments[idx + 1]
        if segment.lower() == "resourcegroups":
            # we have seen "resouceGroups" and "resourcegroups"
            attrs["group"] = segments[idx + 1]
    return attrs


class AzureResource:
    def __init__(
        self,
        info: Mapping[str, Any],
        tag_key_pattern: TagsOption,
    ) -> None:
        super().__init__()
        self.tags = self._filter_tags(info.get("tags", {}), tag_key_pattern)
        self.info = {**info, "tags": self.tags}
        self.info.update(get_attrs_from_uri(info["id"]))

        self.section = info["type"].split("/")[-1].lower()
        self.piggytargets = []
        if group := self.info.get("group"):
            self.info["group"] = group.lower()
            self.piggytargets.append(group.lower())
        self.metrics: list = []

    def dumpinfo(self) -> Sequence[tuple]:
        # TODO: Hmmm, should the variable-length tuples actually be lists?
        lines: list[tuple[str | int, ...]] = [("Resource",), (json.dumps(self.info),)]
        if self.metrics:
            lines += [("metrics following", len(self.metrics))]
            lines += [(json.dumps(m),) for m in self.metrics]
        return lines

    def _filter_tags(self, tags: dict[str, str], tag_key_pattern: TagsOption) -> dict[str, str]:
        if tag_key_pattern == TagsImportPatternOption.import_all:
            return tags
        if tag_key_pattern == TagsImportPatternOption.ignore_all:
            return {}
        return {key: value for key, value in tags.items() if re.search(tag_key_pattern, key)}


def filter_keys(mapping: Mapping, keys: Iterable[str]) -> Mapping:
    items = ((k, mapping.get(k)) for k in keys)
    return {k: v for k, v in items if v is not None}


def get_params_from_azure_id(
    resource_id: str, resource_types: Sequence[str] | None = None
) -> Sequence[str]:
    values = resource_id.lower().split("/")
    type_strings = list(map(str.lower, resource_types)) if resource_types else []
    index_keywords = ["subscriptions", "resourcegroups"] + type_strings
    return [values[values.index(keyword) + 1] for keyword in index_keywords]


async def get_frontend_ip_configs(
    mgmt_client: BaseAsyncApiClient, resource: Mapping
) -> dict[str, dict[str, object]]:
    async def _get_public_ip_addresses(
        mgmt_client: BaseAsyncApiClient, group: str, name: str
    ) -> Mapping[str, Any]:
        return await mgmt_client.get_async(
            f"resourceGroups/{group}/providers/Microsoft.Network/publicIPAddresses/{name}",
            params={"api-version": "2024-05-01"},
        )

    frontend_ip_configs: dict[str, dict[str, object]] = {}

    for ip_config in resource["properties"]["frontendIPConfigurations"]:
        ip_config_data = {
            **filter_keys(ip_config, ("id", "name")),
            **filter_keys(
                ip_config["properties"],
                ("privateIPAllocationMethod", "privateIPAddress"),
            ),
        }
        if "publicIPAddress" in ip_config.get("properties"):
            public_ip_id = ip_config["properties"]["publicIPAddress"]["id"]

            _, group, ip_name = get_params_from_azure_id(
                public_ip_id, resource_types=["publicIPAddresses"]
            )
            public_ip = await _get_public_ip_addresses(mgmt_client, group, ip_name)
            dns_settings = public_ip["properties"].get("dnsSettings")

            public_ip_keys = ("ipAddress", "publicIPAllocationMethod")
            ip_config_data["public_ip_address"] = {
                "dns_fqdn": dns_settings["fqdn"] if dns_settings else "",
                **filter_keys(public_ip, ("name", "location")),
                **filter_keys(public_ip["properties"], public_ip_keys),
            }

        frontend_ip_configs[ip_config_data["id"]] = ip_config_data

    return frontend_ip_configs


def _get_routing_rules(request_routing_rules: Mapping) -> Sequence[Mapping]:
    routing_rule_keys = ("httpListener", "backendAddressPool", "backendHttpSettings")
    return [
        {
            "name": r["name"],
            **filter_keys(r["properties"], routing_rule_keys),
        }
        for r in request_routing_rules
    ]


def _get_http_listeners(http_listeners: Mapping) -> Mapping[str, Mapping]:
    listener_keys = (
        "port",
        "protocol",
        "hostNames",
        "frontendIPConfiguration",
        "frontendPort",
    )
    return {
        l["id"]: {
            "id": l["id"],
            "name": l["name"],
            **filter_keys(l["properties"], listener_keys),
        }
        for l in http_listeners
    }


async def _collect_app_gateways_resources(
    mgmt_client: BaseAsyncApiClient,
    monitored_resources_by_id: Mapping[str, AzureResource],
) -> Sequence[AzureResource]:
    app_gateways = await mgmt_client.get_async(
        "providers/Microsoft.Network/applicationGateways",
        key="value",
        params={"api-version": "2024-05-01"},
    )

    applications_gateways: list[AzureResource] = []
    for app_gateway in app_gateways:
        try:
            resource = monitored_resources_by_id[app_gateway["id"].lower()]
        except KeyError:
            # this can happen because the resource has been filtered out
            # (for example because it is not in the monitored group configured via --explicit-config)
            LOGGER.info(
                "Application gateway not found in monitored resources: %s",
                app_gateway["id"],
            )
            continue

        resource.info["properties"] = {}
        resource.info["properties"]["operational_state"] = app_gateway["properties"][
            "operationalState"
        ]
        resource.info["properties"]["routing_rules"] = _get_routing_rules(
            app_gateway["properties"]["requestRoutingRules"]
        )
        resource.info["properties"]["http_listeners"] = _get_http_listeners(
            app_gateway["properties"]["httpListeners"]
        )

        if (
            waf_config := app_gateway["properties"].get("webApplicationFirewallConfiguration")
        ) is not None:
            resource.info["properties"]["waf_enabled"] = waf_config["enabled"]

        frontend_ports = {
            p["id"]: {"port": p["properties"]["port"]}
            for p in app_gateway["properties"]["frontendPorts"]
        }
        resource.info["properties"]["frontend_ports"] = frontend_ports

        backend_settings = {
            c["id"]: {
                "name": c["name"],
                **filter_keys(c["properties"], ("port", "protocol")),
            }
            for c in app_gateway["properties"]["backendHttpSettingsCollection"]
        }
        resource.info["properties"]["backend_settings"] = backend_settings

        backend_pools = {p["id"]: p for p in app_gateway["properties"]["backendAddressPools"]}
        resource.info["properties"]["backend_address_pools"] = backend_pools

        frontend_ip_configs = await get_frontend_ip_configs(mgmt_client, app_gateway)
        resource.info["properties"]["frontend_api_configs"] = frontend_ip_configs

        applications_gateways.append(resource)

    return applications_gateways


# TODO: test
async def process_app_gateways(
    mgmt_client: BaseAsyncApiClient,
    monitored_resources_by_id: Mapping[str, AzureResource],
) -> Sequence[AzureSection]:
    applications_gateways = await _collect_app_gateways_resources(
        mgmt_client, monitored_resources_by_id
    )

    sections = []
    for resource in applications_gateways:
        section = AzureSection(resource.section, resource.piggytargets)
        section.add(resource.dumpinfo())
        sections.append(section)

    return sections


async def _collect_load_balancers_resources(
    mgmt_client: BaseAsyncApiClient,
    monitored_resources_by_id: Mapping[str, AzureResource],
) -> Sequence[AzureResource]:
    load_balancers_response = await mgmt_client.get_async(
        "providers/Microsoft.Network/loadBalancers",
        key="value",
        params={"api-version": "2024-05-01"},
    )

    load_balancers_resources: list[AzureResource] = []
    for load_balancer in load_balancers_response:
        try:
            resource = monitored_resources_by_id[load_balancer["id"].lower()]
        except KeyError:
            # this can happen because the resource has been filtered out
            # (for example because it is not in the monitored group configured via --explicit-config)
            LOGGER.info("Load balancer not found in monitored resources: %s", load_balancer["id"])
            continue

        try:
            frontend_ip_configs, inbound_nat_rules, backend_pools = await asyncio.gather(
                get_frontend_ip_configs(mgmt_client, load_balancer),
                get_inbound_nat_rules(mgmt_client, load_balancer),
                get_backend_address_pools(mgmt_client, load_balancer),
            )
        except Exception:
            raise ApiErrorMissingData(
                f"Failed to collect data for load balancer: {load_balancer['id']}"
            )

        resource.info["properties"] = {}
        resource.info["properties"]["frontend_ip_configs"] = frontend_ip_configs
        resource.info["properties"]["inbound_nat_rules"] = inbound_nat_rules
        resource.info["properties"]["backend_pools"] = {p["id"]: p for p in backend_pools}

        outbound_rule_keys = ("protocol", "idleTimeoutInMinutes", "backendAddressPool")
        outbound_rules = [
            {"name": r["name"], **filter_keys(r["properties"], outbound_rule_keys)}
            for r in load_balancer["properties"].get("outboundRules", [])
        ]
        resource.info["properties"]["outbound_rules"] = outbound_rules

        load_balancers_resources.append(resource)

    return load_balancers_resources


# TODO: test
async def process_load_balancers(
    mgmt_client: BaseAsyncApiClient,
    monitored_resources_by_id: Mapping[str, AzureResource],
) -> Sequence[AzureSection]:
    load_balancers = await _collect_load_balancers_resources(mgmt_client, monitored_resources_by_id)

    sections = []
    for resource in load_balancers:
        section = AzureSection(resource.section, resource.piggytargets)
        section.add(resource.dumpinfo())
        sections.append(section)

    return sections


async def _get_standard_network_interface_config(
    mgmt_client: BaseAsyncApiClient, nic_id: str
) -> Mapping[str, Mapping]:
    _, group, nic_name, ip_conf_name = get_params_from_azure_id(
        nic_id, resource_types=["networkInterfaces", "ipConfigurations"]
    )
    return await mgmt_client.get_async(
        f"resourceGroups/{group}/providers/Microsoft.Network/networkInterfaces/{nic_name}/ipConfigurations/{ip_conf_name}",
        params={"api-version": "2022-01-01"},
    )


async def _get_vmss_network_interface_config(
    mgmt_client: BaseAsyncApiClient, nic_id: str
) -> Mapping[str, Mapping]:
    async def _nic_vmss_ip_conf_view(group, vmss, virtual_machine_index, nic_name, ip_conf_name):
        return await mgmt_client.get_async(
            f"resourceGroups/{group}/providers/microsoft.Compute/virtualMachineScaleSets/"
            f"{vmss}/virtualMachines/{virtual_machine_index}/networkInterfaces/{nic_name}/ipConfigurations/{ip_conf_name}",
            params={"api-version": "2024-07-01"},
        )

    _, group, vmss, vm_index, nic_name, ip_conf_name = get_params_from_azure_id(
        nic_id,
        resource_types=[
            "virtualMachineScaleSets",
            "virtualMachines",
            "networkInterfaces",
            "ipConfigurations",
        ],
    )
    return await _nic_vmss_ip_conf_view(group, vmss, vm_index, nic_name, ip_conf_name)


async def get_network_interface_config(
    mgmt_client: BaseAsyncApiClient, nic_id: str
) -> Mapping[str, Mapping]:
    if "virtualMachineScaleSets" in nic_id:
        return await _get_vmss_network_interface_config(mgmt_client, nic_id)

    return await _get_standard_network_interface_config(mgmt_client, nic_id)


async def get_inbound_nat_rules(
    mgmt_client: BaseAsyncApiClient, load_balancer: Mapping
) -> list[dict[str, object]]:
    nat_rule_keys = ("frontendPort", "backendPort", "frontendIPConfiguration")

    inbound_nat_rules: list[dict[str, object]] = []
    for inbound_nat_rule in load_balancer["properties"]["inboundNatRules"]:
        nat_rule_data = {
            "name": inbound_nat_rule["name"],
            **filter_keys(inbound_nat_rule["properties"], nat_rule_keys),
        }

        if "backendIPConfiguration" in inbound_nat_rule.get("properties"):
            ip_config_id = inbound_nat_rule["properties"]["backendIPConfiguration"]["id"]

            if (
                backend_address_data := await get_backend_address_data(mgmt_client, ip_config_id)
            ) is not None:
                nat_rule_data["backend_ip_config"] = backend_address_data

        inbound_nat_rules.append(nat_rule_data)

    return inbound_nat_rules


async def get_backend_address_data(
    mgmt_client: BaseAsyncApiClient, ip_config_id: str
) -> Mapping[str, object] | None:
    backend_address_keys = ("privateIPAddress", "privateIPAllocationMethod", "primary")
    nic_config = await get_network_interface_config(mgmt_client, ip_config_id)

    if "name" in nic_config and "properties" in nic_config:
        backend_address_data = {
            "name": nic_config["name"],
            **filter_keys(nic_config["properties"], backend_address_keys),
        }
        return backend_address_data
    return None


async def get_backend_address_pools(
    mgmt_client: BaseAsyncApiClient, load_balancer: Mapping
) -> list[dict[str, object]]:
    backend_pools: list[dict[str, object]] = []

    for backend_pool in load_balancer["properties"]["backendAddressPools"]:
        backend_addresses = []
        for backend_address in backend_pool["properties"].get("loadBalancerBackendAddresses", []):
            if "networkInterfaceIPConfiguration" in backend_address.get("properties"):
                ip_config_id = backend_address["properties"]["networkInterfaceIPConfiguration"][
                    "id"
                ]

                if (
                    backend_address_data := await get_backend_address_data(
                        mgmt_client, ip_config_id
                    )
                ) is None:
                    continue
                backend_addresses.append(backend_address_data)

        backend_pools.append(
            {
                "id": backend_pool["id"],
                "name": backend_pool["name"],
                "addresses": backend_addresses,
            }
        )

    return backend_pools


async def get_remote_peerings(
    mgmt_client: BaseAsyncApiClient, resource: dict
) -> Sequence[Mapping[str, object]]:
    # retrieve the current subscription ID from the virtual network gateway ID
    vnet_gateway_subscription, *_ = get_params_from_azure_id(resource["id"])

    peering_keys = ("name", "peeringState", "peeringSyncLevel")
    vnet_peerings = []
    for vnet_peering in resource["properties"].get("remoteVirtualNetworkPeerings", []):
        vnet_peering_id = vnet_peering["id"]
        peering_subscription, group, providers, vnet_id, vnet_peering_id = get_params_from_azure_id(
            vnet_peering_id,
            resource_types=[
                "providers",
                "virtualNetworks",
                "virtualNetworkPeerings",
            ],
        )
        # skip vNet peerings that belong to another Azure subscription
        if peering_subscription != vnet_gateway_subscription:
            continue

        peering_view = await mgmt_client.get_async(
            f"resourceGroups/{group}/providers/{providers}/virtualNetworks/{vnet_id}/virtualNetworkPeerings/{vnet_peering_id}",
            params={
                "api-version": "2024-10-01",
            },
        )

        vnet_peering = {
            **filter_keys(peering_view, peering_keys),
            **filter_keys(peering_view["properties"], peering_keys),
        }
        vnet_peerings.append(vnet_peering)

    return vnet_peerings


async def get_vnet_gw_health(
    mgmt_client: BaseAsyncApiClient, resource: Mapping
) -> Mapping[str, object]:
    health_keys = ("availabilityState", "summary", "reasonType", "occuredTime")

    _, group, providers, vnet_gw = get_params_from_azure_id(
        resource["id"], resource_types=["providers", "virtualNetworkGateways"]
    )

    health_view = await mgmt_client.get_async(
        f"resourceGroups/{group}/providers/{providers}/virtualNetworkGateways/{vnet_gw}/providers/Microsoft.ResourceHealth/availabilityStatuses/current",
        params={
            "api-version": "2025-04-01",
        },
    )

    return filter_keys(health_view["properties"], health_keys)


async def process_virtual_net_gw(
    api_client: BaseAsyncApiClient, resource: AzureResource
) -> AzureSection:
    gw_keys = (
        "bgpSettings",
        "disableIPSecReplayProtection",
        "gatewayType",
        "vpnType",
        "activeActive",
        "enableBgp",
    )

    gw_view = await api_client.get_async(
        f"resourceGroups/{resource.info['group']}/providers/Microsoft.Network/virtualNetworkGateways/{resource.info['name']}",
        params={
            "api-version": "2024-05-01",
        },
    )

    resource.info["specific_info"] = filter_keys(gw_view["properties"], gw_keys)

    vnet_peerings, vnet_health = await asyncio.gather(
        get_remote_peerings(api_client, gw_view),
        get_vnet_gw_health(api_client, gw_view),
    )
    resource.info["properties"] = {
        "remote_vnet_peerings": vnet_peerings,
        "health": vnet_health,
    }

    section = AzureSection(
        FetchedResource.virtual_network_gateways.section,
        resource.piggytargets,
    )
    section.add(resource.dumpinfo())

    return section


class MetricCache(DataCache):
    def __init__(
        self,
        *,
        metric_definition: tuple[str, str, str],
        resource_type: str,
        region: str,
        cache_id: str,
        ref_time: datetime.datetime,
        debug: bool = False,
    ) -> None:
        self.metric_definition = metric_definition
        metric_names = metric_definition[0]
        super().__init__(
            self.get_cache_path(cache_id, resource_type, region),
            metric_names,
            debug=debug,
        )
        self.remaining_reads = None
        self.timedelta = {
            "PT1M": datetime.timedelta(minutes=1),
            "PT5M": datetime.timedelta(minutes=5),
            "PT1H": datetime.timedelta(hours=1),
        }[metric_definition[1]]
        # For 1-min metrics, the start time should be at least 4 minutes before because of the
        # ingestion time of Azure metrics (we had to change from 3 minutes to 5 minutes because we
        # were missing some metrics with 3 minutes).
        # More info on Azure Monitor Ingestion time:
        # https://docs.microsoft.com/en-us/azure/azure-monitor/logs/data-ingestion-time
        self.start_time = (ref_time - 5 * self.timedelta).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.end_time = ref_time.strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def get_cache_path(cache_id: str, resource_type: str, region: str) -> Path:
        valid_chars = f"-_.() {string.ascii_letters}{string.digits}"
        subdir = "".join(c if c in valid_chars else "_" for c in f"{region}_{resource_type}")
        return AZURE_CACHE_FILE_PATH / cache_id / subdir

    @property
    def cache_interval(self) -> int:
        return self.timedelta.seconds

    def get_validity_from_args(self, *args: Any) -> bool:
        return True

    @staticmethod
    def _get_available_metrics_from_exception(
        desired_names: str, api_error: ApiError, resource_type: str
    ) -> str | None:
        match = re.match(
            r"Failed to find metric configuration for provider.*Valid metrics: ([\w,]*)",
            api_error.args[0],
        )
        if not match:
            raise api_error

        available_names = match.groups()[0]
        retry_names = set(desired_names.split(",")) & set(available_names.split(","))
        if not retry_names:
            LOGGER.debug("None of the expected metrics are available for %s", resource_type)
            return None

        return ",".join(sorted(retry_names))

    async def _get_metrics(self, api_client, region, resource_ids, params):
        regional_url = api_client.build_regional_url(region, "/metrics:getBatch")

        async def _query_metrics(specific_params):
            return await api_client.request_async(
                "POST",
                full_uri=regional_url,
                body={"resourceids": resource_ids},
                params=specific_params,
                key="values",
            )

        params["api-version"] = "2023-10-01"
        try:
            return await _query_metrics(params)
        except ApiError as exc:
            if retry_names := self._get_available_metrics_from_exception(
                params["metricnames"], exc, params["metricnamespace"]
            ):
                params["metricnames"] = retry_names
                return await _query_metrics(params)
            return []

    async def get_live_data(self, *args: Any) -> Any:
        mgmt_client: BaseAsyncApiClient = args[0]
        region: str = args[1]
        resource_ids: Sequence[str] = args[2]
        resource_type: str = args[3]
        err: IssueCollector = args[4]

        metric_names, interval, aggregation = self.metric_definition

        params = {
            "starttime": self.start_time,
            "endtime": self.end_time,
            "interval": interval,
            "metricnames": metric_names,
            "metricnamespace": resource_type,
            "aggregation": aggregation,
        }

        raw_metrics = []
        for chunk in _chunks(resource_ids):
            raw_metrics += await self._get_metrics(mgmt_client, region, chunk, params)

        metrics = defaultdict(list)

        for resource_metrics in raw_metrics:
            resource_id = resource_metrics["resourceid"]

            for raw_metric in resource_metrics["value"]:
                parsed_metric = create_metric_dict(raw_metric, aggregation, interval)
                if parsed_metric is not None:
                    metrics[resource_id].append(parsed_metric)
                else:
                    metric_name = raw_metric["name"]["value"]
                    if metric_name in OPTIONAL_METRICS.get(resource_type, []):
                        continue

                    msg = f"metric not found: {metric_name} ({aggregation})"
                    err.add("info", resource_id, msg)
                    LOGGER.info(msg)

        return metrics

    async def get_metrics(self, *args, **kwargs):
        use_cache = kwargs.pop("use_cache", True)
        if use_cache and self.get_validity_from_args(*args) and self._cache_is_valid():
            try:
                return self.get_cached_data()
            except (OSError, ValueError) as exc:
                logging.info("Getting live data (failed to read from cache: %s).", exc)
                if self.debug:
                    raise

        live_data = await self.get_live_data(*args)
        try:
            self._write_to_cache(live_data)
        except (OSError, TypeError) as exc:
            logging.info("Failed to write data to cache file: %s", exc)
            if self.debug:
                raise
        return live_data


async def process_users(graph_api_client: BaseAsyncApiClient) -> AzureSection:
    users_count = await graph_api_client.request_async(
        "GET",
        uri_end="users",
        params={"$top": 1, "$count": "true"},
        key="@odata.count",
        custom_headers={"ConsistencyLevel": "eventual"},
    )
    section = AzureSection("ad")
    section.add(["users_count", users_count])

    return section


async def process_organization(graph_api_client: BaseAsyncApiClient) -> AzureSection:
    orgs = await graph_api_client.get_async("organization", key="value")
    section = AzureSection("ad")
    section.add(["ad_connect", json.dumps(orgs, sort_keys=True)])

    return section


async def process_app_registrations(graph_api_client: BaseAsyncApiClient) -> AzureSection:
    apps = await graph_api_client.get_async(
        "applications", key="value", next_page_key="@odata.nextLink"
    )

    key_subset = {"id", "appId", "displayName", "passwordCredentials"}
    apps = [{k: app[k] for k in key_subset} for app in apps if app["passwordCredentials"]]

    section = AzureSection("app_registration", separator=0)
    for app_reg in apps:
        section.add([json.dumps(app_reg, sort_keys=True)])

    return section


async def process_metrics(
    mgmt_client: BaseAsyncApiClient, resources: Sequence[AzureResource], args: Args
) -> None:
    errors = await _gather_metrics(mgmt_client, resources, args)

    if not errors:
        return

    agent_info_section = AzureSection("agent_info")
    agent_info_section.add(errors.dumpinfo())
    agent_info_section.write()


# TODO: to test
async def _gather_metrics(
    mgmt_client: BaseAsyncApiClient, all_resources: Sequence[AzureResource], args: Args
) -> IssueCollector:
    """
    Gather metrics for all resources. Metrics are collected per resource type, region, metric
    aggregation and time resolution. One query collects metrics of all resources of a given type.
    """
    resource_dict = {resource.info["id"]: resource for resource in all_resources}
    err = IssueCollector()

    grouped_resource_ids = defaultdict(list)
    for resource in all_resources:
        grouped_resource_ids[(resource.info["type"], resource.info["location"])].append(
            resource.info["id"]
        )

    tasks = set()
    for group, resource_ids in grouped_resource_ids.items():
        resource_type, resource_region = group

        if resource_type == FetchedResource.virtual_machines.type:
            if args.piggyback_vms != "self":
                continue

        metric_definitions = ALL_METRICS.get(resource_type, [])
        for metric_definition in metric_definitions:
            cache = MetricCache(
                metric_definition=metric_definition,
                resource_type=resource_type,
                region=resource_region,
                cache_id=args.cache_id,
                ref_time=NOW,
                debug=args.debug,
            )

            tasks.add(
                cache.get_metrics(
                    mgmt_client,
                    resource_region,
                    resource_ids,
                    resource_type,
                    err,
                    use_cache=cache.cache_interval > 60,
                )
            )

    results = await asyncio.gather(*tasks, return_exceptions=True)
    for result in results:
        if isinstance(result, BaseException):
            if args.debug:
                raise result
            err.add("exception", "metric collection", str(result))
            LOGGER.exception(result)
            continue

        for resource_id, metrics in result.items():
            if (resource_metric := resource_dict.get(resource_id)) is not None:
                resource_metric.metrics += metrics
            else:
                LOGGER.info(
                    "Resource %s found in metrics cache no longer monitored",
                    resource_id,
                )

    return err


def get_vm_labels_section(vm: AzureResource, group_labels: GroupLabels) -> LabelsSection:
    group_name = vm.info["group"]
    vm_labels = dict(vm.tags)

    for tag_name, tag_value in group_labels[group_name].items():
        if tag_name not in vm.tags:
            vm_labels[tag_name] = tag_value

    labels_section = LabelsSection(vm.info["name"])
    labels_section.add((json.dumps({"group_name": vm.info["group"], "vm_instance": True}),))
    labels_section.add((json.dumps(vm_labels),))
    return labels_section


async def get_group_labels(
    mgmt_client: BaseAsyncApiClient,
    monitored_groups: Sequence[str],
    tag_key_pattern: TagsOption,
) -> GroupLabels:
    group_labels: dict[str, dict[str, str]] = {}

    resource_groups = await mgmt_client.get_async(
        "resourcegroups", key="value", params={"api-version": "2019-05-01"}
    )

    for group in resource_groups:
        name = group["name"].lower()

        if tag_key_pattern == TagsImportPatternOption.ignore_all:
            tags = {}
        else:
            tags = group.get("tags", {})
            if tag_key_pattern != TagsImportPatternOption.import_all:
                tags = {
                    key: value for key, value in tags.items() if re.search(tag_key_pattern, key)
                }

        if name in monitored_groups:
            group_labels[name] = tags

    return group_labels


def write_group_info(
    monitored_groups: Sequence[str],
    monitored_resources: Sequence[AzureResource],
    group_labels: GroupLabels,
) -> None:
    for group_name, tags in group_labels.items():
        labels_section = LabelsSection(group_name)
        labels_section.add((json.dumps({"group_name": group_name}),))
        labels_section.add((json.dumps(tags),))
        labels_section.write()

    section = AzureSection("agent_info")
    section.add(("monitored-groups", json.dumps(monitored_groups)))
    section.add(
        (
            "monitored-resources",
            json.dumps([r.info["name"] for r in monitored_resources]),
        )
    )
    section.write()
    # write empty agent_info section for all groups, otherwise
    # the service will only be discovered if something goes wrong
    AzureSection("agent_info", monitored_groups).write()


def write_remaining_reads(rate_limit: int | None) -> None:
    agent_info_section = AzureSection("agent_info")
    agent_info_section.add(("remaining-reads", rate_limit))
    agent_info_section.write()


def write_to_agent_info_section(message: str, component: str, status: int) -> None:
    value = json.dumps((status, f"{component}: {message}"))
    section = AzureSection("agent_info")
    section.add(("agent-bailout", value))
    section.write()


def write_exception_to_agent_info_section(exception, component):
    LOGGER.warning("Writing exception for component %s:\n %s", component, exception)

    # those exceptions are quite noisy. try to make them more concise:
    msg = str(exception).split("Trace ID", 1)[0]
    msg = msg.split(":", 2)[-1].strip(" ,")

    if "does not have authorization to perform action" in msg:
        msg += "HINT: Make sure you have a proper role asigned to your client!"

    write_to_agent_info_section(msg, component, 2)


async def main_graph_client(args: Args, monitored_services: set[str]) -> None:
    tasks_map = {
        "users_count": process_users,
        "ad_connect": process_organization,
        "app_registrations": process_app_registrations,
    }
    if not any(service in monitored_services for service in tasks_map):
        return

    def _handle_graph_client_exception(exc: Exception, debug: bool) -> None:
        if isinstance(exc, ApiLoginFailed | ApiErrorAuthorizationRequestDenied):
            # We are not raising the exception in debug mode.
            # Having no permissions for the graph API is a legit configuration
            write_exception_to_agent_info_section(exc, "Graph client (async)")
        elif debug:
            raise exc
        else:
            write_exception_to_agent_info_section(exc, "Graph client (async)")

    try:
        async with BaseAsyncApiClient(
            get_graph_authority_urls(args.authority),
            deserialize_http_proxy_config(args.proxy),
            tenant=args.tenant,
            client=args.client,
            secret=args.secret,
        ) as graph_client:
            tasks = {
                task_call(graph_client)
                for service, task_call in tasks_map.items()
                if service in monitored_services
            }

            for coroutine in asyncio.as_completed(tasks):
                try:
                    section = await coroutine
                    section.write()
                except Exception as exc:
                    _handle_graph_client_exception(exc, args.debug)

    except Exception as exc:
        _handle_graph_client_exception(exc, args.debug)


def _process_query_id(columns, rows, common_metadata):
    processed_query = []
    column_names = [c["name"] for c in columns]
    for index, row in enumerate(rows):
        processed_row = common_metadata.copy()
        # each entry should have a different name because the agent expects this value to be
        # different for each resource but in case of a query the "name" is the id of the
        # query so we replace it with a different name for each query result
        processed_row["name"] = f"{processed_row['name']}-{index}"
        processed_row["properties"] = dict(zip(column_names, row))
        processed_query.append(processed_row)
    return processed_query


async def _collect_usage_data(mgmt_client: BaseAsyncApiClient) -> Sequence[dict[str, Any]]:
    yesterday = (NOW - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    body = {
        "type": "ActualCost",
        "dataSet": {
            "granularity": "None",
            "aggregation": {
                "totalCost": {"name": "Cost", "function": "Sum"},
                "totalCostUSD": {"name": "CostUSD", "function": "Sum"},
            },
            "grouping": [
                {"type": "Dimension", "name": "ResourceType"},
                {"type": "Dimension", "name": "ResourceGroupName"},
            ],
            "include": ["Tags"],
        },
        "timeframe": "Custom",
        "timePeriod": {
            "from": f"{yesterday}T00:00:00+00:00",
            "to": f"{yesterday}T23:59:59+00:00",
        },
    }
    json_data = await mgmt_client.request_async(
        "POST",
        "/providers/Microsoft.CostManagement/query",
        body=body,
        params={"api-version": "2025-03-01"},
    )

    # since data is nested in "properties" and "columns" we need to
    # paginate here in a specific way

    data = mgmt_client.lookup_json_data(json_data, "properties")
    columns = mgmt_client.lookup_json_data(data, "columns")
    rows = mgmt_client.lookup_json_data(data, "rows")

    while next_link := data.get("nextLink"):
        new_json_data = await mgmt_client.request_async("POST", full_uri=next_link, body=body)
        data = mgmt_client.lookup_json_data(new_json_data, "properties")
        rows += mgmt_client.lookup_json_data(data, "rows")

    common_metadata = {k: v for k, v in json_data.items() if k != "properties"}
    processed_query = _process_query_id(columns, rows, common_metadata)
    return processed_query


async def get_usage_data(client: BaseAsyncApiClient) -> Sequence[dict[str, Any]]:
    NO_CONSUMPTION_API = (
        "offer MS-AZR-0145P",
        "offer MS-AZR-0146P",
        "offer MS-AZR-159P",
        "offer MS-AZR-0036P",
        "offer MS-AZR-0143P",
        "offer MS-AZR-0015P",
        "offer MS-AZR-0144P",
        "Customer does not have the privilege to see the cost",
    )

    LOGGER.debug("get usage details")

    try:
        usage_data = await _collect_usage_data(client)
    except ApiError as exc:
        if any(s in exc.args[0] for s in NO_CONSUMPTION_API):
            raise NoConsumptionAPIError
        raise

    # TODO: usage details are related to yesterday! Can we cache them?
    LOGGER.debug("yesterdays usage details: %d", len(usage_data))
    return usage_data


def write_usage_section(
    usage_data: Sequence[dict[str, Any]],
    monitored_groups: list[str],
    tag_key_pattern: TagsOption,
) -> None:
    if not usage_data:
        AzureSection("usagedetails", monitored_groups + [""]).write(write_empty=True)

    for usage in usage_data:
        # fill "resource" mandatory information
        usage["type"] = "Microsoft.Consumption/usageDetails"
        usage["group"] = usage["properties"]["ResourceGroupName"]

        usage_resource = AzureResource(usage, tag_key_pattern)
        piggytargets = [g for g in usage_resource.piggytargets if g in monitored_groups] + [""]

        section = AzureSection(usage_resource.section, piggytargets)
        section.add(usage_resource.dumpinfo())
        section.write()


async def process_usage_details(
    mgmt_client: BaseAsyncApiClient, monitored_groups: list[str], args: Args
) -> None:
    try:
        usage_section = await get_usage_data(mgmt_client)
        if not usage_section:
            write_to_agent_info_section(
                "Azure API did not return any usage details", "Usage client", 0
            )
            return

        write_usage_section(usage_section, monitored_groups, args.tag_key_pattern)

    except NoConsumptionAPIError:
        LOGGER.debug("Azure offer doesn't support querying the cost API")
        return

    except Exception as exc:
        if args.debug:
            raise
        write_exception_to_agent_info_section(exc, "Usage client")
        write_usage_section([], monitored_groups, args.tag_key_pattern)


async def process_resource_health(
    mgmt_client: BaseAsyncApiClient,
    monitored_resources_by_id: Mapping[str, AzureResource],
    monitored_groups: Sequence[str],
    debug: bool,
) -> Sequence[AzureSection]:
    multi_response = await asyncio.gather(
        *(
            mgmt_client.get_async(
                f"/resourceGroups/{resource_group}/providers/Microsoft.ResourceHealth/availabilityStatuses",
                params={
                    "api-version": "2025-05-01",
                    "$top": "1000",  # retrieves up to 1000 (still not clear what) per request
                },
                key="value",
            )
            for resource_group in monitored_groups
        ),
        return_exceptions=True,
    )

    health_values: list[ResourceHealth] = []
    for response in multi_response:
        if isinstance(response, BaseException):
            if debug:
                raise response
            write_exception_to_agent_info_section(response, "Resource Health client")
            continue
        health_values.extend(response)

    return _get_resource_health_sections(health_values, monitored_resources_by_id)


# TODO: test
async def process_virtual_machines(
    api_client: BaseAsyncApiClient,
    args: Args,
    group_labels: GroupLabels,
    monitored_resources_by_id: Mapping[str, AzureResource],
) -> Sequence[AzureSection]:
    response = await api_client.get_async(
        "providers/Microsoft.Compute/virtualMachines",
        params={
            "api-version": "2024-11-01",
            "statusOnly": "true",  # fetching only run time status
        },
        key="value",
    )

    virtual_machines: list[AzureResource] = []
    for vm in response:
        try:
            resource = monitored_resources_by_id[vm["id"].lower()]
        except KeyError:
            # this can happen because the resource has been filtered out
            # (for example because it is not in the monitored group configured via --explicit-config)
            LOGGER.info("Virtual machine not found in monitored resources: %s", vm["id"])
            continue

        try:
            statuses = vm.pop("properties")["instanceView"]["statuses"]
        except KeyError:
            raise ApiErrorMissingData("Virtual machine instance's statuses must be present")

        resource.info["specific_info"] = {"statuses": statuses}
        virtual_machines.append(resource)

    sections = []
    for resource in virtual_machines:
        if args.piggyback_vms == "self":
            labels_section = get_vm_labels_section(resource, group_labels)
            labels_section.write()

        section = AzureSection(
            FetchedResource.virtual_machines.section,
            [resource.info["name"] if args.piggyback_vms == "self" else resource.info["group"]],
        )
        section.add(resource.dumpinfo())
        sections.append(section)

    return sections


# TODO: test
async def process_vault(
    api_client: BaseAsyncApiClient,
    resource: AzureResource,
) -> AzureSection:
    vault_properties = (
        "friendlyName",
        "backupManagementType",
        "protectedItemType",
        "lastBackupTime",
        "lastBackupStatus",
        "protectionState",
        "protectionStatus",
        "policyName",
        "isArchiveEnabled",
    )

    response = await api_client.get_async(
        f"resourceGroups/{resource.info['group']}/providers/Microsoft.RecoveryServices/vaults/{resource.info['name']}/backupProtectedItems",
        params={
            "api-version": "2025-02-01",
        },
        key="value",
    )

    try:
        properties = filter_keys(response[0]["properties"], vault_properties)
    except KeyError:
        write_exception_to_agent_info_section(
            ApiErrorMissingData("Vault properties must be present"), "Vaults"
        )
        raise ApiErrorMissingData("Vault properties must be present")

    resource.info["properties"] = {}
    resource.info["properties"]["backup_containers"] = [properties]

    section = AzureSection(
        FetchedResource.vaults.section,
        resource.piggytargets,
    )
    section.add(resource.dumpinfo())

    return section


class ResourceHealth(TypedDict, total=False):
    id: Required[str]
    properties: Required[Mapping[str, str]]


def _get_resource_health_sections(
    resource_health_view: Sequence[ResourceHealth],
    resources_by_id: Mapping[str, AzureResource],
) -> Sequence[AzureSection]:
    health_section: defaultdict[str, list[str]] = defaultdict(list)

    for health in resource_health_view:
        health_id = health["id"]
        _, group = get_params_from_azure_id(health_id)
        resource_id = "/".join(health_id.split("/")[:-4])

        try:
            resource = resources_by_id[resource_id.lower()]
        except KeyError:
            continue

        health_data = {
            "id": health_id,
            "name": "/".join(health_id.split("/")[-6:-4]),
            **filter_keys(
                health["properties"],
                ("availabilityState", "summary", "reasonType", "occuredTime"),
            ),
            "tags": resource.tags,
        }

        health_section[group].append(json.dumps(health_data))

    sections = []
    for group, values in health_section.items():
        section = AzureSection("resource_health", [group.lower()])
        for value in values:
            section.add([value])
        sections.append(section)

    return sections


async def _test_connection(args: Args) -> int:
    """We test the connection only via the Management API client, not via the Graph API client.
    The Graph API client is used for three specific services, which are disabled in the default
    setup when configured via the UI.
    The Management API client is used for all other services, so we assume here that this is the
    connection that's essential for the vast majority of setups."""

    try:
        async with BaseAsyncApiClient(
            get_mgmt_authority_urls(args.authority, ""),
            deserialize_http_proxy_config(args.proxy),
            tenant=args.tenant,
            client=args.client,
            secret=args.secret,
        ):
            # we just need to authenticate
            ...
    except (ApiLoginFailed, ValueError) as exc:
        error_msg = f"Connection failed with: {exc}\n"
        sys.stdout.write(error_msg)
        return 2
    except requests.exceptions.ProxyError as exc:
        error_msg = f"Connection failed due to a proxy error: {exc}\n"
        sys.stdout.write(error_msg)
        return 2
    return 0


def get_bulk_tasks(
    mgmt_client: BaseAsyncApiClient,
    args: Args,
    group_labels: GroupLabels,
    monitored_services: set[str],
    monitored_resources_by_id: Mapping[str, AzureResource],
) -> Iterator[asyncio.Task]:
    if FetchedResource.virtual_machines.type in monitored_services:
        yield asyncio.create_task(
            process_virtual_machines(mgmt_client, args, group_labels, monitored_resources_by_id)
        )
    if FetchedResource.app_gateways.type in monitored_services:
        yield asyncio.create_task(process_app_gateways(mgmt_client, monitored_resources_by_id))
    if FetchedResource.load_balancers.type in monitored_services:
        yield asyncio.create_task(process_load_balancers(mgmt_client, monitored_resources_by_id))


# TODO: test
async def process_single_resources(
    mgmt_client: BaseAsyncApiClient,
    args: Args,
    monitored_resources_by_id: Mapping[str, AzureResource],
) -> Sequence[Section]:
    sections = []
    tasks = set()
    for _resource_id, resource in monitored_resources_by_id.items():
        resource_type = resource.info["type"]
        if resource_type in BULK_QUERIED_RESOURCES:
            continue

        if resource_type == FetchedResource.vaults.type:
            tasks.add(process_vault(mgmt_client, resource))
        elif resource_type == FetchedResource.virtual_network_gateways.type:
            tasks.add(process_virtual_net_gw(mgmt_client, resource))
        else:
            # simple sections without further processing
            if resource_type in SUPPORTED_FLEXIBLE_DATABASE_SERVER_RESOURCE_TYPES:
                resource.section = "servers"  # use the same section as for single servers

            section = AzureSection(resource.section, resource.piggytargets)
            section.add(resource.dumpinfo())
            sections.append(section)

    results = await asyncio.gather(*tasks, return_exceptions=True)
    for section_async in results:
        if isinstance(section_async, BaseException):
            if args.debug:
                raise section_async
            write_exception_to_agent_info_section(section_async, "Process single resources (async)")
            continue

        sections.append(section_async)

    return sections


async def process_resources(
    mgmt_client: BaseAsyncApiClient,
    args: Args,
    group_labels: GroupLabels,
    selected_resources: Sequence[AzureResource],
    monitored_services: set[str],
    monitored_groups: Sequence[str],
) -> None:
    monitored_resources_by_id = {
        r.info["id"].lower(): r for r in selected_resources if r.info["type"] in monitored_services
    }

    tasks = {
        process_resource_health(
            mgmt_client, monitored_resources_by_id, monitored_groups, args.debug
        ),
        *get_bulk_tasks(
            mgmt_client,
            args,
            group_labels,
            monitored_services,
            monitored_resources_by_id,
        ),
        process_single_resources(mgmt_client, args, monitored_resources_by_id),
    }

    for coroutine in asyncio.as_completed(tasks):
        try:
            for section in await coroutine:
                section.write()
        except Exception as e:
            if args.debug:
                raise
            write_exception_to_agent_info_section(e, "Management client (async)")


async def _collect_resources(
    mgmt_client: BaseAsyncApiClient, args: Args, selector: Selector
) -> tuple[Sequence[AzureResource], list[str]]:
    resources = await mgmt_client.get_async(
        "resources", key="value", params={"api-version": "2019-05-01"}
    )

    all_resources = (AzureResource(r, args.tag_key_pattern) for r in resources)

    # Selected resources are all the resources that match the selector.
    # They are NOT the "monitored resources", which also depend on the *services* selected via command line call.
    # Here, we need all these resources to be able to create the `monitored_groups` sections.
    # -> I don't know if this is actually intended (we are populating the agent information `monitored-resources`
    #    with resources not really monitored), but the agent behaved like this before.
    selected_resources = [r for r in all_resources if selector.do_monitor(r)]
    monitored_groups = sorted({r.info["group"] for r in selected_resources})

    return selected_resources, monitored_groups


async def main_subscription(
    args: Args, selector: Selector, subscription: str, monitored_services: set[str]
) -> None:
    try:
        async with BaseAsyncApiClient(
            get_mgmt_authority_urls(args.authority, subscription),
            deserialize_http_proxy_config(args.proxy),
            tenant=args.tenant,
            client=args.client,
            secret=args.secret,
        ) as mgmt_client:
            selected_resources, monitored_groups = await _collect_resources(
                mgmt_client, args, selector
            )

            group_labels = await get_group_labels(
                mgmt_client, monitored_groups, args.tag_key_pattern
            )
            write_group_info(monitored_groups, selected_resources, group_labels)

            await process_metrics(mgmt_client, selected_resources, args)

            tasks = {
                process_usage_details(mgmt_client, monitored_groups, args)
                if "usage_details" in monitored_services
                else None,
                process_resources(
                    mgmt_client,
                    args,
                    group_labels,
                    selected_resources,
                    monitored_services,
                    monitored_groups,
                ),
            }
            tasks.discard(None)
            await asyncio.gather(*tasks)  # type: ignore[arg-type]

            write_remaining_reads(mgmt_client.ratelimit)

    except Exception as exc:
        if args.debug:
            raise
        write_exception_to_agent_info_section(exc, "Management client")


async def _get_subscriptions(args: Args) -> set[str]:
    if args.subscriptions:
        LOGGER.info("Using subscriptions from command line: %s", args.subscriptions)
        return set(args.subscriptions)

    if args.all_subscriptions:
        async with BaseAsyncApiClient(
            get_mgmt_authority_urls(args.authority, ""),
            deserialize_http_proxy_config(args.proxy),
            args.tenant,
            args.client,
            args.secret,
        ) as api_client:
            response = await api_client.request_async(
                method="GET",
                full_uri="https://management.azure.com/subscriptions",
                params={"api-version": "2022-12-01"},
            )
            subscriptions = {item["subscriptionId"] for item in response.get("value", [])}
            LOGGER.info("Using subscriptions from API: %s", subscriptions)
            return subscriptions

    return set()  # no subscriptions


async def collect_info(args: Args, selector: Selector, subscriptions: set[str]) -> None:
    monitored_services = set(args.services)
    await asyncio.gather(
        main_graph_client(args, monitored_services),
        *{
            main_subscription(args, selector, subscription, monitored_services)
            for subscription in subscriptions
        },
    )


async def main_async(args: Args, selector: Selector) -> int:
    if args.connection_test:
        return await _test_connection(args)

    subscriptions = await _get_subscriptions(args)
    await collect_info(args, selector, subscriptions)
    LOGGER.debug("%s", selector)
    return 0


def _setup_logging(verbose: int) -> None:
    logging.basicConfig(
        level={0: logging.WARN, 1: logging.INFO, 2: logging.DEBUG}.get(verbose, logging.DEBUG)
    )

    if verbose == 2:
        # if verbose >= 3, be verbose (show all messages from other modules)
        # if verbose == 2, be verbose, but silence msrest, urllib3 and requests_oauthlib
        # for the others, keep the logging level as set
        logging.getLogger("msrest").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("requests_oauthlib").setLevel(logging.WARNING)


def _debug_args(args: Args) -> None:
    # debug args
    # secret is required, so no risks in adding it here if not present
    args_dict = vars(args) | {"secret": "****"}
    for key, value in args_dict.items():
        LOGGER.debug("argparse: %s = %r", key, value)


def agent_azure_main(args: Args) -> int:
    selector = Selector(args)
    if args.dump_config:
        sys.stdout.write("Configuration:\n%s\n" % selector)
        return 0

    _setup_logging(args.verbose)
    _debug_args(args)

    return asyncio.run(main_async(args, selector))


def main() -> int:
    return special_agent_main(parse_arguments, agent_azure_main)


if __name__ == "__main__":
    main()
