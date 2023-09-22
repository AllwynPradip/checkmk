#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.


from collections.abc import Mapping, Sequence
from typing import Any

from cmk.base.check_api import passwordstore_get_cmdline
from cmk.base.config import special_agent_info


def agent_netapp_arguments(
    params: Mapping[str, Any], hostname: str, ipaddress: str | None
) -> Sequence[str]:
    return [
        ipaddress or hostname,
        params["username"],
        passwordstore_get_cmdline("%s", params["password"]),
        "--no_counters",
    ] + [element[4:] for element in params["skip_elements"] if element.startswith("ctr_")]


special_agent_info["netapp"] = agent_netapp_arguments
