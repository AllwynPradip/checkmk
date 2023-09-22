#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.


from cmk.base.check_api import get_bytes_human_readable, LegacyCheckDefinition
from cmk.base.check_legacy_includes.cisco_ucs import DETECT, map_operability
from cmk.base.config import check_info
from cmk.base.plugins.agent_based.agent_based_api.v1 import SNMPTree

# comNET GmbH, Fabian Binder - 2018-05-07

# .1.3.6.1.4.1.9.9.719.1.45.8.1.14 cucsStorageLocalLunType
# .1.3.6.1.4.1.9.9.719.1.45.8.1.13 cucsStorageLocalLunSize
# .1.3.6.1.4.1.9.9.719.1.45.8.1.9  cucsStorageLocalLunOperability

map_luntype = {
    "0": (2, "unspecified"),
    "1": (1, "simple"),
    "2": (0, "mirror"),
    "3": (1, "stripe"),
    "4": (0, "lun"),
    "5": (0, "stripeParity"),
    "6": (0, "stripeDualParity"),
    "7": (0, "mirrorStripe"),
    "8": (0, "stripeParityStripe"),
    "9": (0, "stripeDualParityStripe"),
}


def inventory_cisco_ucs_lun(info):
    return [(None, None)]


def check_cisco_ucs_lun(_no_item, _no_params, info):
    mode, size, status = info[0]
    state, state_readable = map_operability.get(status, (3, "Unknown, status code %s" % status))
    mode_state, mode_state_readable = map_luntype.get(mode, (3, "Unknown, status code %s" % mode))
    # size is returned in MB
    # on migration: check whether to use render.size (MB) or render.bytes (MiB)
    size_readable = get_bytes_human_readable(int(size or "0") * 1024 * 1024)
    yield state, "Status: %s" % state_readable
    yield 0, "Size: %s" % size_readable
    yield mode_state, "Mode: %s" % mode_state_readable


check_info["cisco_ucs_lun"] = LegacyCheckDefinition(
    detect=DETECT,
    fetch=SNMPTree(
        base=".1.3.6.1.4.1.9.9.719.1.45.8.1",
        oids=["14", "13", "9"],
    ),
    service_name="LUN",
    discovery_function=inventory_cisco_ucs_lun,
    check_function=check_cisco_ucs_lun,
)
