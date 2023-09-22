#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.


from collections.abc import Mapping, Sequence
from typing import Any

from cmk.base.check_api import passwordstore_get_cmdline
from cmk.base.config import special_agent_info


def agent_couchbase_arguments(
    params: Mapping[str, Any], hostname: str, ipaddress: str | None
) -> Sequence[str | tuple[str, str, str]]:
    args = []

    for bucket in params.get("buckets", []):
        args += ["--buckets", bucket]

    if "timeout" in params:
        args += ["--timeout", params["timeout"]]

    if "port" in params:
        args += ["--port", params["port"]]

    if "authentication" in params:
        user, pwd = params["authentication"]
        args += [
            "--username",
            user,
            "--password",
            passwordstore_get_cmdline("%s", pwd),
        ]

    args.append(ipaddress or hostname)

    return args


special_agent_info["couchbase"] = agent_couchbase_arguments
