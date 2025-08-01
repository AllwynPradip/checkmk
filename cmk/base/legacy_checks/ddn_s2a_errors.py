#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.


from cmk.agent_based.legacy.v0_unstable import LegacyCheckDefinition
from cmk.base.check_legacy_includes.ddn_s2a import parse_ddn_s2a_api_response

check_info = {}


def parse_ddn_s2a_errors(string_table):
    preparsed = parse_ddn_s2a_api_response(string_table)
    return {
        "port_type": preparsed["port_type"],
        "link_failure_errs": list(map(int, preparsed["link_failure_errs"])),
        "lost_sync_errs": list(map(int, preparsed["lost_sync_errs"])),
        "loss_of_signal_errs": list(map(int, preparsed["loss_of_sig_errs"])),
        "prim_seq_errs": list(map(int, preparsed["prim_seq_errs"])),
        "crc_errs": list(map(int, preparsed["CRC_errs"])),
        "receive_errs": list(map(int, preparsed["receive_errs"])),
        "ctio_timeouts": list(map(int, preparsed["CTIO_timeouts"])),
        "ctio_xmit_errs": list(map(int, preparsed["CTIO_xmit_errs"])),
        "ctio_other_errs": list(map(int, preparsed["CTIO_other_errs"])),
    }


def inventory_ddn_s2a_errors(parsed):
    def value_to_levels(value):
        # As the values in this check are all error counters since last reset,
        # we calculate default levels according to the current counter state,
        # so we'll be warned if an error occurs.
        return (value + 1, value + 5)

    for nr, port_type in enumerate(parsed["port_type"]):
        # Note: The API command returning the port errors that we evaluate
        #       in this check differentiates between FC and IB ports, providing
        #       different values according to port type. As we have no example
        #       for the IB ports at this time, we only implement logic for what
        #       we can test.
        if port_type == "FC":
            yield (
                "%d" % (nr + 1),
                {
                    "link_failure_errs": value_to_levels(parsed["link_failure_errs"][nr]),
                    "lost_sync_errs": value_to_levels(parsed["lost_sync_errs"][nr]),
                    "loss_of_signal_errs": value_to_levels(parsed["loss_of_signal_errs"][nr]),
                    "prim_seq_errs": value_to_levels(parsed["prim_seq_errs"][nr]),
                    "crc_errs": value_to_levels(parsed["crc_errs"][nr]),
                    "receive_errs": value_to_levels(parsed["receive_errs"][nr]),
                    "ctio_timeouts": value_to_levels(parsed["ctio_timeouts"][nr]),
                    "ctio_xmit_errs": value_to_levels(parsed["ctio_xmit_errs"][nr]),
                    "ctio_other_errs": value_to_levels(parsed["ctio_other_errs"][nr]),
                },
            )


def check_ddn_s2a_errors(item, params, parsed):
    def check_errors(value, levels, infotext_formatstring):
        infotext = infotext_formatstring % value
        if levels is None:
            return 0, infotext

        warn, crit = levels
        levelstext = " (warn/crit at %d/%d errors)" % (warn, crit)
        if value >= crit:
            status = 2
            infotext += levelstext
        elif value >= warn:
            status = 1
            infotext += levelstext
        else:
            status = 0
        return status, infotext

    nr = int(item) - 1
    link_failure_errs = parsed["link_failure_errs"][nr]
    lost_sync_errs = parsed["lost_sync_errs"][nr]
    loss_of_signal_errs = parsed["loss_of_signal_errs"][nr]
    prim_seq_errs = parsed["prim_seq_errs"][nr]
    crc_errs = parsed["crc_errs"][nr]
    receive_errs = parsed["receive_errs"][nr]
    ctio_timeouts = parsed["ctio_timeouts"][nr]
    ctio_xmit_errs = parsed["ctio_xmit_errs"][nr]
    ctio_other_errs = parsed["ctio_other_errs"][nr]

    yield check_errors(link_failure_errs, params["link_failure_errs"], "Link failure errors: %d")
    yield check_errors(lost_sync_errs, params["lost_sync_errs"], "Lost sync errors: %d")
    yield check_errors(
        loss_of_signal_errs, params["loss_of_signal_errs"], "Loss of signal errors: %d"
    )
    yield check_errors(
        prim_seq_errs, params["prim_seq_errs"], "PrimSeq errors: %d"
    )  # TODO: What is this?
    yield check_errors(crc_errs, params["crc_errs"], "CRC errors: %d")
    yield check_errors(receive_errs, params["receive_errs"], "Receive errors: %d")
    yield check_errors(ctio_timeouts, params["ctio_timeouts"], "CTIO timeouts: %d")
    yield check_errors(ctio_xmit_errs, params["ctio_xmit_errs"], "CTIO transmission errors: %d")
    yield check_errors(ctio_other_errs, params["ctio_other_errs"], "CTIO other errors: %d")


check_info["ddn_s2a_errors"] = LegacyCheckDefinition(
    name="ddn_s2a_errors",
    parse_function=parse_ddn_s2a_errors,
    service_name="DDN S2A Port Errors %s",
    discovery_function=inventory_ddn_s2a_errors,
    check_function=check_ddn_s2a_errors,
    check_ruleset_name="ddn_s2a_port_errors",
)
