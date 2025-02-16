#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

from collections.abc import Mapping

import pytest

from tests.testlib import SpecialAgent

from cmk.base.config import (  # pylint: disable=cmk-module-layer-violation
    SpecialAgentInfoFunctionResult,
)

pytestmark = pytest.mark.checks


@pytest.mark.parametrize(
    "params,expected_args",
    [
        (
            {
                "values": [],
                "devices": [
                    {
                        "slot": 2,
                        "tcp_port": 102,
                        "values": [],
                        "host_name": "device1",
                        "host_address": "host",
                        "rack": 2,
                    },
                    {
                        "slot": 1,
                        "tcp_port": 22,
                        "values": [],
                        "host_name": "device2",
                        "host_address": "hostaddress",
                        "rack": 2,
                    },
                ],
            },
            ["--hostspec", "device1;host;2;2;102", "--hostspec", "device2;hostaddress;2;1;22"],
        ),
    ],
)
def test_siemens_plc_argument_parsing(
    params: Mapping[str, object], expected_args: SpecialAgentInfoFunctionResult
) -> None:
    """Tests if all required arguments are present."""
    agent = SpecialAgent("agent_siemens_plc")
    arguments = agent.argument_func(params, "host", "address")
    assert arguments == expected_args
