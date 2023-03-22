#!/usr/bin/env python3
# Copyright (C) 2023 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

from collections.abc import Callable, Iterable
from typing import NotRequired, TypedDict

_DiscoveredParameters = dict | tuple | str | None


class CheckInfoElement(TypedDict):
    check_function: NotRequired[Callable]
    inventory_function: NotRequired[
        Callable[..., None | Iterable[tuple[str | None, _DiscoveredParameters]]]
    ]
    parse_function: NotRequired[Callable[[list], object]]
    group: NotRequired[str]
    snmp_info: NotRequired[tuple | list]
    snmp_scan_function: NotRequired[Callable[[Callable], bool]]
    default_levels_variable: NotRequired[str]
    service_description: NotRequired[str]
