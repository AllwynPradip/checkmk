#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

# healthy
# <<<pvecm_status:sep(58)>>>
# Version: 6.2.0
# Config Version: 35
# status Id: 27764
# status Member: Yes
# status Generation: 36032
# Membership state: status-Member
# Nodes: 7
# Expected votes: 7
# Total votes: 7
# Node votes: 1
# Quorum: 4
# Active subsystems: 1
# Flags:
# Ports Bound: 0
# Node name: host-FOO
# Node ID: 5
# Multicast addresses: aaa.bbb.ccc.ddd
# Node addresses: nnn.mmm.ooo.ppp

# with problems:
# <<<pvecm_status:sep(58)>>>
# cman_tool: Cannot open connection to cman, is it running?

# <<<pvecm_status:sep(58)>>>
# Version: 6.2.0
# Config Version: 2
# status Id: 4921
# status Member: Yes
# status Generation: 280
# Membership state: status-Member
# Nodes: 1
# Expected votes: 2
# Total votes: 1
# Node votes: 1
# Quorum: 2 Activity blocked
# Active subsystems: 5
# Flags:
# Ports Bound: 0
# Node name: host-FOO
# Node ID: 1
# Multicast addresses: aaa.bbb.ccc.ddd
# Node addresses: nnn.mmm.ooo.ppp


# mypy: disable-error-code="var-annotated"

from cmk.base.check_api import LegacyCheckDefinition
from cmk.base.config import check_info


def parse_pvecm_status(string_table):
    parsed = {}
    for line in string_table:
        if len(line) < 2:
            continue
        k = line[0].strip().lower()
        if k == "date":
            v = ":".join(line[1:]).strip()
        else:
            v = " ".join(line[1:]).strip()
        parsed.setdefault(k, v)
    return parsed


def inventory_pvecm_status(parsed):
    if parsed:
        return [(None, None)]
    return []


def check_pvecm_status(_no_item, _no_params, parsed):
    if "cman_tool" in parsed and "cannot open connection to cman" in parsed["cman_tool"]:
        yield 2, "Cluster management tool: %s" % parsed["cman_tool"]

    else:
        name = parsed.get("cluster name", parsed.get("quorum provider", "unknown"))

        yield 0, "Name: {}, Nodes: {}".format(name, parsed["nodes"])

        if "activity blocked" in parsed["quorum"]:
            yield 2, "Quorum: %s" % parsed["quorum"]

        if int(parsed["expected votes"]) == int(parsed["total votes"]):
            yield 0, "No faults"
        else:
            yield 2, "Expected votes: {}, Total votes: {}".format(
                parsed["expected votes"],
                parsed["total votes"],
            )


check_info["pvecm_status"] = LegacyCheckDefinition(
    parse_function=parse_pvecm_status,
    service_name="PVE Cluster State",
    discovery_function=inventory_pvecm_status,
    check_function=check_pvecm_status,
)
