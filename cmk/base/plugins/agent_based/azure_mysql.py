#!/usr/bin/env python3
# Copyright (C) 2022 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

from collections.abc import Callable, Mapping
from typing import Any

from .agent_based_api.v1 import register, render
from .agent_based_api.v1.type_defs import CheckResult
from .utils.azure import (
    check_connections,
    check_cpu,
    check_memory,
    check_network,
    check_storage,
    create_check_metrics_function,
    create_discover_by_metrics_function,
    MetricData,
    Section,
)

DB_MYSQL_RESOURCE_NAME = "Microsoft.DBforMySQL/servers"


register.check_plugin(
    name="azure_mysql_memory",
    sections=["azure_servers"],
    service_name="Azure/DB for MySQL %s Memory",
    discovery_function=create_discover_by_metrics_function(
        "average_memory_percent", resource_type=DB_MYSQL_RESOURCE_NAME
    ),
    check_function=check_memory(),
    check_ruleset_name="memory_utilization",
    check_default_parameters={},
)

register.check_plugin(
    name="azure_mysql_cpu",
    sections=["azure_servers"],
    service_name="Azure/DB for MySQL %s CPU",
    discovery_function=create_discover_by_metrics_function(
        "average_cpu_percent", resource_type=DB_MYSQL_RESOURCE_NAME
    ),
    check_function=check_cpu(),
    check_ruleset_name="cpu_utilization_with_item",
    check_default_parameters={"levels": (65.0, 90.0)},
)


def check_replication() -> Callable[[str, Mapping[str, Any], Section], CheckResult]:
    return create_check_metrics_function(
        [
            MetricData(
                "maximum_seconds_behind_master",
                "replication_lag",
                "Replication lag",
                render.timespan,
                upper_levels_param="levels",
            )
        ]
    )


register.check_plugin(
    name="azure_mysql_replication",
    sections=["azure_servers"],
    service_name="Azure/DB for MySQL %s Replication",
    discovery_function=create_discover_by_metrics_function(
        "maximum_seconds_behind_master", resource_type=DB_MYSQL_RESOURCE_NAME
    ),
    check_function=check_replication(),
    check_ruleset_name="replication_lag",
    check_default_parameters={},
)

register.check_plugin(
    name="azure_mysql_connections",
    sections=["azure_servers"],
    service_name="Azure/DB for MySQL %s Connections",
    discovery_function=create_discover_by_metrics_function(
        "average_active_connections",
        "total_connections_failed",
        resource_type=DB_MYSQL_RESOURCE_NAME,
    ),
    check_function=check_connections(),
    check_ruleset_name="database_connections",
    check_default_parameters={},
)

register.check_plugin(
    name="azure_mysql_network",
    sections=["azure_servers"],
    service_name="Azure/DB for MySQL %s Network",
    discovery_function=create_discover_by_metrics_function(
        "total_network_bytes_ingress",
        "total_network_bytes_egress",
        resource_type=DB_MYSQL_RESOURCE_NAME,
    ),
    check_function=check_network(),
    check_ruleset_name="network_io",
    check_default_parameters={},
)

register.check_plugin(
    name="azure_mysql_storage",
    sections=["azure_servers"],
    service_name="Azure/DB for MySQL %s Storage",
    discovery_function=create_discover_by_metrics_function(
        "average_io_consumption_percent",
        "average_serverlog_storage_percent",
        "average_storage_percent",
        resource_type=DB_MYSQL_RESOURCE_NAME,
    ),
    check_function=check_storage(),
    check_ruleset_name="azure_db_storage",
    check_default_parameters={},
)
