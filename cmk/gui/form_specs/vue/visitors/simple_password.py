#!/usr/bin/env python3
# Copyright (C) 2024 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.
import base64
from collections.abc import Callable, Sequence
from typing import Any, override

from cmk.gui.form_specs.converter import SimplePassword
from cmk.gui.form_specs.private import not_empty
from cmk.gui.i18n import _
from cmk.gui.utils.encrypter import Encrypter
from cmk.shared_typing import vue_formspec_components as shared_type_defs

from .._type_defs import DefaultValue, IncomingData, InvalidValue, RawDiskData
from .._utils import (
    compute_validators,
    get_title_and_help,
    optional_validation,
)
from .._visitor_base import FormSpecVisitor
from ..validators import build_vue_validators

_ParsedValueModel = str
_FallbackModel = tuple[str, bool]


class SimplePasswordVisitor(FormSpecVisitor[SimplePassword, _ParsedValueModel, _FallbackModel]):
    @override
    def _parse_value(
        self, raw_value: IncomingData
    ) -> _ParsedValueModel | InvalidValue[_FallbackModel]:
        if isinstance(raw_value, DefaultValue):
            return InvalidValue(reason=_("No password provided"), fallback_value=("", False))

        if isinstance(raw_value, RawDiskData):
            if not isinstance(raw_value.value, str):
                return InvalidValue(reason=_("No password provided"), fallback_value=("", False))
            return raw_value.value

        if not isinstance(raw_value.value, list):
            return InvalidValue(reason=_("No password provided"), fallback_value=("", False))
        password, encrypted = raw_value.value
        if not isinstance(password, str):
            return InvalidValue(reason=_("No password provided"), fallback_value=("", False))

        return (
            Encrypter.decrypt(base64.b64decode(password.encode("ascii"))) if encrypted else password
        )

    @override
    def _validators(self) -> Sequence[Callable[[Any], object]]:
        return [not_empty()] + compute_validators(self.form_spec)

    @override
    def _to_vue(
        self, parsed_value: _ParsedValueModel | InvalidValue[_FallbackModel]
    ) -> tuple[shared_type_defs.SimplePassword, object]:
        title, help_text = get_title_and_help(self.form_spec)
        if isinstance(parsed_value, InvalidValue):
            encrypted_password = parsed_value.fallback_value[0]
        else:
            encrypted_password = base64.b64encode(Encrypter.encrypt(parsed_value)).decode("ascii")

        return (
            shared_type_defs.SimplePassword(
                title=title,
                help=help_text,
                validators=build_vue_validators(self._validators()),
            ),
            (encrypted_password, bool(encrypted_password)),
        )

    @override
    def _validate(
        self, parsed_value: _ParsedValueModel
    ) -> list[shared_type_defs.ValidationMessage]:
        return [
            shared_type_defs.ValidationMessage(location=[], message=x, replacement_value="")
            for x in optional_validation(self._validators(), parsed_value)
            if x is not None
        ]

    @override
    def _to_disk(self, parsed_value: _ParsedValueModel) -> object:
        return parsed_value

    @override
    def _mask(self, parsed_value: _ParsedValueModel) -> object:
        return "******"
