#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.


# mypy: disable-error-code="var-annotated"

import time
from collections.abc import MutableMapping
from typing import Any

from cmk.base.check_api import LegacyCheckDefinition, regex
from cmk.base.config import check_info
from cmk.base.plugins.agent_based.agent_based_api.v1 import get_value_store, IgnoreResults, render

# <<<omd_apache:sep(124)>>>
# [heute]
# /heute/check_mk/view.py?view_name=allhosts&_display_options=htbfcoderuw&_do_actions=&_ajaxid=1433252694|200|5067|13465
# /heute/check_mk/sidebar_snapin.py?names=tactical_overview,admin|200|4046|8109
# /heute/check_mk/index.py?start_url=%2Fheute%2Fcheck_mk%2Fview.py%3Fview_name%3Dallhosts|200|515|7528
# /heute/check_mk/view.py?view_name=allhosts|200|37656|57298
# /heute/check_mk/side.py|200|39885|108178
# /heute/check_mk/js/graphs-2015.06.02.js|200|28895|1823
# [heute2]

omd_apache_patterns = [
    # perf keys         url matching regex
    ("cmk_views", r"^check_mk/view\.py"),
    ("cmk_wato", r"^check_mk/wato\.py"),
    ("cmk_bi", r"^check_mk/bi\.py"),
    ("cmk_snapins", r"^check_mk/sidebar_snapin\.py"),
    ("cmk_dashboards", r"^check_mk/dashboard\.py"),
    ("cmk_other", r"^check_mk/.*\.py"),
    ("nagvis_snapin", r"^nagvis/server/core/ajax_handler\.php?mod=Multisite&act=getMaps"),
    ("nagvis_ajax", r"^nagvis/server/core/ajax_handler\.php"),
    ("nagvis_other", r"^nagvis/.*\.php"),
    ("images", r"\.(jpg|png|gif)$"),
    ("styles", r"\.css$"),
    ("scripts", r"\.js$"),
    ("other", ".*"),
]


def inventory_omd_apache(parsed):
    return [(k, None) for k in parsed]


def _compute_rate(
    value_store: MutableMapping[str, Any], key: str, now: float, value: float
) -> float | None:
    last_time = value_store.get(key)
    value_store[key] = now
    if last_time is None or (time_delta := now - last_time) == 0:
        return None
    return value / time_delta


def check_omd_apache(item, _no_params, parsed):
    # First initialize all possible values to be able to always report all perf keys
    stats = {"requests": {}, "secs": {}, "bytes": {}}
    for key, pattern in omd_apache_patterns:
        stats["requests"][key] = 0
        stats["secs"][key] = 0
        stats["bytes"][key] = 0

    if item not in parsed:
        return
    if not parsed[item]:
        yield 0, "No activity since last check"
        return

    for line in parsed[item]:
        if len(line) < 3:
            continue
        if len(line) == 4:
            url, _status, size_bytes, microsec = line
        else:
            url = " ".join(line[:-3])
            _status, size_bytes, microsec = line[-3:]

        for key, pattern in omd_apache_patterns:
            # make url relative to site directory
            if regex(pattern).search(url[len("/" + item + "/") :]):
                stats["requests"].setdefault(key, 0)
                stats["requests"][key] += 1

                stats["secs"].setdefault(key, 0)
                stats["secs"][key] += (int(microsec) / 1000.0) / 1000.0

                stats["bytes"].setdefault(key, 0)
                stats["bytes"][key] += int(size_bytes)

                break  # don't call a line twice

    # Now process the result. Break down the gathered values to values per second.
    # the output is showing total values, for the graphing we provide detailed data
    this_time = time.time()
    value_store = get_value_store()
    for ty, title in [
        ("requests", "Requests"),
        ("secs", "Seconds serving"),
        ("bytes", "Sent"),
    ]:
        total = 0.0
        for key, value in sorted(stats[ty].items(), key=lambda k_v: k_v[1], reverse=True):
            metric_name = f"{ty}_{key}"
            if (rate := _compute_rate(value_store, metric_name, this_time, value)) is None:
                yield IgnoreResults(f"Initialized counter '{metric_name}'")
                continue
            total += rate
            yield 0, "", [(metric_name, rate)]

        total_str = render.iobandwidth(total) if ty == "bytes" else ("%.2f/s" % total)
        yield 0, f"{title}: {total_str}"


# This check uses the section defined in cmk/base/plugins/agent_based/omd_apache.py!
check_info["omd_apache"] = LegacyCheckDefinition(
    service_name="OMD %s apache",
    discovery_function=inventory_omd_apache,
    check_function=check_omd_apache,
)
