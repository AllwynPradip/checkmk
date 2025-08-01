#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

import enum
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal, NewType, TypedDict

from cmk.agent_based.v1 import check_levels as check_levels_v1
from cmk.agent_based.v2 import (
    all_of,
    CheckPlugin,
    CheckResult,
    DiscoveryResult,
    Metric,
    not_matches,
    OIDEnd,
    render,
    Result,
    Service,
    SNMPSection,
    SNMPTree,
    State,
    StringTable,
)
from cmk.plugins.lib.constants import OID_SYS_OBJ
from cmk.plugins.lib.printer import DETECT_PRINTER

MAP_UNIT: Final = {
    "3": "ten thousandths of inches",
    "4": "micrometers",
    "7": "impressions",
    "8": "sheets",
    "11": "hours",
    "12": "thousandths of ounces",
    "13": "tenths of grams",
    "14": "hundreths of fluid ounces",
    "15": "tenths of milliliters",
    "16": "feet",
    "17": "meters",
    "18": "items",
    "19": "%",
}

# Supported languages: English, German, French, and Spanish.
VALID_BLACK_WORDS = ("black", "schwarz", "noir", "negra")
VALID_CYAN_WORDS = ("cyan", "zyan", "cian")
VALID_MAGENTA_WORDS = ("magenta",)
VALID_YELLOW_WORDS = ("yellow", "gelb", "jaune", "amarilla")


Unit = NewType("Unit", str)

type Color = Literal["black", "cyan", "magenta", "yellow"]


class SupplyClass(enum.Enum):
    CONTAINER = enum.auto()
    RECEPTACLE = enum.auto()


@dataclass(frozen=True)
class PrinterSupply:
    unit: Unit
    max_capacity: int
    level: int
    supply_class: SupplyClass
    color: Color | None

    @property
    def capacity_unrestricted(self) -> bool:
        return self.max_capacity == -1

    @property
    def capacity_unknown(self) -> bool:
        return self.max_capacity == -2

    @property
    def level_unrestricted(self) -> bool:
        return self.level == -1

    @property
    def level_unknown(self) -> bool:
        return self.level == -2

    @property
    def some_level_remains(self) -> bool:
        return self.level == -3

    @property
    def has_partial_data(self) -> bool:
        return (
            self.capacity_unknown
            or self.level_unrestricted
            or self.level_unknown
            or self.some_level_remains
        )


Section = dict[str, PrinterSupply]


def _get_oid_end_last_index(oid_end: str) -> str:
    # return last number of OID_END
    return oid_end.split(".")[-1]


def _get_supply_unit(raw_unit: str) -> Unit:
    unit = MAP_UNIT.get(raw_unit, "")
    return Unit(unit) if unit in {"", "%"} else Unit(f" {unit}")


def _get_supply_color(raw_color: str, raw_description: str) -> Color | None:
    color = raw_color.lower()
    description = raw_description.lower()

    if color == "black" or any(word in description for word in VALID_BLACK_WORDS):
        return "black"

    if color == "cyan" or any(word in description for word in VALID_CYAN_WORDS):
        return "cyan"

    if color == "magenta" or any(word in description for word in VALID_MAGENTA_WORDS):
        return "magenta"

    if color == "yellow" or any(word in description for word in VALID_YELLOW_WORDS):
        return "yellow"

    return None


def _get_supply_class(raw_supply_class: str) -> SupplyClass:
    # When unit type is
    # 1 = other
    # 3 = supplyThatIsConsumed
    # 4 = supplyThatIsFilled
    # the value is contains the current level if this supply is a container
    # but when the remaining space if this supply is a receptacle
    #
    # This table can be missing on some devices. Assume type 3 in this case.
    return SupplyClass.RECEPTACLE if raw_supply_class == "4" else SupplyClass.CONTAINER


def parse_printer_supply(string_table: Sequence[StringTable]) -> Section:
    if len(string_table) < 2:
        return {}

    parsed = {}
    colors = []

    color_mapping = {_get_oid_end_last_index(oid_end): value for oid_end, value in string_table[0]}

    for index, (
        name,
        raw_unit,
        raw_max_capacity,
        raw_level,
        raw_supply_class,
        color_id,
    ) in enumerate(string_table[1]):
        try:
            max_capacity = int(raw_max_capacity)
            level = int(raw_level)
        except ValueError:
            continue
        # Ignore devices which show -2 for current value and -2 for max value -> useless
        if max_capacity == -2 and level == -2:
            continue

        # Assume 100% as maximum when 0 is reported
        # Saw some toner cartridge reporting value=0 and max_capacity=0 on empty toner
        if max_capacity == 0:
            max_capacity = 100

        raw_color = color_mapping.get(color_id, "")
        # For toners or drum units add the color (if available)
        if name.startswith("Toner Cartridge") or name.startswith("Image Drum Unit"):
            if raw_color:
                colors += [raw_color]
            elif raw_color == "" and colors:
                raw_color = colors[index - len(colors)]
            if raw_color:
                name = f"{raw_color.title()} {name}"

        # fix trailing zero bytes (seen on HP Jetdirect 143 and 153)
        description = name.split(" S/N:")[0].strip("\0")
        raw_color = raw_color.rstrip("\0")

        unit = _get_supply_unit(raw_unit)
        color = _get_supply_color(raw_color, description)
        supply_class = _get_supply_class(raw_supply_class)

        parsed[description] = PrinterSupply(unit, max_capacity, level, supply_class, color)

    return parsed


snmp_section_printer_supply = SNMPSection(
    name="printer_supply",
    detect=all_of(DETECT_PRINTER, not_matches(OID_SYS_OBJ, ".1.3.6.1.4.1.367.1.1")),
    parse_function=parse_printer_supply,
    fetch=[
        SNMPTree(
            base=".1.3.6.1.2.1.43.12.1.1",
            oids=[
                OIDEnd(),
                "4",  # Printer-MIB::prtMarkerColorantValue
            ],
        ),
        SNMPTree(
            base=".1.3.6.1.2.1.43.11.1.1",
            oids=[
                "6",  # Printer-MIB::prtMarkerSuppliesDescription
                "7",  # Printer-MIB::prtMarkerSuppliesUnit
                "8",  # Printer-MIB::prtMarkerSuppliesMaxCapacity
                "9",  # Printer-MIB::prtMarkerSuppliesLevel
                "4",  # Printer-MIB::prtMarkerSuppliesClass
                "3",  # Printer-MIB:prtMarkerSuppliesColorantIndex
            ],
        ),
    ],
)


def discovery_printer_supply(section: Section) -> DiscoveryResult:
    for key in section.keys():
        yield Service(item=key)


class CheckParams(TypedDict):
    levels: tuple[float, float]
    upturn_toner: bool
    some_remaining_ink: int
    some_remaining_space: int


def check_printer_supply(item: str, params: CheckParams, section: Section) -> CheckResult:
    if (supply := section.get(item)) is None:
        return

    color_info = _get_supply_color_info(item, supply.color)
    metric_name = f"supply_toner_{supply.color or 'other'}"

    if supply.has_partial_data:  # no percentage possible
        yield from _get_partial_data_results(supply, params, color_info, metric_name)
        return

    yield from check_levels_v1(
        _get_fill_level_percentage(supply, params["upturn_toner"]),
        metric_name=metric_name,
        levels_lower=params["levels"],
        label="Supply level remaining",
        render_func=render.percent,
    )

    if supply.unit not in {"", "%"}:
        yield Result(
            state=State.OK,
            summary=f"Supply: {supply.level} of max. {supply.max_capacity}{supply.unit}",
        )


def _get_supply_color_info(item: str, color: Color | None) -> str:
    return f"[{color}] " if color and color not in item.lower() else ""


def _get_partial_data_results(
    supply: PrinterSupply, params: CheckParams, color_info: str, metric_name: str
) -> CheckResult:
    if supply.level_unrestricted or supply.capacity_unrestricted:
        summary = "%sThere are no restrictions on this supply" % color_info
        yield Result(state=State.OK, summary=summary)

    elif supply.some_level_remains:
        match supply.supply_class:
            case SupplyClass.CONTAINER:
                yield Result(
                    state=State(params["some_remaining_ink"]),
                    summary=f"{color_info}Some ink remaining",
                )
            case SupplyClass.RECEPTACLE:
                yield Result(
                    state=State(params["some_remaining_space"]),
                    summary=f"{color_info}Some space remaining",
                )

    elif supply.level_unknown:
        yield Result(state=State.UNKNOWN, summary="%s Unknown level" % color_info)

    elif supply.capacity_unknown:
        yield Result(state=State.OK, summary="Supply: %d%s" % (supply.level, supply.unit))
        yield Metric(metric_name, supply.level)


def _get_fill_level_percentage(supply: PrinterSupply, upturn_toner: bool) -> float:
    fill_level_percentage = 100.0 * supply.level / supply.max_capacity

    if supply.supply_class is SupplyClass.RECEPTACLE:
        # We expect a receptacle (like a waste container) to display used space that counts up.
        # Since we handle all percentages as "supply left", we turn the percentage upside down.
        fill_level_percentage = 100 - fill_level_percentage

    if upturn_toner:
        # This option must always upturn the applying logic.
        # Otherwise, we wouldn't catch a receptacle that shows space left instead of space used.
        return 100 - fill_level_percentage

    return fill_level_percentage


check_plugin_printer_supply = CheckPlugin(
    name="printer_supply",
    service_name="Supply %s",
    discovery_function=discovery_printer_supply,
    check_function=check_printer_supply,
    check_ruleset_name="printer_supply",
    check_default_parameters=CheckParams(
        levels=(20.0, 10.0),
        upturn_toner=False,
        some_remaining_ink=State.WARN.value,
        some_remaining_space=State.WARN.value,
    ),
)
