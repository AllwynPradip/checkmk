#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.


import time

from cmk.base.check_api import LegacyCheckDefinition, saveint
from cmk.base.config import check_info
from cmk.base.plugins.agent_based.agent_based_api.v1 import (
    any_of,
    equals,
    get_rate,
    get_value_store,
    render,
    SNMPTree,
)

# .1.3.6.1.4.1.3375.2.1.2.4.4.3.1.1.  index for ifname
# .1.3.6.1.4.1.3375.2.1.2.4.1.2.1.17. index for ifstate
# .1.3.6.1.4.1.3375.2.1.2.4.4.3.1.3.  index for IN bytes
# .1.3.6.1.4.1.3375.2.1.2.4.4.3.1.5.  index for OUT bytes

f5_bigip_interface_states = {
    1: "down (has no link and is initialized)",
    2: "disabled (has been forced down)",
    3: "uninitialized (has not been initialized)",
    4: "loopback (in loopback mode)",
    5: "unpopulated (interface not physically populated)",
}


def check_f5_bigip_interfaces(item, params, info):
    for port, ifstate, inbytes, outbytes in info:
        if item != port:
            continue

        if int(ifstate) != 0:
            return (
                2,
                "State of {} is {}".format(
                    f5_bigip_interface_states.get(ifstate, "unhandled (%d)" % ifstate), port
                ),
            )

        this_time = int(time.time())
        in_per_sec = get_rate(
            get_value_store(),
            "in",
            this_time,
            saveint(inbytes),
            raise_overflow=True,
        )
        out_per_sec = get_rate(
            get_value_store(),
            "out",
            this_time,
            saveint(outbytes),
            raise_overflow=True,
        )

        inbytes_h = render.iobandwidth(in_per_sec)
        outbytes_h = render.iobandwidth(out_per_sec)
        perf = [
            ("bytes_in", in_per_sec),
            ("bytes_out", out_per_sec),
        ]
        return (0, f"in bytes: {inbytes_h}, out bytes: {outbytes_h}", perf)
    return 3, "Interface not found in SNMP data"


check_info["f5_bigip_interfaces"] = LegacyCheckDefinition(
    detect=any_of(
        equals(".1.3.6.1.2.1.1.2.0", ".1.3.6.1.4.1.3375.2.1.3.4.10"),
        equals(".1.3.6.1.2.1.1.2.0", ".1.3.6.1.4.1.3375.2.1.3.4.20"),
    ),
    fetch=SNMPTree(
        base=".1.3.6.1.4.1.3375.2.1.2.4",
        oids=["4.3.1.1", "1.2.1.17", "4.3.1.3", "4.3.1.5"],
    ),
    service_name="f5 Interface %s",
    discovery_function=lambda info: [(x[0], {"state": 0}) for x in info if int(x[1]) == 0],
    check_function=check_f5_bigip_interfaces,
)
