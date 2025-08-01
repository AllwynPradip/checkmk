#!/usr/bin/env python3
# Copyright (C) 2025 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.
from ipaddress import ip_address
from typing import Final

from cmk.rulesets.v1 import Message
from cmk.rulesets.v1.form_specs.validators import ValidationError


class IPAddress:
    """Validator that ensures the validated value is an IP v4 or v6 address"""

    def __init__(self, error_msg: Message | None = None) -> None:
        self.error_msg: Final = error_msg or (Message("Your input is not a valid IP address."))

    def __call__(self, value: str) -> None:
        try:
            ip_address(value)
        except ValueError:
            raise ValidationError(self.error_msg)
