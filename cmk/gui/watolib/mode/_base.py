#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

import abc
from collections.abc import Collection, Iterable
from typing import final

from cmk.gui.breadcrumb import Breadcrumb, BreadcrumbItem
from cmk.gui.config import Config
from cmk.gui.htmllib.html import html
from cmk.gui.http import request
from cmk.gui.i18n import _
from cmk.gui.logged_in import user
from cmk.gui.main_menu import main_menu_registry
from cmk.gui.page_menu import PageMenu
from cmk.gui.type_defs import ActionResult, HTTPVariables, MainMenu, PermissionName
from cmk.gui.utils.transaction_manager import transactions
from cmk.gui.utils.urls import makeuri_contextless
from cmk.gui.watolib.main_menu import main_module_registry


class WatoMode(abc.ABC):
    def __init__(self) -> None:
        super().__init__()
        self._from_vars()

    @staticmethod
    @abc.abstractmethod
    def static_permissions() -> None | Collection[PermissionName]:
        """Static permissions needed to access this mode

        static_permissions = None -> every user can use this mode, permissions
        are checked by the mode itself. Otherwise the user needs at
        least wato.use and - if he makes actions - wato.edit. Plus wato.*
        for each permission in the list."""
        raise NotImplementedError()

    @final
    @classmethod
    def _ensure_static_permissions(cls) -> None:
        permissions = cls.static_permissions()
        if permissions is None:
            permissions = []
        else:
            user.need_permission("wato.use")
        if transactions.is_transaction():
            user.need_permission("wato.edit")
        elif user.may("wato.seeall"):
            permissions = []
        for pname in permissions:
            user.need_permission(pname if "." in pname else ("wato." + pname))

    def ensure_permissions(self) -> None:
        """Overwrite this method to additionally check request-specific permissions if needed."""
        self._ensure_static_permissions()

    @classmethod
    @abc.abstractmethod
    def name(cls) -> str:
        """Wato wide unique mode name which is used to access this mode"""
        raise NotImplementedError("%s misses name()" % cls.__name__)

    @classmethod
    def mode_url(cls, **kwargs: str) -> str:
        """Create a URL pointing to this mode (with all needed vars)"""
        get_vars: HTTPVariables = [("mode", cls.name())]
        get_vars += list(kwargs.items())
        return makeuri_contextless(request, get_vars, filename="wato.py")

    @classmethod
    def parent_mode(cls) -> None | type["WatoMode"]:
        """Reference from a mode to it's parent mode to make the breadcrumb be able to render the
        hierarchy of modes"""
        return None

    def _from_vars(self) -> None:
        """Override this method to set mode specific attributes based on the
        given HTTP variables."""

    def title(self) -> str:
        return _("(Untitled module)")

    # Currently only needed for a special Setup module "user_notifications_p" that
    # is not part of the Setup main menu but the user menu.
    def main_menu(self) -> MainMenu:
        """Specify the top-level breadcrumb item of this mode"""
        return main_menu_registry.menu_setup()

    def breadcrumb(self) -> Breadcrumb:
        """Render the breadcrumb to the current mode

        This methods job is to a) gather the breadcrumb from the
        parent modes, b) append it's own part and then return it
        """

        if parent_cls := self.parent_mode():
            # For some reason pylint does not understand that this is a class type
            breadcrumb = parent_cls().breadcrumb()
        else:
            breadcrumb = Breadcrumb()

        breadcrumb.extend(self._topic_breadcrumb_item())
        breadcrumb.append(self._breadcrumb_item())

        return breadcrumb

    def _breadcrumb_item(self) -> BreadcrumbItem:
        """Return the breadcrumb item for the current mode"""
        # For the currently active mode use the same link as the "page title click"
        if request.get_ascii_input("mode") == self.name():
            breadcrumb_url = "javascript:window.location.reload(false)"
        else:
            breadcrumb_url = self._breadcrumb_url()

        return BreadcrumbItem(
            title=self.title(),
            url=breadcrumb_url,
        )

    def _breadcrumb_url(self) -> str:
        """Override this method to implement a custom breadcrumb URL

        This can be useful when a mode needs some more contextual information
        to link to the correct page.
        """
        return self.mode_url()

    def _topic_breadcrumb_item(self) -> Iterable[BreadcrumbItem]:
        """Yield the BreadcrumbItem(s) for the topic of this mode

        For the top level modes we need to prepend the topic of the mode.
        The mode is sadly not available directly in WatoMode. Instead it is
        configured in the MainModule class that is related to the WatoMode.
        There is no 1:1 connection between WatoMode / MainModule classes.
        For the moment we lookup the main_module_registry to find the topics
        for as many modes as possible.

        TODO: Once all non top level modes have a parent_mode() method, we
              know which modes are top level modes. Then we could move all
              attributes from the MainModules to the WatoModes and create
              the Setup menu items directly out of the WatoModes.
        """
        mode_name = self.name()

        main_module = main_module_registry.get(mode_name)
        if main_module is None:
            return
            # TODO: Can be activated once all non top level modes have a parent_mode set
            # raise RuntimeError("Could not determine topic breadcrumb item for mode %r" % mode_name)

        yield BreadcrumbItem(
            title=main_module().topic.title,
            url=None,
        )
        yield from main_module.additional_breadcrumb_items()

    def page_menu(self, config: Config, breadcrumb: Breadcrumb) -> PageMenu:
        """Returns the data structure representing the page menu for this mode"""
        return PageMenu(breadcrumb=breadcrumb)

    def buttons(self) -> None: ...

    def action(self, config: Config) -> ActionResult: ...

    def page(self, config: Config) -> None:
        html.show_message(_("(This module is not yet implemented)"))

    def handle_page(self, config: Config) -> None:
        return self.page(config)
