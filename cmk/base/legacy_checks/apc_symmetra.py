#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.


# mypy: disable-error-code="var-annotated,arg-type,list-item"

import time

from cmk.agent_based.legacy.v0_unstable import LegacyCheckDefinition
from cmk.agent_based.v2 import render, SNMPTree
from cmk.base.check_legacy_includes.elphase import check_elphase
from cmk.base.check_legacy_includes.temperature import check_temperature
from cmk.plugins.lib.apc import DETECT

check_info = {}

# .1.3.6.1.4.1.318.1.1.1.2.1.1.0 2
# .1.3.6.1.4.1.318.1.1.1.4.1.1.0 2
# .1.3.6.1.4.1.318.1.1.1.11.1.1.0 0001010000000000001000000000000000000000000000000000000000000000
# .1.3.6.1.4.1.318.1.1.1.2.2.1.0 100
# .1.3.6.1.4.1.318.1.1.1.2.2.4.0 1
# .1.3.6.1.4.1.318.1.1.1.2.2.6.0 0
# .1.3.6.1.4.1.318.1.1.1.2.2.3.0 360000
# .1.3.6.1.4.1.318.1.1.1.7.2.6.0 2
# .1.3.6.1.4.1.318.1.1.1.7.2.4.0 0
# .1.3.6.1.4.1.318.1.1.1.2.2.2.0 25
# .1.3.6.1.4.1.318.1.1.1.2.2.9.0 0

# upsBasicStateOutputState:
# The flags are numbered 1 to 64, read from left to right. The flags are defined as follows:
# 1: Abnormal Condition Present, 2: On Battery, 3: Low Battery, 4: On Line
# 5: Replace Battery, 6: Serial Communication Established, 7: AVR Boost Active
# 8: AVR Trim Active, 9: Overload, 10: Runtime Calibration, 11: Batteries Discharged
# 12: Manual Bypass, 13: Software Bypass, 14: In Bypass due to Internal Fault
# 15: In Bypass due to Supply Failure, 16: In Bypass due to Fan Failure
# 17: Sleeping on a Timer, 18: Sleeping until Utility Power Returns
# 19: On, 20: Rebooting, 21: Battery Communication Lost, 22: Graceful Shutdown Initiated
# 23: Smart Boost or Smart Trim Fault, 24: Bad Output Voltage, 25: Battery Charger Failure
# 26: High Battery Temperature, 27: Warning Battery Temperature, 28: Critical Battery Temperature
# 29: Self Test In Progress, 30: Low Battery / On Battery, 31: Graceful Shutdown Issued by Upstream Device
# 32: Graceful Shutdown Issued by Downstream Device, 33: No Batteries Attached
# 34: Synchronized Command is in Progress, 35: Synchronized Sleeping Command is in Progress
# 36: Synchronized Rebooting Command is in Progress, 37: Inverter DC Imbalance
# 38: Transfer Relay Failure, 39: Shutdown or Unable to Transfer, 40: Low Battery Shutdown
# 41: Electronic Unit Fan Failure, 42: Main Relay Failure, 43: Bypass Relay Failure
# 44: Temporary Bypass, 45: High Internal Temperature, 46: Battery Temperature Sensor Fault
# 47: Input Out of Range for Bypass, 48: DC Bus Overvoltage, 49: PFC Failure
# 50: Critical Hardware Fault, 51: Green Mode/ECO Mode, 52: Hot Standby
# 53: Emergency Power Off (EPO) Activated, 54: Load Alarm Violation, 55: Bypass Phase Fault
# 56: UPS Internal Communication Failure, 57-64: <Not Used>


def parse_apc_symmetra(string_table):
    sensor_info, string_table = string_table
    parsed = {}

    for name, temp in sensor_info:
        parsed.setdefault("temp", {})[name] = int(temp)

    if not string_table:
        return parsed

    # some numeric fields may be empty
    (
        ups_comm_status,
        battery_status,
        output_status,
        battery_capacity,
        battery_replace,
        battery_num_batt_packs,
        battery_time_remain,
        calib_result,
        last_diag_date,
        battery_temp,
        battery_current,
        state_output_state,
    ) = string_table[0]

    if state_output_state != "":
        # string contains a bitmask, convert to int
        output_state_bitmask = int(state_output_state, 2)
    else:
        output_state_bitmask = 0
    self_test_in_progress = output_state_bitmask & 1 << 35 != 0

    for key, val in [
        ("ups_comm_status", ups_comm_status),
        ("status", battery_status),
        ("output", output_status),
        ("self_test", self_test_in_progress),
        ("capacity", battery_capacity),
        ("replace", battery_replace),
        ("num_packs", battery_num_batt_packs),
        ("time_remain", battery_time_remain),
        ("calib", calib_result),
        ("diag_date", last_diag_date),
    ]:
        if val:
            parsed.setdefault("status", {})
            parsed["status"][key] = val

    if battery_temp:
        parsed.setdefault("temp", {})["Battery"] = float(battery_temp)

    if battery_current:
        parsed["elphase"] = {"Battery": {"current": float(battery_current)}}

    return parsed


#   .--battery status------------------------------------------------------.
#   |   _           _   _                        _        _                |
#   |  | |__   __ _| |_| |_ ___ _ __ _   _   ___| |_ __ _| |_ _   _ ___    |
#   |  | '_ \ / _` | __| __/ _ \ '__| | | | / __| __/ _` | __| | | / __|   |
#   |  | |_) | (_| | |_| ||  __/ |  | |_| | \__ \ || (_| | |_| |_| \__ \   |
#   |  |_.__/ \__,_|\__|\__\___|_|   \__, | |___/\__\__,_|\__|\__,_|___/   |
#   |                                |___/                                 |
#   '----------------------------------------------------------------------'

# old format:
# apc_default_levels = ( 95, 40, 1, 220 )  or  { "levels" : ( 95, 40, 1, 220 ) }
# crit_capacity, crit_sys_temp, crit_batt_curr, crit_voltage = levels
# Temperature default now 60C: regadring to a apc technician a temperature up tp 70C is possible


def inventory_apc_symmetra(parsed):
    if "status" in parsed:
        yield None, {}


def check_apc_symmetra(_no_item, params, parsed):
    data = parsed.get("status")
    if data is None:
        return

    if data.get("ups_comm_status") == "2":
        yield 3, "UPS communication lost"

    battery_status = data.get("status")
    output_status = data.get("output")
    self_test_in_progress = data.get("self_test")
    battery_capacity = data.get("capacity")
    battery_replace = data.get("replace")
    battery_num_batt_packs = data.get("num_packs")
    battery_time_remain = data.get("time_remain")
    calib_result = data.get("calib")
    last_diag_date = data.get("diag_date")

    alt_crit_capacity = None
    # the last_diag_date is reported as %m/%d/%Y or %y
    if (
        params.get("post_calibration_levels")
        and last_diag_date not in [None, "Unknown"]
        and len(last_diag_date) in [8, 10]
    ):
        year_format = "%y" if len(last_diag_date) == 8 else "%Y"
        last_ts = time.mktime(time.strptime(last_diag_date, "%m/%d/" + year_format))
        diff_sec = time.time() - last_ts
        allowed_delay_sec = 86400 + params["post_calibration_levels"]["additional_time_span"]
        alt_crit_capacity = params["post_calibration_levels"]["altcapacity"]

    state, state_readable = {
        "1": (3, "unknown"),
        "2": (0, "normal"),
        "3": (2, "low"),
        "4": (2, "in fault condition"),
    }.get(battery_status, (3, "unexpected(%s)" % battery_status))
    yield state, "Battery status: %s" % state_readable

    if battery_replace:
        state, state_readable = {
            "1": (0, "No battery needs replacing"),
            "2": (params["battery_replace_state"], "Battery needs replacing"),
        }.get(battery_replace, (3, "Battery needs replacing: unknown"))
        if battery_num_batt_packs and int(battery_num_batt_packs) > 1:
            yield 2, "%i batteries need replacing" % int(battery_num_batt_packs)
        elif state:
            yield state, state_readable

    if output_status:
        output_status_txts = {
            "1": "unknown",
            "2": "on line",
            "3": "on battery",
            "4": "on smart boost",
            "5": "timed sleeping",
            "6": "software bypass",
            "7": "off",
            "8": "rebooting",
            "9": "switched bypass",
            "10": "hardware failure bypass",
            "11": "sleeping until power return",
            "12": "on smart trim",
            "13": "eco mode",
            "14": "hot standby",
            "15": "on battery test",
            "16": "emergency static bypass",
            "17": "static bypass standby",
            "18": "power saving mode",
            "19": "spot mode",
            "20": "e conversion",
        }
        state_readable = output_status_txts.get(output_status, "unexpected(%s)" % output_status)

        if output_status not in output_status_txts:
            state = 3
        elif (
            output_status not in ["2", "4", "12"]
            and calib_result != "3"
            and not self_test_in_progress
        ):
            state = 2
        elif (
            output_status in ["2", "4", "12"] and calib_result == "2" and not self_test_in_progress
        ):
            state = params.get("calibration_state")
        else:
            state = 0

        calib_text = {
            "1": "",
            "2": " (calibration invalid)",
            "3": " (calibration in progress)",
        }.get(calib_result, " (calibration unexpected(%s))" % calib_result)

        yield (
            state,
            "Output status: {}{}{}".format(
                state_readable,
                calib_text,
                " (self-test running)" if self_test_in_progress else "",
            ),
        )

    if battery_capacity:
        battery_capacity = int(battery_capacity)
        warn_cap, crit_cap = params["capacity"]
        state = 0
        levelstxt = ""
        if alt_crit_capacity is not None and diff_sec < allowed_delay_sec:
            if battery_capacity < alt_crit_capacity:
                state = 2
                levelstxt = " (crit below %d%% in delay after calibration)" % alt_crit_capacity
        elif battery_capacity < crit_cap:
            state = 2
            levelstxt = f" (warn/crit below {warn_cap:.1f}%/{crit_cap:.1f}%)"
        elif battery_capacity < warn_cap:
            state = 1
            levelstxt = f" (warn/crit below {warn_cap:.1f}%/{crit_cap:.1f}%)"

        yield (
            state,
            "Capacity: %d%%%s" % (battery_capacity, levelstxt),
            [("capacity", battery_capacity, warn_cap, crit_cap, 0, 100)],
        )

    if battery_time_remain:
        battery_time_remain = float(battery_time_remain) / 100.0
        battery_time_remain_readable = render.timespan(battery_time_remain)
        state = 0
        levelstxt = ""
        battery_time_warn, battery_time_crit = None, None
        if params.get("battime"):
            battery_time_warn, battery_time_crit = params["battime"]
            if battery_time_remain < battery_time_crit:
                state = 2
            elif battery_time_remain < battery_time_warn:
                state = 1
            perfdata = [
                (
                    "runtime",
                    battery_time_remain / 60.0,
                    battery_time_warn / 60.0,
                    battery_time_crit / 60.0,
                )
            ]
        else:
            perfdata = [("runtime", battery_time_remain / 60.0)]

        if state:
            levelstxt = f" (warn/crit below {render.timespan(battery_time_warn)}/{render.timespan(battery_time_crit)})"

        yield state, f"Time remaining: {battery_time_remain_readable}{levelstxt}", perfdata


check_info["apc_symmetra"] = LegacyCheckDefinition(
    name="apc_symmetra",
    detect=DETECT,
    fetch=[
        SNMPTree(
            base=".1.3.6.1.4.1.318.1.1.10.4.2.3.1",
            oids=["3", "5"],
        ),
        SNMPTree(
            base=".1.3.6.1.4.1.318.1.1.1",
            oids=[
                "8.1.0",
                "2.1.1.0",
                "4.1.1.0",
                "2.2.1.0",
                "2.2.4.0",
                "2.2.6.0",
                "2.2.3.0",
                "7.2.6.0",
                "7.2.4.0",
                "2.2.2.0",
                "2.2.9.0",
                "11.1.1.0",
            ],
        ),
    ],
    parse_function=parse_apc_symmetra,
    service_name="APC Symmetra status",
    discovery_function=inventory_apc_symmetra,
    check_function=check_apc_symmetra,
    check_ruleset_name="apc_symentra",
    check_default_parameters={
        "capacity": (95.0, 80.0),
        "calibration_state": 0,
        "battery_replace_state": 1,
    },
)

# .
#   .--temperature---------------------------------------------------------.
#   |      _                                      _                        |
#   |     | |_ ___ _ __ ___  _ __   ___ _ __ __ _| |_ _   _ _ __ ___       |
#   |     | __/ _ \ '_ ` _ \| '_ \ / _ \ '__/ _` | __| | | | '__/ _ \      |
#   |     | ||  __/ | | | | | |_) |  __/ | | (_| | |_| |_| | | |  __/      |
#   |      \__\___|_| |_| |_| .__/ \___|_|  \__,_|\__|\__,_|_|  \___|      |
#   |                       |_|                                            |
#   '----------------------------------------------------------------------'

# Temperature default now 60C: regadring to a apc technician a temperature up tp 70C is possible


def inventory_apc_symmetra_temp(parsed):
    return [(k, {}) for k in parsed.get("temp", {})]


def check_apc_symmetra_temp(item, params, parsed):
    reading = parsed.get("temp", {}).get(item)
    if reading is None:
        return None

    if "levels" not in params:
        params_copy = params.copy()
        default_key = "levels_battery" if item == "Battery" else "levels_sensors"
        params_copy["levels"] = params[default_key]
        params = params_copy

    name_temp = "check_apc_symmetra_temp.%s" if item == "Battery" else "apc_temp_%s"
    return check_temperature(reading, params, name_temp % item)


check_info["apc_symmetra.temp"] = LegacyCheckDefinition(
    name="apc_symmetra_temp",
    service_name="Temperature %s",
    sections=["apc_symmetra"],
    discovery_function=inventory_apc_symmetra_temp,
    check_function=check_apc_symmetra_temp,
    check_ruleset_name="temperature",
    check_default_parameters={
        # This is very unorthodox, and requires special handling in the
        # wato ruleset. A dedicated service would have been the better choice.
        "levels_battery": (50, 60),
        "levels_sensors": (25, 30),
    },
)

# .
#   .--el phase------------------------------------------------------------.
#   |                      _         _                                     |
#   |                  ___| |  _ __ | |__   __ _ ___  ___                  |
#   |                 / _ \ | | '_ \| '_ \ / _` / __|/ _ \                 |
#   |                |  __/ | | |_) | | | | (_| \__ \  __/                 |
#   |                 \___|_| | .__/|_| |_|\__,_|___/\___|                 |
#   |                         |_|                                          |
#   '----------------------------------------------------------------------'


def inventory_apc_symmetra_elphase(parsed):
    for phase in parsed.get("elphase", {}):
        yield phase, {}


def check_apc_symmetra_elphase(item, params, parsed):
    return check_elphase(item, params, parsed.get("elphase", {}))


check_info["apc_symmetra.elphase"] = LegacyCheckDefinition(
    name="apc_symmetra_elphase",
    service_name="Phase %s",
    sections=["apc_symmetra"],
    discovery_function=inventory_apc_symmetra_elphase,
    check_function=check_apc_symmetra_elphase,
    check_ruleset_name="ups_outphase",
    check_default_parameters={},
)
