#!/usr/bin/env python3
# Copyright (C) 2022 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.
from typing import cast

from flask import current_app, g

from cmk.gui import http, i18n
from cmk.gui.config import active_config
from cmk.gui.display_options import DisplayOptions
from cmk.gui.htmllib.html import HTMLGenerator
from cmk.gui.http import request
from cmk.gui.utils.logging_filters import PrependURLFilter
from cmk.gui.utils.mobile import is_mobile
from cmk.gui.utils.output_funnel import OutputFunnel
from cmk.gui.utils.theme import Theme
from cmk.gui.utils.timeout_manager import TimeoutManager
from cmk.gui.utils.user_errors import UserErrors
from cmk.gui.wsgi.applications.checkmk import get_mime_type_from_output_format, get_output_format


def set_global_vars() -> None:
    # These variables will only be retained for the duration of the request.
    # *Flask* will clear them after the request finished.

    # Be aware that the order, in which these initialized is intentional.
    g.endpoint = None
    g.translation = None

    output_format = get_output_format(request.args.get("output_format", default="html", type=str))

    response = cast(http.Response, current_app.make_response(""))
    response.mimetype = get_mime_type_from_output_format(output_format)

    # The oder within this block is irrelevant.
    g.output_funnel = output_funnel = OutputFunnel(response)
    g.display_options = DisplayOptions()
    g.response = response
    g.theme = theme = Theme()
    theme.from_config(active_config.ui_theme)
    g.timeout_manager = TimeoutManager()
    g.url_filter = PrependURLFilter()
    g.user_errors = UserErrors()
    g.html = HTMLGenerator(
        request,
        output_funnel=output_funnel,
        output_format=output_format,
        mobile=is_mobile(request, response),
    )

    lang_code = request.args.get("lang", default=active_config.default_language, type=str)
    i18n.localize(lang_code)  # sets g.translation
