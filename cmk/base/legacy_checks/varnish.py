#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.


# mypy: disable-error-code="var-annotated"

import time

from cmk.agent_based.legacy.v0_unstable import check_levels, LegacyCheckDefinition
from cmk.agent_based.v2 import get_rate, get_value_store, render
from cmk.base.check_legacy_includes.uptime import check_uptime_seconds

check_info = {}


# Special thanks to Rene Stolle (r.stolle@funkemedien.de)
#   .--agent output--------------------------------------------------------.
#   |                           _                 _               _        |
#   |     __ _  __ _  ___ _ __ | |_    ___  _   _| |_ _ __  _   _| |_      |
#   |    / _` |/ _` |/ _ \ '_ \| __|  / _ \| | | | __| '_ \| | | | __|     |
#   |   | (_| | (_| |  __/ | | | |_  | (_) | |_| | |_| |_) | |_| | |_      |
#   |    \__,_|\__, |\___|_| |_|\__|  \___/ \__,_|\__| .__/ \__,_|\__|     |
#   |          |___/                                 |_|                   |
#   '----------------------------------------------------------------------'
# <<<varnish>>>
# client_conn           13687134         4.41 Client connections accepted
# client_drop                  0         0.00 Connection dropped, no sess/wrk
# client_req            22397280         7.21 Client requests received
# cache_hit                 3678         0.00 Cache hits
# cache_hitpass                0         0.00 Cache hits for pass
# cache_miss                5687         0.00 Cache misses
# backend_conn           6870153         2.21 Backend conn. success
# backend_unhealthy            0         0.00 Backend conn. not attempted
# backend_busy                 0         0.00 Backend conn. too many
# backend_fail                 0         0.00 Backend conn. failures
# backend_reuse         15528248         5.00 Backend conn. reuses
# backend_toolate           6235         0.00 Backend conn. was closed
# backend_recycle       15534489         5.00 Backend conn. recycles
# backend_retry               46         0.00 Backend conn. retry
# fetch_head                2026         0.00 Fetch head
# fetch_length            262203         0.08 Fetch with Length
# fetch_chunked         15034709         4.84 Fetch chunked
# fetch_eof                    0         0.00 Fetch EOF
# fetch_bad                    0         0.00 Fetch had bad headers
# fetch_close                  0         0.00 Fetch wanted close
# fetch_oldhttp                0         0.00 Fetch pre HTTP/1.1 closed
# fetch_zero                   0         0.00 Fetch zero len
# fetch_failed                 0         0.00 Fetch failed
# fetch_1xx                    0         0.00 Fetch no body (1xx)
# fetch_204                    0         0.00 Fetch no body (204)
# fetch_304               242534         0.08 Fetch no body (304)
# n_sess_mem              100000          .   N struct sess_mem
# n_sess                  205470          .   N struct sess
# n_object                     5          .   N struct object
# n_vampireobject              0          .   N unresurrected objects
# n_objectcore               101          .   N struct objectcore
# n_objecthead               104          .   N struct objecthead
# n_waitinglist             1655          .   N struct waitinglist
# n_vbc                       60          .   N struct vbc
# n_wrk                     1000          .   N worker threads
# n_wrk_create              1000         0.00 N worker threads created
# n_wrk_failed                 0         0.00 N worker threads not created
# n_wrk_max                  893         0.00 N worker threads limited
# n_wrk_lqueue                 0         0.00 work request queue length
# n_wrk_queued                21         0.00 N queued work requests
# n_wrk_drop                   0         0.00 N dropped work requests
# n_backend                    2          .   N backends
# n_expired                 5680          .   N expired objects
# n_lru_nuked                  0          .   N LRU nuked objects
# n_lru_moved               1031          .   N LRU moved objects
# losthdr                      0         0.00 HTTP header overflows
# n_objsendfile                0         0.00 Objects sent with sendfile
# n_objwrite            15303178         4.93 Objects sent with write
# n_objoverflow                0         0.00 Objects overflowing workspace
# s_sess                13687207         4.41 Total Sessions
# s_req                 22397280         7.21 Total Requests
# s_pipe                 6856634         2.21 Total pipe
# s_pass                15536150         5.00 Total pass
# s_fetch               15535049         5.00 Total fetch
# s_hdrbytes          2623427334       844.71 Total header bytes
# s_bodybytes        64229472478     20681.18 Total body bytes
# sess_closed           13154452         4.24 Session Closed
# sess_pipeline                0         0.00 Session Pipeline
# sess_readahead               0         0.00 Session Read Ahead
# sess_linger           15526026         5.00 Session Linger
# sess_herd             14211876         4.58 Session herd
# shm_records         1455193814       468.56 SHM records
# shm_writes           117694273        37.90 SHM writes
# shm_flushes                  0         0.00 SHM flushes due to overflow
# shm_cont               1081665         0.35 SHM MTX contention
# shm_cycles                 646         0.00 SHM cycles through buffer
# sms_nreq                  1919         0.00 SMS allocator requests
# sms_nobj                     0          .   SMS outstanding allocations
# sms_nbytes                   0          .   SMS outstanding bytes
# sms_balloc              708111          .   SMS bytes allocated
# sms_bfree               708111          .   SMS bytes freed
# backend_req           15541595         5.00 Backend requests made
# n_vcl                        1         0.00 N vcl total
# n_vcl_avail                  1         0.00 N vcl available
# n_vcl_discard                0         0.00 N vcl discarded
# n_ban                        1          .   N total active bans
# n_ban_add                    1         0.00 N new bans added
# n_ban_retire                 0         0.00 N old bans deleted
# n_ban_obj_test               0         0.00 N objects tested
# n_ban_re_test                0         0.00 N regexps tested against
# n_ban_dups                   0         0.00 N duplicate bans removed
# hcb_nolock                9355         0.00 HCB Lookups without lock
# hcb_lock                  5679         0.00 HCB Lookups with lock
# hcb_insert                5535         0.00 HCB Inserts
# esi_errors                   0         0.00 ESI parse errors (unlock)
# esi_warnings                 0         0.00 ESI parse warnings (unlock)
# accept_fail                  0         0.00 Accept failures
# client_drop_late             0         0.00 Connection dropped late
# uptime                 3105696         1.00 Client uptime
# dir_dns_lookups              0         0.00 DNS director lookups
# dir_dns_failed               0         0.00 DNS director failed lookups
# dir_dns_hit                  0         0.00 DNS director cached lookups hit
# dir_dns_cache_full           0         0.00 DNS director full dnscache
# vmods                        1          .   Loaded VMODs
# n_gzip                       0         0.00 Gzip operations
# n_gunzip                 82386         0.03 Gunzip operations
# LCK.sms.creat                1         0.00 Created locks
# LCK.sms.destroy              0         0.00 Destroyed locks
# LCK.sms.locks             5757         0.00 Lock Operations
# LCK.sms.colls                0         0.00 Collisions
# LCK.smp.creat                0         0.00 Created locks
# LCK.smp.destroy              0         0.00 Destroyed locks
# LCK.smp.locks                0         0.00 Lock Operations
# LCK.smp.colls                0         0.00 Collisions
# LCK.sma.creat                2         0.00 Created locks
# LCK.sma.destroy              0         0.00 Destroyed locks
# LCK.sma.locks         76782194        24.72 Lock Operations
# LCK.sma.colls                0         0.00 Collisions
# LCK.smf.creat                0         0.00 Created locks
# LCK.smf.destroy              0         0.00 Destroyed locks
# LCK.smf.locks                0         0.00 Lock Operations
# LCK.smf.colls                0         0.00 Collisions
# LCK.hsl.creat                0         0.00 Created locks
# LCK.hsl.destroy              0         0.00 Destroyed locks
# LCK.hsl.locks                0         0.00 Lock Operations
# LCK.hsl.colls                0         0.00 Collisions
# LCK.hcb.creat                1         0.00 Created locks
# LCK.hcb.destroy              0         0.00 Destroyed locks
# LCK.hcb.locks            28463         0.01 Lock Operations
# LCK.hcb.colls                0         0.00 Collisions
# LCK.hcl.creat                0         0.00 Created locks
# LCK.hcl.destroy              0         0.00 Destroyed locks
# LCK.hcl.locks                0         0.00 Lock Operations
# LCK.hcl.colls                0         0.00 Collisions
# LCK.vcl.creat                1         0.00 Created locks
# LCK.vcl.destroy              0         0.00 Destroyed locks
# LCK.vcl.locks             2849         0.00 Lock Operations
# LCK.vcl.colls                0         0.00 Collisions
# LCK.stat.creat               1         0.00 Created locks
# LCK.stat.destroy             0         0.00 Destroyed locks
# LCK.stat.locks          100000         0.03 Lock Operations
# LCK.stat.colls               0         0.00 Collisions
# LCK.sessmem.creat            1         0.00 Created locks
# LCK.sessmem.destroy            0         0.00 Destroyed locks
# LCK.sessmem.locks       13787845         4.44 Lock Operations
# LCK.sessmem.colls              0         0.00 Collisions
# LCK.wstat.creat                1         0.00 Created locks
# LCK.wstat.destroy              0         0.00 Destroyed locks
# LCK.wstat.locks          9610148         3.09 Lock Operations
# LCK.wstat.colls                0         0.00 Collisions
# LCK.herder.creat               1         0.00 Created locks
# LCK.herder.destroy             0         0.00 Destroyed locks
# LCK.herder.locks               1         0.00 Lock Operations
# LCK.herder.colls               0         0.00 Collisions
# LCK.wq.creat                   2         0.00 Created locks
# LCK.wq.destroy                 0         0.00 Destroyed locks
# LCK.wq.locks            60930521        19.62 Lock Operations
# LCK.wq.colls                   0         0.00 Collisions
# LCK.objhdr.creat            5628         0.00 Created locks
# LCK.objhdr.destroy          5528         0.00 Destroyed locks
# LCK.objhdr.locks           50484         0.02 Lock Operations
# LCK.objhdr.colls               0         0.00 Collisions
# LCK.exp.creat                  1         0.00 Created locks
# LCK.exp.destroy                0         0.00 Destroyed locks
# LCK.exp.locks            3116794         1.00 Lock Operations
# LCK.exp.colls                  0         0.00 Collisions
# LCK.lru.creat                  2         0.00 Created locks
# LCK.lru.destroy                0         0.00 Destroyed locks
# LCK.lru.locks               5685         0.00 Lock Operations
# LCK.lru.colls                  0         0.00 Collisions
# LCK.cli.creat                  1         0.00 Created locks
# LCK.cli.destroy                0         0.00 Destroyed locks
# LCK.cli.locks            1034578         0.33 Lock Operations
# LCK.cli.colls                  0         0.00 Collisions
# LCK.ban.creat                  1         0.00 Created locks
# LCK.ban.destroy                0         0.00 Destroyed locks
# LCK.ban.locks            3116799         1.00 Lock Operations
# LCK.ban.colls                  0         0.00 Collisions
# LCK.vbp.creat                  1         0.00 Created locks
# LCK.vbp.destroy                0         0.00 Destroyed locks
# LCK.vbp.locks                  0         0.00 Lock Operations
# LCK.vbp.colls                  0         0.00 Collisions
# LCK.vbe.creat                  1         0.00 Created locks
# LCK.vbe.destroy                0         0.00 Destroyed locks
# LCK.vbe.locks           13740586         4.42 Lock Operations
# LCK.vbe.colls                  0         0.00 Collisions
# LCK.backend.creat              2         0.00 Created locks
# LCK.backend.destroy            0         0.00 Destroyed locks
# LCK.backend.locks       51685293        16.64 Lock Operations
# LCK.backend.colls              0         0.00 Collisions
# SMA.s0.c_req               13215         0.00 Allocator requests
# SMA.s0.c_fail                  0         0.00 Allocator failures
# SMA.s0.c_bytes         959888353       309.07 Bytes allocated
# SMA.s0.c_freed         959475615       308.94 Bytes freed
# SMA.s0.g_alloc                12          .   Allocations outstanding
# SMA.s0.g_bytes            412738          .   Bytes outstanding
# SMA.s0.g_space         268022718          .   Bytes available
# SMA.Transient.c_req     30821613         9.92 Allocator requests
# SMA.Transient.c_fail           0         0.00 Allocator failures
# SMA.Transient.c_bytes 2049827454520    660021.93 Bytes allocated
# SMA.Transient.c_freed 2049827454520    660021.93 Bytes freed
# SMA.Transient.g_alloc            0          .   Allocations outstanding
# SMA.Transient.g_bytes            0          .   Bytes outstanding
# SMA.Transient.g_space            0          .   Bytes available
# VBE.default(127.0.0.1,,81).vcls            1          .   VCL references
# VBE.default(127.0.0.1,,81).happy           0          .   Happy health probes
# VBE.name(xxx.xxx.xxx.xxx,,80).vcls            1          .   VCL references
# VBE.name(xxx.xxx.xxx.xxx,,80).happy           0          .   Happy health probes
# Newer agent output has MAIN and MGT prefix keys at the beginning
# and provide addtional sections MEMPOOL:
# (LCK, SMA, VBE has the same structure)
# MGT.uptime Management
# MGT.child_start Child
# MGT.child_exit Child
# MGT.child_stop Child
# MGT.child_died Child
# MGT.child_dump Child
# MGT.child_panic Child
# MAIN.summs stat
# MAIN.uptime Child
# MAIN.sess_conn Sessions
# MAIN.sess_drop Sessions
# MAIN.sess_fail Session
# MAIN.client_req_400 Client
# MAIN.client_req_417 Client
# MAIN.client_req Good
# MAIN.cache_hit Cache
# MAIN.cache_hitpass Cache
# MAIN.cache_hitmiss Cache
# MAIN.cache_miss Cache
# ...
# MEMPOOL.busyobj.live In
# MEMPOOL.busyobj.pool In
# MEMPOOL.busyobj.sz_wanted Size
# MEMPOOL.busyobj.sz_actual Size
# MEMPOOL.busyobj.allocs Allocations
# MEMPOOL.busyobj.frees Frees
# MEMPOOL.busyobj.recycle Recycled
# MEMPOOL.busyobj.timeout Timed
# MEMPOOL.busyobj.toosmall Too
# MEMPOOL.busyobj.surplus Too
# MEMPOOL.busyobj.randry Pool
# MEMPOOL.req0.live In
# MEMPOOL.req0.pool In
# MEMPOOL.req0.sz_wanted Size
# MEMPOOL.req0.sz_actual Size
# MEMPOOL.req0.allocs Allocations
# MEMPOOL.req0.frees Frees
# MEMPOOL.req0.recycle Recycled
# MEMPOOL.req0.timeout Timed
# MEMPOOL.req0.toosmall Too
# MEMPOOL.req0.surplus Too
# ...
# .
#   .--common--------------------------------------------------------------.
#   |                                                                      |
#   |               ___ ___  _ __ ___  _ __ ___   ___  _ __                |
#   |              / __/ _ \| '_ ` _ \| '_ ` _ \ / _ \| '_ \               |
#   |             | (_| (_) | | | | | | | | | | | (_) | | | |              |
#   |              \___\___/|_| |_| |_|_| |_| |_|\___/|_| |_|              |
#   |                                                                      |
#   '----------------------------------------------------------------------'
def parse_varnish(string_table):
    parsed = {}
    for line in string_table:
        parsed_path = _parse_path(line[0])
        instance = _create_hierarchy(parsed_path, parsed)
        try:
            value = int(line[1])
        except ValueError:
            value = None
        if line[3].lower() in line[0]:
            descr = " ".join(line[4:])
        else:
            descr = " ".join(line[3:])
        perf_var_name = "varnish_%s_rate" % parsed_path[-1]
        if perf_var_name.startswith("varnish_n_wrk"):
            perf_var_name = perf_var_name.replace("n_wrk", "worker")
        elif perf_var_name.startswith("varnish_n_"):
            perf_var_name = perf_var_name.replace("n_", "objects_")
        instance.update(
            {
                "value": value,
                "descr": descr.replace("/", " "),
                "perf_var_name": perf_var_name,
                "params_var_name": parsed_path[-1].split("_", 1)[-1],
            }
        )
    # Newer output has MAIN or MGT prefix keys,
    # see above in 'agent output'
    for key in ["MAIN", "MGT"]:
        values = parsed.pop(key, {})
        parsed.update(values)
    return parsed


def _parse_path(raw_path):
    # Split raw path on ".". We have to deal with different paths:
    # - 'client_conn'
    #   => ['client_conn']
    # - 'LCK.sms.creat'
    #   => ['LCK', 'sms', 'creat']
    # - 'VBE.default(127.0.0.1,,81).happy'
    #   => ['VBE', 'default(127.0.0.1,,81)', 'happy']
    if "(" not in raw_path:
        return raw_path.split(".")
    head, middle = raw_path.split("(", 1)
    address, tail = middle.split(")", 1)
    head = head.strip(".").split(".")
    return head[:-1] + [f"{head[-1]}({address})"] + tail.strip(".").split(".")


def _create_hierarchy(path, instance):
    if not path:
        return instance
    head, tail = path[0], path[1:]
    child = instance.setdefault(head, {})
    return _create_hierarchy(tail, child)


def inventory_varnish(parsed, needed_keys):
    if all(key in parsed for key in needed_keys):
        return [(None, {})]
    return []


def check_varnish_stats(_no_item, params, parsed, expected_keys):
    this_time = time.time()
    for key in expected_keys:
        data = parsed.get(key)
        if not data:
            continue
        descr_per_sec = "%s/s" % data["descr"]
        yield check_levels(
            get_rate(
                get_value_store(), "varnish.%s" % key, this_time, data["value"], raise_overflow=True
            ),
            data["perf_var_name"],
            params.get(data["params_var_name"], (None, None)),
            human_readable_func=lambda r, d=descr_per_sec: ("%.1f " + d) % r,
        )


def check_varnish_ratio(_no_item, params, parsed, ratio_keys):
    reference_key, additional_key, perf_key = ratio_keys
    reference_value = parsed[reference_key]["value"]
    ratio = 0.0
    total = reference_value + parsed[additional_key]["value"]
    if total > 0:
        ratio = 100.0 * reference_value / total
    warn, crit = params["levels_lower"]
    return check_levels(
        ratio, perf_key, (None, None, warn, crit), human_readable_func=render.percent
    )


# .
#   .--uptime--------------------------------------------------------------.
#   |                              _   _                                   |
#   |                  _   _ _ __ | |_(_)_ __ ___   ___                    |
#   |                 | | | | '_ \| __| | '_ ` _ \ / _ \                   |
#   |                 | |_| | |_) | |_| | | | | | |  __/                   |
#   |                  \__,_| .__/ \__|_|_| |_| |_|\___|                   |
#   |                       |_|                                            |
#   +----------------------------------------------------------------------+
#   |                             main check                               |
#   '----------------------------------------------------------------------'
def inventory_varnish_uptime(parsed):
    if "uptime" in parsed:
        return [(None, None)]
    return []


def check_varnish_uptime(_no_item, _no_params, parsed):
    if "uptime" in parsed:
        try:
            return check_uptime_seconds(_no_params, parsed["uptime"]["value"])
        except OverflowError:
            return (
                3,
                f"Could not handle uptime value {parsed['uptime']['value']!r}. "
                "Output of `varnishstats` seems to be faulty.",
            )
    return None


check_info["varnish"] = LegacyCheckDefinition(
    name="varnish",
    parse_function=parse_varnish,
    service_name="Varnish Uptime",
    discovery_function=inventory_varnish_uptime,
    check_function=check_varnish_uptime,
)


def discover_varnish_cache(parsed):
    return inventory_varnish(parsed, ["cache_miss"])


def check_varnish_cache(item, params, parsed):
    return check_varnish_stats(
        item,
        params,
        parsed,
        [
            "cache_miss",
            "cache_hit",
            "cache_hitpass",
        ],
    )


# .
#   .--cache---------------------------------------------------------------.
#   |                                     _                                |
#   |                       ___ __ _  ___| |__   ___                       |
#   |                      / __/ _` |/ __| '_ \ / _ \                      |
#   |                     | (_| (_| | (__| | | |  __/                      |
#   |                      \___\__,_|\___|_| |_|\___|                      |
#   |                                                                      |
#   '----------------------------------------------------------------------'
check_info["varnish.cache"] = LegacyCheckDefinition(
    name="varnish_cache",
    service_name="Varnish Cache",
    sections=["varnish"],
    discovery_function=discover_varnish_cache,
    check_function=check_varnish_cache,
    check_ruleset_name="varnish_cache",
)


def discover_varnish_client(parsed):
    return inventory_varnish(parsed, ["client_req"])


def check_varnish_client(item, params, parsed):
    return check_varnish_stats(
        item,
        params,
        parsed,
        [
            "client_drop",
            "client_req",
            "client_conn",
            "client_drop_late",
        ],
    )


# .
#   .--client--------------------------------------------------------------.
#   |                            _ _            _                          |
#   |                        ___| (_) ___ _ __ | |_                        |
#   |                       / __| | |/ _ \ '_ \| __|                       |
#   |                      | (__| | |  __/ | | | |_                        |
#   |                       \___|_|_|\___|_| |_|\__|                       |
#   |                                                                      |
#   '----------------------------------------------------------------------'
check_info["varnish.client"] = LegacyCheckDefinition(
    name="varnish_client",
    service_name="Varnish Client",
    sections=["varnish"],
    discovery_function=discover_varnish_client,
    check_function=check_varnish_client,
    check_ruleset_name="varnish_client",
)


def discover_varnish_backend(parsed):
    return inventory_varnish(parsed, ["backend_fail", "backend_unhealthy", "backend_busy"])


def check_varnish_backend(item, params, parsed):
    return check_varnish_stats(
        item,
        params,
        parsed,
        [
            "backend_busy",
            "backend_unhealthy",
            "backend_req",
            "backend_recycle",
            "backend_retry",
            "backend_fail",
            "backend_toolate",
            "backend_conn",
            "backend_reuse",
        ],
    )


# .
#   .--backend-------------------------------------------------------------.
#   |                _                _                  _                 |
#   |               | |__   __ _  ___| | _____ _ __   __| |                |
#   |               | '_ \ / _` |/ __| |/ / _ \ '_ \ / _` |                |
#   |               | |_) | (_| | (__|   <  __/ | | | (_| |                |
#   |               |_.__/ \__,_|\___|_|\_\___|_| |_|\__,_|                |
#   |                                                                      |
#   '----------------------------------------------------------------------'
check_info["varnish.backend"] = LegacyCheckDefinition(
    name="varnish_backend",
    service_name="Varnish Backend",
    sections=["varnish"],
    discovery_function=discover_varnish_backend,
    check_function=check_varnish_backend,
    check_ruleset_name="varnish_backend",
)


def discover_varnish_fetch(parsed):
    return inventory_varnish(
        parsed,
        [
            "fetch_1xx",
            "fetch_204",
            "fetch_304",
            "fetch_bad",
            "fetch_eof",
            "fetch_failed",
            "fetch_zero",
        ],
    )


def check_varnish_fetch(item, params, parsed):
    return check_varnish_stats(
        item,
        params,
        parsed,
        [
            "fetch_oldhttp",
            "fetch_head",
            "fetch_eof",
            "fetch_zero",
            "fetch_304",
            "fetch_length",
            "fetch_failed",
            "fetch_bad",
            "fetch_close",
            "fetch_1xx",
            "fetch_chunked",
            "fetch_204",
        ],
    )


# .
#   .--fetch---------------------------------------------------------------.
#   |                        __      _       _                             |
#   |                       / _| ___| |_ ___| |__                          |
#   |                      | |_ / _ \ __/ __| '_ \                         |
#   |                      |  _|  __/ || (__| | | |                        |
#   |                      |_|  \___|\__\___|_| |_|                        |
#   |                                                                      |
#   '----------------------------------------------------------------------'
check_info["varnish.fetch"] = LegacyCheckDefinition(
    name="varnish_fetch",
    service_name="Varnish Fetch",
    sections=["varnish"],
    discovery_function=discover_varnish_fetch,
    check_function=check_varnish_fetch,
    check_ruleset_name="varnish_fetch",
)


def discover_varnish_esi(parsed):
    return inventory_varnish(parsed, ["esi_errors"])


def check_varnish_esi(item, params, parsed):
    return check_varnish_stats(
        item,
        params,
        parsed,
        [
            "esi_errors",
            "esi_warnings",
        ],
    )


# .
#   .--ESI-----------------------------------------------------------------.
#   |                           _____ ____ ___                             |
#   |                          | ____/ ___|_ _|                            |
#   |                          |  _| \___ \| |                             |
#   |                          | |___ ___) | |                             |
#   |                          |_____|____/___|                            |
#   |                                                                      |
#   '----------------------------------------------------------------------'
check_info["varnish.esi"] = LegacyCheckDefinition(
    name="varnish_esi",
    service_name="Varnish ESI",
    sections=["varnish"],
    discovery_function=discover_varnish_esi,
    check_function=check_varnish_esi,
    check_ruleset_name="varnish_esi",
    check_default_parameters={"errors": (1.0, 2.0)},
)


def discover_varnish_objects(parsed):
    return inventory_varnish(parsed, ["n_expired", "n_lru_nuked"])


def check_varnish_objects(item, params, parsed):
    return check_varnish_stats(
        item,
        params,
        parsed,
        [
            "n_expired",
            "n_lru_nuked",
            "n_lru_moved",
        ],
    )


# .
#   .--objects-------------------------------------------------------------.
#   |                         _     _           _                          |
#   |                    ___ | |__ (_) ___  ___| |_ ___                    |
#   |                   / _ \| '_ \| |/ _ \/ __| __/ __|                   |
#   |                  | (_) | |_) | |  __/ (__| |_\__ \                   |
#   |                   \___/|_.__// |\___|\___|\__|___/                   |
#   |                            |__/                                      |
#   '----------------------------------------------------------------------'
check_info["varnish.objects"] = LegacyCheckDefinition(
    name="varnish_objects",
    service_name="Varnish Objects",
    sections=["varnish"],
    discovery_function=discover_varnish_objects,
    check_function=check_varnish_objects,
    check_ruleset_name="varnish_objects",
)


def discover_varnish_worker(parsed):
    return inventory_varnish(parsed, ["n_wrk_failed", "n_wrk_queued"])


def check_varnish_worker(item, params, parsed):
    return check_varnish_stats(
        item,
        params,
        parsed,
        [
            "n_wrk_lqueue",
            "n_wrk_create",
            "n_wrk_drop",
            "n_wrk",
            "n_wrk_failed",
            "n_wrk_queued",
            "n_wrk_max",
        ],
    )


# .
#   .--worker--------------------------------------------------------------.
#   |                                     _                                |
#   |                 __      _____  _ __| | _____ _ __                    |
#   |                 \ \ /\ / / _ \| '__| |/ / _ \ '__|                   |
#   |                  \ V  V / (_) | |  |   <  __/ |                      |
#   |                   \_/\_/ \___/|_|  |_|\_\___|_|                      |
#   |                                                                      |
#   '----------------------------------------------------------------------'
check_info["varnish.worker"] = LegacyCheckDefinition(
    name="varnish_worker",
    service_name="Varnish Worker",
    sections=["varnish"],
    discovery_function=discover_varnish_worker,
    check_function=check_varnish_worker,
    check_ruleset_name="varnish_worker",
)


def discover_varnish_cache_hit_ratio(parsed):
    return inventory_varnish(parsed, ["cache_miss", "cache_hit"])


def check_varnish_cache_hit_ratio(item, params, parsed):
    return check_varnish_ratio(item, params, parsed, ("cache_hit", "cache_miss", "cache_hit_ratio"))


# .
#   .--cache hit ratio-----------------------------------------------------.
#   |                  _            _     _ _               _   _          |
#   |    ___ __ _  ___| |__   ___  | |__ (_) |_   _ __ __ _| |_(_) ___     |
#   |   / __/ _` |/ __| '_ \ / _ \ | '_ \| | __| | '__/ _` | __| |/ _ \    |
#   |  | (_| (_| | (__| | | |  __/ | | | | | |_  | | | (_| | |_| | (_) |   |
#   |   \___\__,_|\___|_| |_|\___| |_| |_|_|\__| |_|  \__,_|\__|_|\___/    |
#   |                                                                      |
#   '----------------------------------------------------------------------'
check_info["varnish.cache_hit_ratio"] = LegacyCheckDefinition(
    name="varnish_cache_hit_ratio",
    service_name="Varnish Cache Hit Ratio",
    sections=["varnish"],
    discovery_function=discover_varnish_cache_hit_ratio,
    check_function=check_varnish_cache_hit_ratio,
    check_ruleset_name="varnish_cache_hit_ratio",
    check_default_parameters={"levels_lower": (70.0, 60.0)},
)


def discover_varnish_backend_success_ratio(parsed):
    return inventory_varnish(parsed, ["backend_fail", "backend_conn"])


def check_varnish_backend_success_ratio(item, params, parsed):
    return check_varnish_ratio(
        item, params, parsed, ("backend_conn", "backend_fail", "varnish_backend_success_ratio")
    )


# .
#   .--backend success ratio-----------------------------------------------.
#   |                _                _                  _                 |
#   |               | |__   __ _  ___| | _____ _ __   __| |                |
#   |               | '_ \ / _` |/ __| |/ / _ \ '_ \ / _` |                |
#   |               | |_) | (_| | (__|   <  __/ | | | (_| |                |
#   |               |_.__/ \__,_|\___|_|\_\___|_| |_|\__,_|                |
#   |                                                                      |
#   |                                                   _   _              |
#   |       ___ _   _  ___ ___ ___  ___ ___   _ __ __ _| |_(_) ___         |
#   |      / __| | | |/ __/ __/ _ \/ __/ __| | '__/ _` | __| |/ _ \        |
#   |      \__ \ |_| | (_| (_|  __/\__ \__ \ | | | (_| | |_| | (_) |       |
#   |      |___/\__,_|\___\___\___||___/___/ |_|  \__,_|\__|_|\___/        |
#   |                                                                      |
#   '----------------------------------------------------------------------'
check_info["varnish.backend_success_ratio"] = LegacyCheckDefinition(
    name="varnish_backend_success_ratio",
    service_name="Varnish Backend Success Ratio",
    sections=["varnish"],
    discovery_function=discover_varnish_backend_success_ratio,
    check_function=check_varnish_backend_success_ratio,
    check_ruleset_name="varnish_backend_success_ratio",
    check_default_parameters={"levels_lower": (70.0, 60.0)},
)
# .
#   .--worker thread ratio-------------------------------------------------.
#   |                     _               _   _                        _   |
#   | __      _____  _ __| | _____ _ __  | |_| |__  _ __ ___  __ _  __| |  |
#   | \ \ /\ / / _ \| '__| |/ / _ \ '__| | __| '_ \| '__/ _ \/ _` |/ _` |  |
#   |  \ V  V / (_) | |  |   <  __/ |    | |_| | | | | |  __/ (_| | (_| |  |
#   |   \_/\_/ \___/|_|  |_|\_\___|_|     \__|_| |_|_|  \___|\__,_|\__,_|  |
#   |                                                                      |
#   |                                  _   _                               |
#   |                        _ __ __ _| |_(_) ___                          |
#   |                       | '__/ _` | __| |/ _ \                         |
#   |                       | | | (_| | |_| | (_) |                        |
#   |                       |_|  \__,_|\__|_|\___/                         |
#   |                                                                      |
#   '----------------------------------------------------------------------'


def check_varnish_worker_thread_ratio(_no_item, params, parsed):
    ratio = 0.0
    worker_create = parsed["n_wrk_create"]["value"]
    if worker_create > 0:
        ratio = 100.0 * parsed["n_wrk"]["value"] / worker_create
    warn, crit = params["levels_lower"]
    return check_levels(
        ratio,
        "varnish_worker_thread_ratio",
        (None, None, warn, crit),
        human_readable_func=render.percent,
    )


def discover_varnish_worker_thread_ratio(parsed):
    return inventory_varnish(parsed, ["n_wrk", "n_wrk_create"])


check_info["varnish.worker_thread_ratio"] = LegacyCheckDefinition(
    name="varnish_worker_thread_ratio",
    service_name="Varnish Worker Thread Ratio",
    sections=["varnish"],
    discovery_function=discover_varnish_worker_thread_ratio,
    check_function=check_varnish_worker_thread_ratio,
    check_ruleset_name="varnish_worker_thread_ratio",
    check_default_parameters={"levels_lower": (70.0, 60.0)},
)
