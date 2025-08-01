#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.
"""Mode for searching hosts"""

from collections.abc import Collection

from cmk.gui import forms
from cmk.gui.breadcrumb import Breadcrumb
from cmk.gui.config import Config
from cmk.gui.htmllib.html import html
from cmk.gui.http import request
from cmk.gui.i18n import _
from cmk.gui.page_menu import make_simple_form_page_menu, PageMenu
from cmk.gui.type_defs import ActionResult, HTTPVariables, PermissionName
from cmk.gui.utils.csrf_token import check_csrf_token
from cmk.gui.utils.urls import makeuri_contextless
from cmk.gui.valuespec import TextInput
from cmk.gui.wato.pages.folders import ModeFolder
from cmk.gui.watolib.host_attributes import all_host_attributes
from cmk.gui.watolib.hosts_and_folders import folder_from_request
from cmk.gui.watolib.mode import ModeRegistry, redirect, WatoMode

from ._host_attributes import configure_attributes


def register(mode_registry: ModeRegistry) -> None:
    mode_registry.register(ModeSearch)


class ModeSearch(WatoMode):
    @classmethod
    def name(cls) -> str:
        return "search"

    @staticmethod
    def static_permissions() -> Collection[PermissionName]:
        return ["hosts"]

    @classmethod
    def parent_mode(cls) -> type[WatoMode] | None:
        return ModeFolder

    def __init__(self) -> None:
        super().__init__()
        self._folder = folder_from_request(request.var("folder"), request.get_ascii_input("host"))

    def page_menu(self, config: Config, breadcrumb: Breadcrumb) -> PageMenu:
        return make_simple_form_page_menu(
            _("Search"),
            breadcrumb,
            form_name="edit_host",
            button_name="_save",
            save_title=_("Submit"),
            save_icon="search",
            save_is_enabled=True,
        )

    def title(self) -> str:
        return _("Search for hosts below %s") % self._folder.title()

    def action(self, config: Config) -> ActionResult:
        check_csrf_token()

        return redirect(
            makeuri_contextless(
                request,
                self._get_search_vars(),
            )
        )

    def _get_search_vars(self) -> HTTPVariables:
        search_vars = {}

        if request.has_var("host_search_host"):
            search_vars["host_search_host"] = request.get_ascii_input_mandatory("host_search_host")

        for varname, value in request.itervars(prefix="host_search_change_"):
            if html.get_checkbox(varname) is False:
                continue

            search_vars[varname] = value

            attr_ident = varname.split("host_search_change_", 1)[1]

            # The URL variable naming scheme is not clear. Try to match with "attr_" prefix
            # and without. We should investigate and clean this up.
            attr_prefix = "host_search_attr_%s" % attr_ident
            search_vars.update(request.itervars(prefix=attr_prefix))
            attr_prefix = "host_search_%s" % attr_ident
            search_vars.update(request.itervars(prefix=attr_prefix))

        for varname, value in request.itervars():
            if varname.startswith(("_", "host_search_")) or varname == "mode":
                continue
            search_vars[varname] = value

        search_vars["mode"] = "folder"

        return list(search_vars.items())

    def page(self, config: Config) -> None:
        html.help(
            _(
                "For the host name field, a partial word search (infix search) is used "
                "— the entered text is searched, at any position, in the host name. "
                "Furthermore, you can limit the search using other host attributes. Please note "
                "that you can search for the attributes configured in the hosts and folders and "
                "not the final settings applied to the monitoring once it's activated. For "
                "in the labels field you are only searching for the explicitly configured labels "
                "and not the effective labels of a host."
            )
        )
        # Show search form
        with html.form_context("edit_host", method="POST"):
            html.prevent_password_auto_completion()

            basic_attributes = [
                (
                    "host_search_host",
                    TextInput(title=_("Host name")),
                    "",
                ),
            ]
            html.set_focus("host_search_host")

            # Attributes
            configure_attributes(
                all_host_attributes(config.wato_host_attrs, config.tags.get_tag_groups_by_topic()),
                new=False,
                hosts={},
                for_what="host_search",
                parent=None,
                varprefix="host_search_",
                basic_attributes=basic_attributes,
                aux_tags_by_tag=config.tags.get_aux_tags_by_tag(),
            )

            forms.end()
            html.hidden_field("host_search", "1")
            html.hidden_fields()
