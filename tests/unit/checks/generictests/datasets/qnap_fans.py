#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2019 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

# yapf: disable
# type: ignore

checkname = 'qnap_fans'

info = [['1', '1027 RPM'], ['2', '968 RPM']]

discovery = {'': [('1', {}), ('2', {})]}

checks = {
    '': [
        (
            '1', {
                'upper': (6000, 6500),
                'lower': (None, None)
            }, [(0, 'Speed: 1027 RPM', [])]
        ),
        (
            '2', {
                'upper': (6000, 6500),
                'lower': (None, None)
            }, [(0, 'Speed: 968 RPM', [])]
        )
    ]
}
