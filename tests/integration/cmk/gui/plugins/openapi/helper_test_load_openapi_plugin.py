#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

from cmk.gui import main_modules

main_modules.load_plugins()
import cmk.gui.openapi

# Mypy can not know about the test plugin
print(cmk.gui.openapi.x)  # type: ignore[attr-defined]
