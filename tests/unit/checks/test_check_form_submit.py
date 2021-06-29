#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2019 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

import pytest
from testlib import ActiveCheck

pytestmark = pytest.mark.checks


@pytest.mark.parametrize("params,expected_args", [
    (["foo", {}], ["-I", "$HOSTADDRESS$"]),
    (["foo", {
        "port": 80
    }], ["-p", 80, "-I", "$HOSTADDRESS$"]),
])
def test_check_form_submit_argument_parsing(params, expected_args):
    """Tests if all required arguments are present."""
    active_check = ActiveCheck("check_form_submit")
    assert active_check.run_argument_function(params) == expected_args
