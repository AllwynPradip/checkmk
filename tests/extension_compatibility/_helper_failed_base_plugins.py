#!/usr/bin/env python3
# Copyright (C) 2023 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

import json

from cmk.base.config import load_all_pluginX
from cmk.utils import paths

print(json.dumps(load_all_pluginX(paths.checks_dir).errors))
