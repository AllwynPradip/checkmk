#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2019 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

# yapf: disable
# type: ignore

checkname = 'k8s_conditions'

info = [[
    '{"DiskPressure": "False", "OutOfDisk": "False", "MemoryPressure": "False", "Ready": "False", "NetworkUnavailable": "False", "KernelDeadlock": "True"}'
]]

discovery = {
    '': [('DiskPressure', {}), ('KernelDeadlock', {}), ('MemoryPressure', {}),
         ('NetworkUnavailable', {}), ('OutOfDisk', {}), ('Ready', {})]
}

checks = {
    '': [('DiskPressure', {}, [(0, 'False', [])]), ('KernelDeadlock', {}, [(2, 'True', [])]),
         ('MemoryPressure', {}, [(0, 'False', [])]),
         ('NetworkUnavailable', {}, [(0, 'False', [])]), ('OutOfDisk', {}, [(0, 'False', [])]),
         ('Ready', {}, [(2, 'False', [])])]
}
