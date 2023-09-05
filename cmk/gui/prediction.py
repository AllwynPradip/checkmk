#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

import json
import time
from collections.abc import Sequence
from dataclasses import dataclass, field

import livestatus

import cmk.utils.prediction as _prediction
from cmk.utils.exceptions import MKGeneralException
from cmk.utils.hostaddress import HostName

import cmk.gui.sites as sites
from cmk.gui.htmllib.header import make_header
from cmk.gui.htmllib.html import html
from cmk.gui.http import request
from cmk.gui.i18n import _
from cmk.gui.pages import PageRegistry
from cmk.gui.view_breadcrumbs import make_service_breadcrumb

graph_size = 2000, 700


@dataclass(frozen=True)
class SwappedStats:
    average: list[float | None] = field(default_factory=list)
    min_: list[float | None] = field(default_factory=list)
    max_: list[float | None] = field(default_factory=list)
    stdev: list[float | None] = field(default_factory=list)
    upper_warn: list[float] = field(default_factory=list)
    upper_crit: list[float] = field(default_factory=list)
    lower_warn: list[float] = field(default_factory=list)
    lower_crit: list[float] = field(default_factory=list)


def register(page_registry: PageRegistry) -> None:
    page_registry.register_page_handler("prediction_graph", page_graph)


def _load_prediction_information(
    *,
    tg_name: str | None,
    prediction_store: _prediction.PredictionStore,
) -> tuple[_prediction.PredictionInfo, Sequence[tuple[str, str]]]:
    selected_timegroup: _prediction.PredictionInfo | None = None
    timegroups: list[_prediction.PredictionInfo] = []
    now = time.time()
    for tg_info in prediction_store.available_predictions():
        timegroups.append(tg_info)
        if tg_info.name == tg_name or (
            tg_name is None and (tg_info.range[0] <= now <= tg_info.range[1])
        ):
            selected_timegroup = tg_info

    timegroups.sort(key=lambda x: x.range[0])

    if selected_timegroup is None:
        if not timegroups:
            raise MKGeneralException(
                _("There is currently no prediction information available for this service.")
            )
        selected_timegroup = timegroups[0]

    return selected_timegroup, [(tg.name, tg.name.title()) for tg in timegroups]


def page_graph() -> None:
    host_name = HostName(request.get_str_input_mandatory("host"))
    service = request.get_str_input_mandatory("service")
    dsname = request.get_str_input_mandatory("dsname")

    breadcrumb = make_service_breadcrumb(host_name, service)
    make_header(
        html,
        _("Prediction for %s - %s - %s") % (host_name, service, dsname),
        breadcrumb,
    )

    # Get current value from perf_data via Livestatus
    current_value = get_current_perfdata(host_name, service, dsname)

    prediction_store = _prediction.PredictionStore(host_name, service, dsname)

    timegroup, choices = _load_prediction_information(
        tg_name=request.var("timegroup"),
        prediction_store=prediction_store,
    )

    html.begin_form("prediction")
    html.write_text(_("Show prediction for "))
    html.dropdown(
        "timegroup", choices, deflt=timegroup.name, onchange="document.prediction.submit();"
    )
    html.hidden_fields()
    html.end_form()

    # Get prediction data
    tg_data = prediction_store.get_data(timegroup.name)
    if tg_data is None:
        raise MKGeneralException(_("Missing prediction data."))

    swapped = swap_and_compute_levels(tg_data, timegroup.params)
    vertical_range = compute_vertical_range(swapped)
    legend = [
        ("#000000", _("Reference")),
        ("#ffffff", _("OK area")),
        ("#ffff00", _("Warning area")),
        ("#ff0000", _("Critical area")),
    ]
    if current_value is not None:
        legend.append(("#0000ff", _("Current value: %.2f") % current_value))

    create_graph(timegroup.name, graph_size, timegroup.range, vertical_range, legend)

    if timegroup.params.levels_upper is not None:
        render_dual_area(swapped.upper_warn, swapped.upper_crit, "#fff000", 0.4)
        render_area_reverse(swapped.upper_crit, "#ff0000", 0.1)

    if timegroup.params.levels_lower is not None:
        render_dual_area(swapped.lower_crit, swapped.lower_warn, "#fff000", 0.4)
        render_area(swapped.lower_crit, "#ff0000", 0.1)

    vscala_low = vertical_range[0]
    vscala_high = vertical_range[1]
    vert_scala = _compute_vertical_scala(vscala_low, vscala_high)
    time_scala = [[timegroup.range[0] + i * 3600, "%02d:00" % i] for i in range(0, 25, 2)]
    render_coordinates(vert_scala, time_scala)

    if timegroup.params.levels_lower is not None:
        render_dual_area(swapped.average, swapped.lower_warn, "#ffffff", 0.5)
        render_curve(swapped.lower_warn, "#e0e000", square=True)
        render_curve(swapped.lower_crit, "#f0b0b0", square=True)

    if timegroup.params.levels_upper is not None:
        render_dual_area(swapped.upper_warn, swapped.average, "#ffffff", 0.5)
        render_curve(swapped.upper_warn, "#e0e000", square=True)
        render_curve(swapped.upper_crit, "#f0b0b0", square=True)
    render_curve(swapped.average, "#000000")
    render_curve(swapped.average, "#000000")  # repetition makes line bolder

    # Try to get current RRD data and render it also
    from_time, until_time = timegroup.range
    now = time.time()
    if from_time <= now <= until_time:
        timeseries = _prediction.get_rrd_data(
            livestatus.LocalConnection(), host_name, service, dsname, "MAX", from_time, until_time
        )
        rrd_data = timeseries.values

        render_curve(rrd_data, "#0000ff", 2)
        if current_value is not None:
            rel_time = (now - _prediction.timezone_at(now)) % timegroup.slice
            render_point(timegroup.range[0] + rel_time, current_value, "#0000ff")

    html.footer()


vranges = [
    ("n", 1024.0**-3),
    ("u", 1024.0**-2),
    ("m", 1024.0**-1),
    ("", 1024.0**0),
    ("K", 1024.0**1),
    ("M", 1024.0**2),
    ("G", 1024.0**3),
    ("T", 1024.0**4),
]


def _compute_vertical_scala(  # pylint: disable=too-many-branches
    low: float, high: float
) -> Sequence[tuple[float, str]]:
    m = max(abs(low), abs(high))
    for letter, factor in vranges:
        if m <= 99 * factor:
            break
    else:
        letter = "P"
        factor = 1024.0**5

    v = 0.0
    steps = (max(0, high) - min(0, low)) / factor
    if steps < 3:
        step = 0.2 * factor
    elif steps < 6:
        step = 0.5 * factor
    elif steps > 50:
        step = 5 * factor
    elif steps > 20:
        step = 2 * factor
    else:
        step = factor

    vert_scala = []
    while v <= max(0, high):
        vert_scala.append((v, f"{v / factor:.1f}{letter}"))
        v += step

    v = -factor
    while v >= min(0, low):
        vert_scala = [(v, f"{v / factor:.1f}{letter}")] + vert_scala
        v -= step

    # Remove trailing ".0", if that is present for *all* entries
    for entry in vert_scala:
        if not entry[1].endswith(".0"):
            break
    else:
        vert_scala = [(e[0], e[1][:-2]) for e in vert_scala]

    return vert_scala


def get_current_perfdata(host: HostName, service: str, dsname: str) -> float | None:
    perf_data = sites.live().query_value(
        "GET services\nFilter: host_name = %s\nFilter: description = %s\n"
        "Columns: perf_data" % (livestatus.lqencode(str(host)), livestatus.lqencode(service))
    )

    for part in perf_data.split():
        name, rest = part.split("=")
        if name == dsname:
            return float(rest.split(";")[0])
    return None


# Compute check levels from prediction data and check parameters
def swap_and_compute_levels(
    tg_data: _prediction.PredictionData, params: _prediction.PredictionParameters
) -> SwappedStats:
    swapped = SwappedStats()
    for step in tg_data.points:
        if step is not None:
            swapped.average.append(step.average)
            swapped.min_.append(step.min_)
            swapped.max_.append(step.max_)
            swapped.stdev.append(step.stdev)
            upper_0, upper_1, lower_0, lower_1 = _prediction.estimate_levels(
                reference_value=step.average,
                stdev=step.stdev,
                levels_lower=params.levels_lower,
                levels_upper=params.levels_upper,
                levels_upper_lower_bound=params.levels_upper_min,
                levels_factor=1.0,
            )
            swapped.upper_warn.append(upper_0 or 0)
            swapped.upper_crit.append(upper_1 or 0)
            swapped.lower_warn.append(lower_0 or 0)
            swapped.lower_crit.append(lower_1 or 0)
        else:
            swapped.average.append(None)
            swapped.min_.append(None)
            swapped.max_.append(None)
            swapped.stdev.append(None)
            swapped.upper_warn.append(0)
            swapped.upper_crit.append(0)
            swapped.lower_warn.append(0)
            swapped.lower_crit.append(0)

    return swapped


def compute_vertical_range(swapped: SwappedStats) -> tuple[float, float]:
    points = (
        swapped.average
        + swapped.min_
        + swapped.max_
        + swapped.min_
        + swapped.stdev
        + swapped.upper_warn
        + swapped.upper_crit
        + swapped.lower_warn
        + swapped.lower_crit
    )
    return min(filter(None, points), default=0.0), max(filter(None, points), default=0.0)


def create_graph(name, size, bounds, v_range, legend):
    html.open_table(class_="prediction")
    html.open_tr()
    html.open_td()
    html.canvas(
        "",
        class_="prediction",
        id_="content_%s" % name,
        style="width: %dpx; height: %dpx;" % (int(size[0] / 2.0), int(size[1] / 2.0)),
        width=size[0],
        height=size[1],
    )
    html.close_td()
    html.close_tr()
    html.open_tr()
    html.open_td(class_="legend")
    for color, title in legend:
        html.div("", class_="color", style="background-color: %s" % color)
        html.div(title, class_="entry")
    html.close_td()
    html.close_tr()
    html.close_table()
    html.javascript(
        f'cmk.prediction.create_graph("content_{name}", {bounds[0]:.4f}, {bounds[1]:.4f}, {v_range[0]:.4f}, {v_range[1]:.4f});'
    )


def render_coordinates(v_scala, t_scala) -> None:  # type: ignore[no-untyped-def]
    html.javascript(
        f"cmk.prediction.render_coordinates({json.dumps(v_scala)}, {json.dumps(t_scala)});"
    )


def render_curve(points, color, width=1, square=False) -> None:  # type: ignore[no-untyped-def]
    html.javascript(
        "cmk.prediction.render_curve(%s, %s, %d, %d);"
        % (json.dumps(points), json.dumps(color), width, square and 1 or 0)
    )


def render_point(t, v, color) -> None:  # type: ignore[no-untyped-def]
    html.javascript(
        f"cmk.prediction.render_point({json.dumps(t)}, {json.dumps(v)}, {json.dumps(color)});"
    )


def render_area(points, color, alpha=1.0) -> None:  # type: ignore[no-untyped-def]
    html.javascript(
        f"cmk.prediction.render_area({json.dumps(points)}, {json.dumps(color)}, {alpha:f});"
    )


def render_area_reverse(points, color, alpha=1.0) -> None:  # type: ignore[no-untyped-def]
    html.javascript(
        f"cmk.prediction.render_area_reverse({json.dumps(points)}, {json.dumps(color)}, {alpha:f});"
    )


def render_dual_area(  # type: ignore[no-untyped-def]
    lower_points, upper_points, color, alpha=1.0
) -> None:
    html.javascript(
        f"cmk.prediction.render_dual_area({json.dumps(lower_points)}, {json.dumps(upper_points)}, {json.dumps(color)}, {alpha:f});"
    )
