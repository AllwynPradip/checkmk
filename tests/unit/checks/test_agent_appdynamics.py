#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2019 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

import pytest
from testlib import SpecialAgent

pytestmark = pytest.mark.checks


@pytest.mark.parametrize('params,expected_args', [
    ({
        'username': 'testID',
        'application': 'appName',
        'password': 'password'
    }, ["-u", "testID", "-p", "password", "address", "appName"]),
    ({
        'username': 'testID',
        'application': 'appName',
        'password': 'password',
        'port': 8090,
        'timeout': 30
    }, ["-u", "testID", "-p", "password", "-P", "8090", "-t", "30", "address", "appName"]),
])
def test_appdynamics_argument_parsing(params, expected_args):
    """Tests if all required arguments are present."""
    agent = SpecialAgent('agent_appdynamics')
    arguments = agent.argument_func(params, "host", "address")
    assert arguments == expected_args
