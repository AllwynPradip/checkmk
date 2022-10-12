#!/usr/bin/env python3
# Copyright (C) 2019 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

import os
from pathlib import Path

import pytest
from _pytest.monkeypatch import MonkeyPatch

from tests.testlib.base import Scenario

from cmk.utils.type_defs import HostAddress, HostName, result, SourceType

import cmk.core_helpers.cache as file_cache
from cmk.core_helpers import FetcherType
from cmk.core_helpers.agent import AgentRawDataSection
from cmk.core_helpers.host_sections import HostSections

from cmk.base.config import HostConfig
from cmk.base.sources.piggyback import PiggybackSource


@pytest.mark.parametrize("ipaddress", [None, HostAddress("127.0.0.1")])
def test_attribute_defaults(ipaddress: HostAddress, monkeypatch: MonkeyPatch) -> None:
    hostname = HostName("testhost")

    # hocus pocus abracadabra: `exit_code_spec` thou gavest me 🪄✨
    ts = Scenario()
    ts.add_host(hostname)
    ts.apply(monkeypatch)
    host_config = HostConfig.make_host_config(hostname)

    source = PiggybackSource(
        hostname,
        ipaddress,
        source_type=SourceType.HOST,
        fetcher_type=FetcherType.PIGGYBACK,
        id_="piggyback",
        cache_dir=Path(os.devnull),
        simulation_mode=True,
        time_settings=[],
        is_piggyback_host=False,
        file_cache_max_age=file_cache.MaxAge.none(),
    )

    assert not source.summarize(
        result.OK(HostSections[AgentRawDataSection]()),
        exit_spec_cb=host_config.exit_code_spec,
    )
