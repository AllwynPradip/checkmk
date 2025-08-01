#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.
"""Setup can be set into read only mode manually using this mode"""

import time
from collections.abc import Collection
from typing import cast

from cmk.ccc import store
from cmk.gui import userdb
from cmk.gui.breadcrumb import Breadcrumb
from cmk.gui.config import Config
from cmk.gui.htmllib.html import html
from cmk.gui.i18n import _
from cmk.gui.logged_in import user
from cmk.gui.page_menu import make_simple_form_page_menu, PageMenu
from cmk.gui.type_defs import ActionResult, PermissionName, ReadOnlySpec
from cmk.gui.utils.csrf_token import check_csrf_token
from cmk.gui.utils.flashed_messages import flash
from cmk.gui.valuespec import (
    AbsoluteDate,
    Alternative,
    Dictionary,
    FixedValue,
    ListOf,
    TextAreaUnicode,
    Tuple,
)
from cmk.gui.watolib.mode import mode_url, ModeRegistry, redirect, WatoMode
from cmk.gui.watolib.utils import multisite_dir


def register(mode_registry: ModeRegistry) -> None:
    mode_registry.register(ModeManageReadOnly)


class ModeManageReadOnly(WatoMode):
    @classmethod
    def name(cls) -> str:
        return "read_only"

    @staticmethod
    def static_permissions() -> Collection[PermissionName]:
        return ["set_read_only"]

    def title(self) -> str:
        return _("Manage configuration read only mode")

    def page_menu(self, config: Config, breadcrumb: Breadcrumb) -> PageMenu:
        return make_simple_form_page_menu(
            _("Mode"), breadcrumb, form_name="read_only", button_name="_save"
        )

    def action(self, config: Config) -> ActionResult:
        check_csrf_token()

        raw_settings = self._vs().from_html_vars("_read_only")
        self._vs().validate_value(raw_settings, "_read_only")
        # cast needed because valuespec does not return a proper type
        settings = cast(ReadOnlySpec, raw_settings)

        self._save(settings, pprint_value=config.wato_pprint_config)
        config.wato_read_only = settings
        flash(_("Saved read only settings"))
        return redirect(mode_url("read_only"))

    def _save(self, settings: ReadOnlySpec, *, pprint_value: bool) -> None:
        store.save_to_mk_file(
            multisite_dir() / "read_only.mk",
            key="wato_read_only",
            value=settings,
            pprint_value=pprint_value,
        )

    def page(self, config: Config) -> None:
        html.p(
            _(
                "The Setup configuration can be set to read only mode for all users that are not "
                "permitted to ignore the read only mode. All users that are permitted to set the "
                "read only can disable it again when another permitted user enabled it before."
            )
        )
        with html.form_context("read_only", method="POST"):
            self._vs().render_input("_read_only", dict(config.wato_read_only))
            html.hidden_fields()

    def _vs(self) -> Dictionary:
        return Dictionary(
            title=_("Read only mode"),
            optional_keys=False,
            render="form",
            elements=[
                (
                    "enabled",
                    Alternative(
                        title=_("Enabled"),
                        elements=[
                            FixedValue(
                                value=False,
                                title=_("Disabled "),
                                totext="Not enabled",
                            ),
                            FixedValue(
                                value=True,
                                title=_("Enabled permanently"),
                                totext=_("Enabled until disabling"),
                            ),
                            Tuple(
                                title=_("Enabled in time range"),
                                elements=[
                                    AbsoluteDate(
                                        title=_("Start"),
                                        include_time=True,
                                    ),
                                    AbsoluteDate(
                                        title=_("Until"),
                                        include_time=True,
                                        default_value=time.time() + 3600,
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                (
                    "rw_users",
                    ListOf(
                        valuespec=userdb.UserSelection(),
                        title=_("Can still edit"),
                        help=_("Users listed here are still allowed to modify things."),
                        movable=False,
                        add_label=_("Add user"),
                        default_value=[user.id],
                    ),
                ),
                (
                    "message",
                    TextAreaUnicode(
                        title=_("Message"),
                        rows=3,
                    ),
                ),
            ],
        )
