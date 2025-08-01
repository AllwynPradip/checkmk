#!/usr/bin/env python3
# Copyright (C) 2023 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

from collections.abc import Sequence

import pytest

from cmk.gui.inventory._tree import InventoryPath, TreeSource
from cmk.gui.inventory.filters import FilterInvText
from cmk.gui.views.inventory._display_hints import (
    AttributeDisplayHint,
    ColumnDisplayHint,
    NodeDisplayHint,
    Table,
)
from cmk.gui.views.inventory._paint_functions import inv_paint_generic
from cmk.gui.views.inventory._tree_renderer import (
    _replace_title_placeholders,
    _SDDeltaItem,
    _SDDeltaItemsSorter,
    _SDItemsSorter,
    SDItem,
)
from cmk.utils.structured_data import (
    ImmutableAttributes,
    ImmutableDeltaAttributes,
    ImmutableDeltaTable,
    ImmutableTable,
    RetentionInterval,
    SDDeltaValue,
    SDKey,
    SDPath,
)


@pytest.mark.parametrize(
    "table, expected",
    [
        (ImmutableTable(), []),
        (
            ImmutableTable(
                key_columns=[SDKey("sid")],
                rows_by_ident={
                    ("SID 2",): {
                        SDKey("sid"): "SID 2",
                        SDKey("flashback"): "Flashback 2",
                        SDKey("other"): "Other 2",
                    },
                    ("SID 1",): {
                        SDKey("sid"): "SID 1",
                        SDKey("flashback"): "Flashback 1",
                        SDKey("other"): "Other 1",
                    },
                    (None,): {
                        SDKey("sid"): None,
                        SDKey("flashback"): None,
                        SDKey("other"): None,
                    },
                },
                retentions={
                    ("SID 2",): {SDKey("sid"): RetentionInterval(1, 2, 3, "previous")},
                },
            ),
            [
                [
                    SDItem(
                        key="sid",
                        title="SID",
                        value="SID 1",
                        retention_interval=None,
                        paint_function=inv_paint_generic,
                        icon_path_svc_problems="",
                    ),
                    SDItem(
                        key="flashback",
                        title="Flashback",
                        value="Flashback 1",
                        retention_interval=None,
                        paint_function=inv_paint_generic,
                        icon_path_svc_problems="",
                    ),
                    SDItem(
                        key="other",
                        title="Other",
                        value="Other 1",
                        retention_interval=None,
                        paint_function=inv_paint_generic,
                        icon_path_svc_problems="",
                    ),
                ],
                [
                    SDItem(
                        key="sid",
                        title="SID",
                        value="SID 2",
                        retention_interval=RetentionInterval(1, 2, 3, "previous"),
                        paint_function=inv_paint_generic,
                        icon_path_svc_problems="",
                    ),
                    SDItem(
                        key="flashback",
                        title="Flashback",
                        value="Flashback 2",
                        retention_interval=None,
                        paint_function=inv_paint_generic,
                        icon_path_svc_problems="",
                    ),
                    SDItem(
                        key="other",
                        title="Other",
                        value="Other 2",
                        retention_interval=None,
                        paint_function=inv_paint_generic,
                        icon_path_svc_problems="",
                    ),
                ],
            ],
        ),
    ],
)
def test_sort_table_rows_displayhint(
    table: ImmutableTable,
    expected: Sequence[Sequence[SDItem]],
) -> None:
    items_sorter = _SDItemsSorter(
        NodeDisplayHint(
            name="inv",
            path=(),
            icon="",
            title="",
            short_title="",
            long_title="",
            attributes={},
            table=Table(
                columns={
                    SDKey("sid"): ColumnDisplayHint(
                        title="SID",
                        short_title="",
                        long_title="",
                        paint_function=inv_paint_generic,
                    ),
                    SDKey("changed"): ColumnDisplayHint(
                        title="Changed",
                        short_title="",
                        long_title="",
                        paint_function=inv_paint_generic,
                    ),
                    SDKey("foo"): ColumnDisplayHint(
                        title="Foo",
                        short_title="",
                        long_title="",
                        paint_function=inv_paint_generic,
                    ),
                    SDKey("flashback"): ColumnDisplayHint(
                        title="Flashback",
                        short_title="",
                        long_title="",
                        paint_function=inv_paint_generic,
                    ),
                    SDKey("other"): ColumnDisplayHint(
                        title="Other",
                        short_title="",
                        long_title="",
                        paint_function=inv_paint_generic,
                    ),
                }
            ),
        ),
        "",
        ImmutableAttributes(),
        table,
    )
    assert items_sorter.sort_rows()[-1] == expected


@pytest.mark.parametrize(
    "delta_table, expected",
    [
        (ImmutableDeltaTable(), []),
        (
            ImmutableDeltaTable(
                key_columns=[SDKey("sid")],
                rows=[
                    {
                        SDKey("sid"): SDDeltaValue(old="SID 1", new="SID 1"),
                        SDKey("flashback"): SDDeltaValue(old=None, new=None),
                    },
                    {
                        SDKey("sid"): SDDeltaValue(old="SID 2", new="SID 2"),
                        SDKey("flashback"): SDDeltaValue(old="Flashback", new="Flashback"),
                    },
                    {
                        SDKey("sid"): SDDeltaValue(old="SID 2", new="SID 2"),
                        SDKey("flashback"): SDDeltaValue(old=None, new=None),
                    },
                ],
            ),
            [],
        ),
        (
            ImmutableDeltaTable(
                key_columns=[SDKey("sid")],
                rows=[
                    {
                        SDKey("sid"): SDDeltaValue(old="SID 1", new="SID 1"),
                        SDKey("flashback"): SDDeltaValue(old=None, new=None),
                    },
                    {
                        SDKey("sid"): SDDeltaValue(old="SID 2", new="SID 2"),
                        SDKey("flashback"): SDDeltaValue(old="Flashback 21", new="Flashback 22"),
                    },
                ],
            ),
            [
                [
                    _SDDeltaItem(
                        key="sid",
                        title="SID",
                        old="SID 2",
                        new="SID 2",
                        paint_function=inv_paint_generic,
                    ),
                    _SDDeltaItem(
                        key="flashback",
                        title="Flashback",
                        old="Flashback 21",
                        new="Flashback 22",
                        paint_function=inv_paint_generic,
                    ),
                ],
            ],
        ),
        (
            ImmutableDeltaTable(
                key_columns=[SDKey("sid")],
                rows=[
                    {
                        SDKey("sid"): SDDeltaValue(old="SID 2", new=None),
                        SDKey("flashback"): SDDeltaValue(old=None, new="Flashback 2"),
                        SDKey("other"): SDDeltaValue(old="Other 2", new="Other 2"),
                        SDKey("changed"): SDDeltaValue(old="Changed 21", new="Changed 22"),
                    },
                    {
                        SDKey("sid"): SDDeltaValue(old="SID 1", new=None),
                        SDKey("flashback"): SDDeltaValue(old=None, new="Flashback 1"),
                        SDKey("other"): SDDeltaValue(old="Other 1", new="Other 1"),
                        SDKey("changed"): SDDeltaValue(old="Changed 11", new="Changed 12"),
                    },
                    {
                        SDKey("sid"): SDDeltaValue(old="SID 3", new="SID 3"),
                        SDKey("flashback"): SDDeltaValue(old="Flashback 3", new="Flashback 3"),
                        SDKey("other"): SDDeltaValue(old=None, new=None),
                        SDKey("changed"): SDDeltaValue(old=None, new=None),
                    },
                ],
            ),
            [
                [
                    _SDDeltaItem(
                        key=SDKey("sid"),
                        title="SID",
                        old="SID 1",
                        new=None,
                        paint_function=inv_paint_generic,
                    ),
                    _SDDeltaItem(
                        key=SDKey("changed"),
                        title="Changed",
                        old="Changed 11",
                        new="Changed 12",
                        paint_function=inv_paint_generic,
                    ),
                    _SDDeltaItem(
                        key=SDKey("flashback"),
                        title="Flashback",
                        old=None,
                        new="Flashback 1",
                        paint_function=inv_paint_generic,
                    ),
                    _SDDeltaItem(
                        key=SDKey("other"),
                        title="Other",
                        old="Other 1",
                        new="Other 1",
                        paint_function=inv_paint_generic,
                    ),
                ],
                [
                    _SDDeltaItem(
                        key=SDKey("sid"),
                        title="SID",
                        old="SID 2",
                        new=None,
                        paint_function=inv_paint_generic,
                    ),
                    _SDDeltaItem(
                        key=SDKey("changed"),
                        title="Changed",
                        old="Changed 21",
                        new="Changed 22",
                        paint_function=inv_paint_generic,
                    ),
                    _SDDeltaItem(
                        key=SDKey("flashback"),
                        title="Flashback",
                        old=None,
                        new="Flashback 2",
                        paint_function=inv_paint_generic,
                    ),
                    _SDDeltaItem(
                        key=SDKey("other"),
                        title="Other",
                        old="Other 2",
                        new="Other 2",
                        paint_function=inv_paint_generic,
                    ),
                ],
            ],
        ),
        (
            ImmutableDeltaTable(
                key_columns=[SDKey("sid")],
                rows=[
                    {
                        SDKey("sid"): SDDeltaValue(old="SID 2", new=None),
                        SDKey("flashback"): SDDeltaValue(old=None, new="Flashback 2"),
                        SDKey("other"): SDDeltaValue(old="Other 2", new="Other 2"),
                        SDKey("changed"): SDDeltaValue(old="Changed 21", new="Changed 22"),
                    },
                    {
                        SDKey("sid"): SDDeltaValue(old="SID 1", new=None),
                        SDKey("flashback"): SDDeltaValue(old=None, new="Flashback 1"),
                        SDKey("other"): SDDeltaValue(old="Other 1", new="Other 1"),
                        SDKey("changed"): SDDeltaValue(old="Changed 11", new="Changed 12"),
                    },
                    {
                        SDKey("sid"): SDDeltaValue(old="SID 3", new="SID 3"),
                        SDKey("flashback"): SDDeltaValue(old="Flashback 3", new="Flashback 3"),
                        SDKey("other"): SDDeltaValue(old=None, new=None),
                        SDKey("changed"): SDDeltaValue(old=None, new=None),
                    },
                ],
            ),
            [
                [
                    _SDDeltaItem(
                        key=SDKey("sid"),
                        title="SID",
                        old="SID 1",
                        new=None,
                        paint_function=inv_paint_generic,
                    ),
                    _SDDeltaItem(
                        key=SDKey("changed"),
                        title="Changed",
                        old="Changed 11",
                        new="Changed 12",
                        paint_function=inv_paint_generic,
                    ),
                    _SDDeltaItem(
                        key=SDKey("flashback"),
                        title="Flashback",
                        old=None,
                        new="Flashback 1",
                        paint_function=inv_paint_generic,
                    ),
                    _SDDeltaItem(
                        key=SDKey("other"),
                        title="Other",
                        old="Other 1",
                        new="Other 1",
                        paint_function=inv_paint_generic,
                    ),
                ],
                [
                    _SDDeltaItem(
                        key=SDKey("sid"),
                        title="SID",
                        old="SID 2",
                        new=None,
                        paint_function=inv_paint_generic,
                    ),
                    _SDDeltaItem(
                        key=SDKey("changed"),
                        title="Changed",
                        old="Changed 21",
                        new="Changed 22",
                        paint_function=inv_paint_generic,
                    ),
                    _SDDeltaItem(
                        key=SDKey("flashback"),
                        title="Flashback",
                        old=None,
                        new="Flashback 2",
                        paint_function=inv_paint_generic,
                    ),
                    _SDDeltaItem(
                        key=SDKey("other"),
                        title="Other",
                        old="Other 2",
                        new="Other 2",
                        paint_function=inv_paint_generic,
                    ),
                ],
            ],
        ),
    ],
)
def test_sort_delta_table_rows_displayhint(
    delta_table: ImmutableDeltaTable,
    expected: Sequence[Sequence[_SDDeltaItem]],
) -> None:
    delta_items_sorter = _SDDeltaItemsSorter(
        NodeDisplayHint(
            name="inv",
            path=(),
            icon="",
            title="",
            short_title="",
            long_title="",
            attributes={},
            table=Table(
                columns={
                    SDKey("sid"): ColumnDisplayHint(
                        title="SID",
                        short_title="",
                        long_title="",
                        paint_function=inv_paint_generic,
                    ),
                    SDKey("changed"): ColumnDisplayHint(
                        title="Changed",
                        short_title="",
                        long_title="",
                        paint_function=inv_paint_generic,
                    ),
                    SDKey("foo"): ColumnDisplayHint(
                        title="Foo",
                        short_title="",
                        long_title="",
                        paint_function=inv_paint_generic,
                    ),
                    SDKey("flashback"): ColumnDisplayHint(
                        title="Flashback",
                        short_title="",
                        long_title="",
                        paint_function=inv_paint_generic,
                    ),
                    SDKey("other"): ColumnDisplayHint(
                        title="Other",
                        short_title="",
                        long_title="",
                        paint_function=inv_paint_generic,
                    ),
                }
            ),
        ),
        ImmutableDeltaAttributes(),
        delta_table,
    )
    assert delta_items_sorter.sort_rows()[-1] == expected


@pytest.mark.parametrize(
    "attributes, expected",
    [
        (ImmutableAttributes(), []),
        (
            ImmutableAttributes(
                pairs={
                    SDKey("b"): "B",
                    SDKey("d"): "D",
                    SDKey("c"): "C",
                    SDKey("a"): "A",
                },
                retentions={SDKey("c"): RetentionInterval(1, 2, 3, "previous")},
            ),
            [
                SDItem(
                    key=SDKey("a"),
                    title="A",
                    value="A",
                    retention_interval=None,
                    paint_function=inv_paint_generic,
                    icon_path_svc_problems="",
                ),
                SDItem(
                    key=SDKey("b"),
                    title="B",
                    value="B",
                    retention_interval=None,
                    paint_function=inv_paint_generic,
                    icon_path_svc_problems="",
                ),
                SDItem(
                    key=SDKey("d"),
                    title="D",
                    value="D",
                    retention_interval=None,
                    paint_function=inv_paint_generic,
                    icon_path_svc_problems="",
                ),
                SDItem(
                    key=SDKey("c"),
                    title="C",
                    value="C",
                    retention_interval=RetentionInterval(1, 2, 3, "previous"),
                    paint_function=inv_paint_generic,
                    icon_path_svc_problems="",
                ),
            ],
        ),
    ],
)
def test_sort_attributes_pairs_displayhint(
    attributes: ImmutableAttributes,
    expected: Sequence[SDItem],
) -> None:
    items_sorter = _SDItemsSorter(
        NodeDisplayHint(
            name="inv",
            path=(),
            icon="",
            title="",
            short_title="",
            long_title="",
            attributes={
                SDKey("a"): AttributeDisplayHint(
                    name="inv_a",
                    title="A",
                    short_title="",
                    long_title="",
                    paint_function=inv_paint_generic,
                    sort_function=lambda *args: 0,
                    filter=FilterInvText(
                        ident="inv_a",
                        title="",
                        inventory_path=InventoryPath(
                            path=(),
                            source=TreeSource.attributes,
                            key=SDKey("a"),
                        ),
                        is_show_more=True,
                    ),
                ),
                SDKey("b"): AttributeDisplayHint(
                    name="inv_b",
                    title="B",
                    short_title="",
                    long_title="",
                    paint_function=inv_paint_generic,
                    sort_function=lambda *args: 0,
                    filter=FilterInvText(
                        ident="inv_b",
                        title="",
                        inventory_path=InventoryPath(
                            path=(),
                            source=TreeSource.attributes,
                            key=SDKey("b"),
                        ),
                        is_show_more=True,
                    ),
                ),
                SDKey("d"): AttributeDisplayHint(
                    name="inv_d",
                    title="D",
                    short_title="",
                    long_title="",
                    paint_function=inv_paint_generic,
                    sort_function=lambda *args: 0,
                    filter=FilterInvText(
                        ident="inv_d",
                        title="",
                        inventory_path=InventoryPath(
                            path=(),
                            source=TreeSource.attributes,
                            key=SDKey("d"),
                        ),
                        is_show_more=True,
                    ),
                ),
                SDKey("c"): AttributeDisplayHint(
                    name="inv_c",
                    title="C",
                    short_title="",
                    long_title="",
                    paint_function=inv_paint_generic,
                    sort_function=lambda *args: 0,
                    filter=FilterInvText(
                        ident="inv_c",
                        title="",
                        inventory_path=InventoryPath(
                            path=(),
                            source=TreeSource.attributes,
                            key=SDKey("c"),
                        ),
                        is_show_more=True,
                    ),
                ),
            },
            table=Table(columns={}),
        ),
        "",
        attributes,
        ImmutableTable(),
    )
    assert items_sorter.sort_pairs() == expected


@pytest.mark.parametrize(
    "delta_attributes, expected",
    [
        (ImmutableDeltaAttributes(), []),
        (
            ImmutableDeltaAttributes(
                pairs={
                    SDKey("b"): SDDeltaValue(old="B", new=None),
                    SDKey("d"): SDDeltaValue(old=None, new="D"),
                    SDKey("c"): SDDeltaValue(old="C", new="C"),
                    SDKey("a"): SDDeltaValue(old="A1", new="A2"),
                }
            ),
            [
                _SDDeltaItem(
                    key=SDKey("a"),
                    title="A",
                    old="A1",
                    new="A2",
                    paint_function=inv_paint_generic,
                ),
                _SDDeltaItem(
                    key=SDKey("b"),
                    title="B",
                    old="B",
                    new=None,
                    paint_function=inv_paint_generic,
                ),
                _SDDeltaItem(
                    key=SDKey("d"),
                    title="D",
                    old=None,
                    new="D",
                    paint_function=inv_paint_generic,
                ),
            ],
        ),
    ],
)
def test_sort_delta_attributes_pairs_displayhint(
    delta_attributes: ImmutableDeltaAttributes,
    expected: Sequence[_SDDeltaItem],
) -> None:
    delta_items_sorter = _SDDeltaItemsSorter(
        NodeDisplayHint(
            name="inv",
            path=(),
            icon="",
            title="",
            short_title="",
            long_title="",
            attributes={
                SDKey("a"): AttributeDisplayHint(
                    name="inv_a",
                    title="A",
                    short_title="",
                    long_title="",
                    paint_function=inv_paint_generic,
                    sort_function=lambda *args: 0,
                    filter=FilterInvText(
                        ident="inv_a",
                        title="",
                        inventory_path=InventoryPath(
                            path=(),
                            source=TreeSource.attributes,
                            key=SDKey("a"),
                        ),
                        is_show_more=True,
                    ),
                ),
                SDKey("b"): AttributeDisplayHint(
                    name="inv_c",
                    title="B",
                    short_title="",
                    long_title="",
                    paint_function=inv_paint_generic,
                    sort_function=lambda *args: 0,
                    filter=FilterInvText(
                        ident="inv_b",
                        title="",
                        inventory_path=InventoryPath(
                            path=(),
                            source=TreeSource.attributes,
                            key=SDKey("b"),
                        ),
                        is_show_more=True,
                    ),
                ),
                SDKey("d"): AttributeDisplayHint(
                    name="inv_d",
                    title="D",
                    short_title="",
                    long_title="",
                    paint_function=inv_paint_generic,
                    sort_function=lambda *args: 0,
                    filter=FilterInvText(
                        ident="inv_d",
                        title="",
                        inventory_path=InventoryPath(
                            path=(),
                            source=TreeSource.attributes,
                            key=SDKey("d"),
                        ),
                        is_show_more=True,
                    ),
                ),
                SDKey("c"): AttributeDisplayHint(
                    name="inv_c",
                    title="C",
                    short_title="",
                    long_title="",
                    paint_function=inv_paint_generic,
                    sort_function=lambda *args: 0,
                    filter=FilterInvText(
                        ident="inv_c",
                        title="",
                        inventory_path=InventoryPath(
                            path=(),
                            source=TreeSource.attributes,
                            key=SDKey("c"),
                        ),
                        is_show_more=True,
                    ),
                ),
            },
            table=Table(columns={}),
        ),
        delta_attributes,
        ImmutableDeltaTable(),
    )
    assert delta_items_sorter.sort_pairs() == expected


@pytest.mark.parametrize(
    "title, abc_path, path, expected_title",
    [
        (
            "Datacenter %d",
            ("software", "applications", "vmwareesx", "*"),
            ("software", "applications", "vmwareesx", "1"),
            "Datacenter 1",
        ),
        (
            "Cluster %d",
            ("software", "applications", "vmwareesx", "*", "clusters", "*"),
            ("software", "applications", "vmwareesx", "1", "clusters", "2"),
            "Cluster 2",
        ),
    ],
)
def test__replace_title_placeholders(
    title: str, abc_path: SDPath, path: SDPath, expected_title: str
) -> None:
    assert (
        _replace_title_placeholders(
            NodeDisplayHint(
                name="",
                path=abc_path,
                icon="",
                title=title,
                short_title=title,
                long_title=title,
                attributes={},
                table=Table(columns={}),
            ),
            path,
        )
        == expected_title
    )
