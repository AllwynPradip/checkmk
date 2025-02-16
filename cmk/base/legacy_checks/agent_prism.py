#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.


# mypy: disable-error-code="list-item"

from collections.abc import Mapping, Sequence
from typing import Any

from cmk.base.check_api import passwordstore_get_cmdline
from cmk.base.config import special_agent_info


def agent_prism_arguments(
    params: Mapping[str, Any], hostname: str, ipaddress: str | None
) -> Sequence[str]:
    return [
        "--server",
        ipaddress or hostname,
        "--username",
        "%s" % params["username"],
        "--password",
        passwordstore_get_cmdline("%s", params["password"]),
        *(["--port", "%s" % params["port"]] if "port" in params else []),
    ]


special_agent_info["prism"] = agent_prism_arguments
