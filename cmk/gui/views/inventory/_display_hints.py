#!/usr/bin/env python3
# Copyright (C) 2023 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal, TypeAlias

from cmk.gui import inventory
from cmk.gui.i18n import _, _l
from cmk.gui.inventory.filters import (
    FilterInvBool,
    FilterInvFloat,
    FilterInvtableAdminStatus,
    FilterInvtableAvailable,
    FilterInvtableIntegerRange,
    FilterInvtableInterfaceType,
    FilterInvtableOperStatus,
    FilterInvtableText,
    FilterInvtableTimestampAsAge,
    FilterInvtableVersion,
    FilterInvText,
)
from cmk.utils.structured_data import SDKey, SDPath

from .registry import (
    inv_paint_funtions,
    InventoryHintSpec,
    InvValue,
    PaintFunction,
    SortFunction,
)


@dataclass(frozen=True)
class _RelatedLegacyHints:
    for_node: InventoryHintSpec = field(default_factory=lambda: InventoryHintSpec())
    for_table: InventoryHintSpec = field(default_factory=lambda: InventoryHintSpec())
    by_column: dict[str, InventoryHintSpec] = field(default_factory=dict)
    by_key: dict[str, InventoryHintSpec] = field(default_factory=dict)


def _get_related_legacy_hints(
    legacy_hints: Mapping[str, InventoryHintSpec],
) -> Mapping[SDPath, _RelatedLegacyHints]:
    related_legacy_hints_by_path: dict[SDPath, _RelatedLegacyHints] = {}
    for raw_path, legacy_hint in legacy_hints.items():
        inventory_path = inventory.parse_internal_raw_path(raw_path)
        related_legacy_hints = related_legacy_hints_by_path.setdefault(
            inventory_path.path,
            _RelatedLegacyHints(),
        )

        if inventory_path.source == inventory.TreeSource.node:
            related_legacy_hints.for_node.update(legacy_hint)
            continue

        if inventory_path.source == inventory.TreeSource.table:
            if inventory_path.key:
                related_legacy_hints.by_column.setdefault(inventory_path.key, legacy_hint)
                continue

            related_legacy_hints.for_table.update(legacy_hint)
            continue

        if inventory_path.source == inventory.TreeSource.attributes and inventory_path.key:
            related_legacy_hints.by_key.setdefault(inventory_path.key, legacy_hint)
            continue

    return related_legacy_hints_by_path


PAINT_FUNCTION_NAME_PREFIX = "inv_paint_"


def _get_paint_function(legacy_hint: InventoryHintSpec) -> tuple[str, PaintFunction]:
    # FIXME At the moment  we need it to get tdclass: Clean this up one day.
    if "paint" in legacy_hint:
        data_type = legacy_hint["paint"]
        return data_type, inv_paint_funtions[PAINT_FUNCTION_NAME_PREFIX + data_type]["func"]
    return "str", inv_paint_funtions["inv_paint_generic"]["func"]


def _make_sort_function(legacy_hint: InventoryHintSpec) -> SortFunction:
    return _decorate_sort_function(legacy_hint.get("sort", _cmp_inv_generic))


def _decorate_sort_function(sort_function: SortFunction) -> SortFunction:
    def wrapper(val_a: InvValue | None, val_b: InvValue | None) -> int:
        if val_a is None:
            return 0 if val_b is None else -1

        if val_b is None:
            return 0 if val_a is None else 1

        return sort_function(val_a, val_b)

    return wrapper


def _cmp_inv_generic(val_a: InvValue, val_b: InvValue) -> int:
    return (val_a > val_b) - (val_a < val_b)


def _make_title_function(legacy_hint: InventoryHintSpec) -> Callable[[str], str]:
    if "title" not in legacy_hint:
        return lambda word: word.replace("_", " ").title()

    if callable(title := legacy_hint["title"]):
        # TODO Do we still need this?
        return title

    return lambda word: str(title)


def _make_long_title(parent_title: str, title: str) -> str:
    return parent_title + " ➤ " + title if parent_title else title


def _make_node_ident(path: SDPath) -> str:
    return "_".join(["inv"] + list(path))


def _make_attr_ident(node_ident: str, key: SDKey | str) -> str:
    return f"{node_ident}_{key}"


def _make_col_ident(table_view_name: str, key: SDKey | str) -> str:
    return f"{table_view_name}_{key}" if table_view_name else ""


def _make_attribute_filter(
    *, path: SDPath, key: str, data_type: str, ident: str, long_title: str, is_show_more: bool
) -> FilterInvText | FilterInvBool | FilterInvFloat:
    inventory_path = inventory.InventoryPath(
        path=path,
        source=inventory.TreeSource.attributes,
        key=SDKey(key),
    )
    match data_type:
        case "str":
            return FilterInvText(
                ident=ident,
                title=long_title,
                inventory_path=inventory_path,
                is_show_more=is_show_more,
            )
        case "bool":
            return FilterInvBool(
                ident=ident,
                title=long_title,
                inventory_path=inventory_path,
                is_show_more=is_show_more,
            )
        case "bytes" | "bytes_rounded":
            unit = _("MB")
            scale = 1024 * 1024
        case "hz":
            unit = _("MHz")
            scale = 1000000
        case "volt":
            unit = _("Volt")
            scale = 1
        case "timestamp":
            unit = _("secs")
            scale = 1
        case _:
            unit = ""
            scale = 1

    return FilterInvFloat(
        ident=ident,
        title=long_title,
        inventory_path=inventory_path,
        unit=unit,
        scale=scale,
        is_show_more=is_show_more,
    )


def _parse_attribute_hint(
    path: SDPath, node_ident: str, node_title: str, key: str, legacy_hint: InventoryHintSpec
) -> AttributeDisplayHint:
    data_type, paint_function = _get_paint_function(legacy_hint)
    ident = _make_attr_ident(node_ident, key)
    title = _make_title_function(legacy_hint)(key)
    long_title = _make_long_title(node_title, title)
    return AttributeDisplayHint(
        ident=ident,
        title=title,
        short_title=(
            title if (short_title := legacy_hint.get("short")) is None else str(short_title)
        ),
        long_title=long_title,
        paint_function=paint_function,
        sort_function=_make_sort_function(legacy_hint),
        filter=_make_attribute_filter(
            path=path,
            key=key,
            data_type=data_type,
            ident=ident,
            long_title=long_title,
            is_show_more=legacy_hint.get("is_show_more", True),
        ),
    )


def _parse_column_display_hint_filter_class(
    filter_class: (
        None
        | type[FilterInvText]
        | type[FilterInvBool]
        | type[FilterInvFloat]
        | type[FilterInvtableAdminStatus]
        | type[FilterInvtableAvailable]
        | type[FilterInvtableIntegerRange]
        | type[FilterInvtableInterfaceType]
        | type[FilterInvtableOperStatus]
        | type[FilterInvtableText]
        | type[FilterInvtableTimestampAsAge]
        | type[FilterInvtableVersion]
    ),
) -> (
    type[FilterInvtableAdminStatus]
    | type[FilterInvtableAvailable]
    | type[FilterInvtableIntegerRange]
    | type[FilterInvtableInterfaceType]
    | type[FilterInvtableOperStatus]
    | type[FilterInvtableText]
    | type[FilterInvtableTimestampAsAge]
    | type[FilterInvtableVersion]
):
    if not filter_class:
        return FilterInvtableText
    match filter_class.__name__:
        case "FilterInvtableAdminStatus":
            return FilterInvtableAdminStatus
        case "FilterInvtableAvailable":
            return FilterInvtableAvailable
        case "FilterInvtableIntegerRange":
            return FilterInvtableIntegerRange
        case "FilterInvtableInterfaceType":
            return FilterInvtableInterfaceType
        case "FilterInvtableOperStatus":
            return FilterInvtableOperStatus
        case "FilterInvtableText":
            return FilterInvtableText
        case "FilterInvtableTimestampAsAge":
            return FilterInvtableTimestampAsAge
        case "FilterInvtableVersion":
            return FilterInvtableVersion
    raise TypeError(filter_class)


def _parse_column_hint(
    table_view_name: str,
    node_title: str,
    key: str,
    legacy_hint: InventoryHintSpec,
) -> ColumnDisplayHint:
    _data_type, paint_function = _get_paint_function(legacy_hint)
    title = _make_title_function(legacy_hint)(key)
    return ColumnDisplayHint(
        ident=_make_col_ident(table_view_name, key),
        title=title,
        short_title=(
            title if (short_title := legacy_hint.get("short")) is None else str(short_title)
        ),
        long_title=_make_long_title(node_title, title),
        paint_function=paint_function,
        sort_function=_make_sort_function(legacy_hint),
        filter_class=_parse_column_display_hint_filter_class(legacy_hint.get("filter")),
    )


def _parse_view_name(view_name: str) -> str:
    if not view_name:
        return ""
    if not view_name.startswith("inv"):
        view_name = f"inv{view_name}"
    if view_name.endswith("_of_host"):
        view_name = view_name[:-8]
    return view_name


def _complete_key_order(key_order: Sequence[str], additional_keys: set[str]) -> Sequence[str]:
    return list(key_order) + [key for key in sorted(additional_keys) if key not in key_order]


@dataclass(frozen=True)
class _NodeDisplayHint:
    ident: str
    path: SDPath
    title: str
    short_title: str
    icon: str
    attributes: OrderedAttributeDisplayHints
    columns: OrderedColumnDisplayHints
    table_view_name: str
    table_is_show_more: bool


def _parse_node_hint(
    path: SDPath,
    legacy_hint: InventoryHintSpec,
    attributes_key_order: Sequence[str],
    attributes: Mapping[str, InventoryHintSpec],
    table_key_order: Sequence[str],
    columns: Mapping[str, InventoryHintSpec],
) -> _NodeDisplayHint:
    ident = _make_node_ident(path)
    title = _make_title_function(legacy_hint)(path[-1] if path else "")
    table_view_name = "" if "*" in path else _parse_view_name(legacy_hint.get("view", ""))
    return _NodeDisplayHint(
        ident=ident,
        path=path,
        title=title,
        short_title=title,
        icon=legacy_hint.get("icon", ""),
        attributes={
            SDKey(key): _parse_attribute_hint(path, ident, title, key, attributes.get(key, {}))
            for key in _complete_key_order(attributes_key_order, set(attributes))
        },
        columns={
            SDKey(key): _parse_column_hint(table_view_name, title, key, columns.get(key, {}))
            for key in _complete_key_order(table_key_order, set(columns))
        },
        table_view_name=table_view_name,
        table_is_show_more=legacy_hint.get("is_show_more", True),
    )


# TODO Workaround for InventoryHintSpec (TypedDict)
# https://github.com/python/mypy/issues/7178
_ALLOWED_KEYS: Sequence[
    Literal[
        "title",
        "short",
        "icon",
        "paint",
        "view",
        "keyorder",
        "sort",
        "filter",
        "is_show_more",
    ]
] = [
    "title",
    "short",
    "icon",
    "paint",
    "view",
    "keyorder",
    "sort",
    "filter",
    "is_show_more",
]


def _parse_legacy_display_hints(
    legacy_hints: Mapping[str, InventoryHintSpec],
) -> Iterator[_NodeDisplayHint]:
    for path, related_legacy_hints in sorted(
        _get_related_legacy_hints(legacy_hints).items(), key=lambda t: t[0]
    ):
        if not path:
            continue

        node_or_table_hints = InventoryHintSpec()
        for key in _ALLOWED_KEYS:
            if (value := related_legacy_hints.for_table.get(key)) is not None:
                node_or_table_hints[key] = value
            elif (value := related_legacy_hints.for_node.get(key)) is not None:
                node_or_table_hints[key] = value

        # Some fields like 'title' or 'keyorder' of legacy display hints are declared
        # either for
        # - real nodes, eg. ".hardware.chassis.",
        # - nodes with attributes, eg. ".hardware.cpu." or
        # - nodes with a table, eg. ".software.packages:"
        yield _parse_node_hint(
            path,
            node_or_table_hints,
            related_legacy_hints.for_node.get("keyorder", []),
            related_legacy_hints.by_key,
            related_legacy_hints.for_table.get("keyorder", []),
            related_legacy_hints.by_column,
        )


@dataclass(frozen=True, kw_only=True)
class AttributeDisplayHint:
    ident: str
    title: str
    short_title: str
    long_title: str
    paint_function: PaintFunction
    sort_function: SortFunction
    filter: FilterInvText | FilterInvBool | FilterInvFloat

    @property
    def long_inventory_title(self) -> str:
        return _("Inventory attribute: %s") % self.long_title


OrderedAttributeDisplayHints: TypeAlias = Mapping[SDKey, AttributeDisplayHint]


@dataclass(frozen=True, kw_only=True)
class ColumnDisplayHint:
    ident: str
    title: str
    short_title: str
    long_title: str
    paint_function: PaintFunction
    sort_function: SortFunction
    filter_class: (
        type[FilterInvtableAdminStatus]
        | type[FilterInvtableAvailable]
        | type[FilterInvtableIntegerRange]
        | type[FilterInvtableInterfaceType]
        | type[FilterInvtableOperStatus]
        | type[FilterInvtableText]
        | type[FilterInvtableTimestampAsAge]
        | type[FilterInvtableVersion]
    )

    @property
    def long_inventory_title(self) -> str:
        return _("Inventory column: %s") % self.long_title


OrderedColumnDisplayHints: TypeAlias = Mapping[SDKey, ColumnDisplayHint]


@dataclass(frozen=True, kw_only=True)
class NodeDisplayHint:
    ident: str
    path: SDPath
    title: str
    short_title: str
    long_title: str
    icon: str
    attributes: OrderedAttributeDisplayHints
    columns: OrderedColumnDisplayHints
    table_view_name: str
    table_is_show_more: bool

    @property
    def long_inventory_title(self) -> str:
        return _("Inventory node: %s") % self.long_title

    @property
    def long_inventory_table_title(self) -> str:
        return _("Inventory table: %s") % self.long_title

    def get_attribute_hint(self, key: str) -> AttributeDisplayHint:
        def _default() -> AttributeDisplayHint:
            ident = _make_attr_ident(self.ident, key)
            title = key.replace("_", " ").title()
            long_title = _make_long_title(self.title if self.path else "", title)
            return AttributeDisplayHint(
                ident=ident,
                title=title,
                short_title=title,
                long_title=long_title,
                paint_function=inv_paint_funtions["inv_paint_generic"]["func"],
                sort_function=_decorate_sort_function(_cmp_inv_generic),
                filter=_make_attribute_filter(
                    path=self.path,
                    key=key,
                    data_type="str",
                    ident=ident,
                    long_title=long_title,
                    is_show_more=True,
                ),
            )

        return hint if (hint := self.attributes.get(SDKey(key))) else _default()

    def get_column_hint(self, key: str) -> ColumnDisplayHint:
        def _default() -> ColumnDisplayHint:
            title = key.replace("_", " ").title()
            return ColumnDisplayHint(
                ident=_make_col_ident(self.table_view_name, key),
                title=title,
                short_title=title,
                long_title=_make_long_title(self.title if self.path else "", title),
                paint_function=inv_paint_funtions["inv_paint_generic"]["func"],
                sort_function=_decorate_sort_function(_cmp_inv_generic),
                filter_class=FilterInvtableText,
            )

        return hint if (hint := self.columns.get(SDKey(key))) else _default()


@dataclass(frozen=True)
class DisplayHints:
    _nodes_by_path: dict[SDPath, NodeDisplayHint]

    def add(self, node_hint: NodeDisplayHint) -> None:
        self._nodes_by_path[node_hint.path] = node_hint

    def __iter__(self) -> Iterator[NodeDisplayHint]:
        yield from self._nodes_by_path.values()

    def _find_abc_path(self, path: SDPath) -> SDPath | None:
        # This inventory path is an 'abc' path because it's the general, abstract path of a display
        # hint and may contain "*" (ie. placeholders).
        # Concrete paths (in trees) contain node names which are inserted into these placeholders
        # while calculating node titles.
        for abc_path in self._nodes_by_path:
            if len(path) != len(abc_path):
                continue
            if all(r in (l, "*") for l, r in zip(path, abc_path)):
                return abc_path
        return None

    def get_node_hint(self, path: SDPath) -> NodeDisplayHint:
        if not path:
            return self._nodes_by_path[()]
        if (abc_path := self._find_abc_path(path)) in self._nodes_by_path:
            return self._nodes_by_path[abc_path]
        title = path[-1].replace("_", " ").title()
        return NodeDisplayHint(
            ident=_make_node_ident(path),
            path=path,
            title=title,
            short_title=title,
            long_title=_make_long_title(
                self.get_node_hint(path[:-1]).title if path[:-1] else "",
                title,
            ),
            icon="",
            attributes={},
            columns={},
            table_view_name="",
            table_is_show_more=True,
        )


inv_display_hints = DisplayHints(
    {
        (): NodeDisplayHint(
            ident=_make_node_ident(()),
            path=(),
            title=str(_l("Inventory tree")),
            short_title=str(_l("Inventory tree")),
            long_title=str(_l("Inventory tree")),
            icon="",
            attributes={},
            columns={},
            table_view_name="",
            table_is_show_more=True,
        )
    }
)


def register_display_hints(legacy_hints: Mapping[str, InventoryHintSpec]) -> None:
    for hint in _parse_legacy_display_hints(legacy_hints):
        inv_display_hints.add(
            NodeDisplayHint(
                ident=hint.ident,
                path=hint.path,
                title=hint.title,
                short_title=hint.short_title,
                long_title=_make_long_title(
                    inv_display_hints.get_node_hint(hint.path[:-1]).title if hint.path[:-1] else "",
                    hint.title,
                ),
                icon=hint.icon,
                attributes=hint.attributes,
                columns=hint.columns,
                table_view_name=hint.table_view_name,
                table_is_show_more=hint.table_is_show_more,
            )
        )
