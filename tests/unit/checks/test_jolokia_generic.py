#!/usr/bin/env python3
# Copyright (C) 2019 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

from collections.abc import Sequence

import pytest

from tests.testlib import Check

from cmk.base.api.agent_based.type_defs import StringTable

from .checktestlib import assertDiscoveryResultsEqual, DiscoveryResult

pytestmark = pytest.mark.checks

info = [
    ["PingFederate-CUK-CDI", "TotalRequests", "64790", "number"],
    ["PingFederate-CUK-CDI", "MaxRequestTime", "2649", "rate"],
]


@pytest.mark.parametrize(
    "check,lines,expected_result",
    [
        ("jolokia_generic", info, [("PingFederate-CUK-CDI TotalRequests", {})]),
        ("jolokia_generic.rate", info, [("PingFederate-CUK-CDI MaxRequestTime", {})]),
    ],
)
def test_jolokia_generic_discovery(
    check: str, lines: StringTable, expected_result: Sequence[object]
) -> None:
    parsed = Check("jolokia_generic").run_parse(lines)

    check_val = Check(check)
    discovered = check_val.run_discovery(parsed)
    assertDiscoveryResultsEqual(
        check_val,
        DiscoveryResult(discovered),
        DiscoveryResult(expected_result),
    )
