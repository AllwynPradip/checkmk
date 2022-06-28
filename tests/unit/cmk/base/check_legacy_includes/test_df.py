#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2019 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

from typing import Optional, Sequence

import pytest
from pytest_mock import MockerFixture

from cmk.base.check_legacy_includes.df import df_check_filesystem_single_coroutine
from cmk.base.plugins.agent_based.utils.df import FILESYSTEM_DEFAULT_PARAMS


@pytest.mark.parametrize(
    ["data", "expected_result"],
    [
        pytest.param(
            (
                0,
                None,
                None,
                None,
                None,
            ),
            [
                (
                    1,
                    "Size of filesystem is 0 B",
                    [],
                ),
            ],
            id="zero capacity",
        ),
        pytest.param(
            (
                102655,
                58814,
                122,
                None,
                None,
            ),
            [
                (
                    0,
                    "Used: 42.71% - 42.8 GiB of 100 GiB",
                    [
                        ("fs_used", 43841.0, 82124.0, 92389.5, 0.0, 102655.0),
                        ("fs_size", 102655, None, None, 0, None),
                        ("fs_used_percent", 42.707125809751105, 80.0, 90.0, 0.0, 100.0),
                    ],
                ),
                (
                    0,
                    "trend: 0 B / 24 hours",
                    [
                        ("growth", 161105947.82608697),
                        ("trend", 0.0, None, None, 0, 4277.291666666667),
                    ],
                ),
            ],
            id="no inode information",
        ),
        pytest.param(
            (
                102655,
                58814,
                122,
                65486,
                111,
            ),
            [
                (
                    0,
                    "Used: 42.71% - 42.8 GiB of 100 GiB",
                    [
                        ("fs_used", 43841.0, 82124.0, 92389.5, 0.0, 102655.0),
                        ("fs_size", 102655, None, None, 0, None),
                        ("fs_used_percent", 42.707125809751105, 80.0, 90.0, 0.0, 100.0),
                    ],
                ),
                (
                    0,
                    "trend: 0 B / 24 hours",
                    [
                        ("growth", 161105947.82608697),
                        ("trend", 0.0, None, None, 0, 4277.291666666667),
                    ],
                ),
                (
                    2,
                    "Inodes used: 99.83% (warn/crit at 90.00%/95.00%), Inodes available: 111 "
                    "(0.17%)",
                    [("inodes_used", 65375.0, 58937.4, 62211.7, 0.0, 65486.0)],
                ),
            ],
            id="with inode information",
        ),
        pytest.param(
            (
                102655,
                58814,
                122,
                65486,
                0,
            ),
            [
                (
                    0,
                    "Used: 42.71% - 42.8 GiB of 100 GiB",
                    [
                        ("fs_used", 43841.0, 82124.0, 92389.5, 0.0, 102655.0),
                        ("fs_size", 102655, None, None, 0, None),
                        ("fs_used_percent", 42.707125809751105, 80.0, 90.0, 0.0, 100.0),
                    ],
                ),
                (
                    0,
                    "trend: 0 B / 24 hours",
                    [
                        ("growth", 161105947.82608697),
                        ("trend", 0.0, None, None, 0, 4277.291666666667),
                    ],
                ),
                (
                    2,
                    "Inodes used: 100.00% (warn/crit at 90.00%/95.00%), Inodes available: 0 (0%)",
                    [("inodes_used", 65486.0, 58937.4, 62211.7, 0.0, 65486.0)],
                ),
            ],
            id="zero inodes left",
        ),
    ],
)
def test_df_check_filesystem_single_coroutine(
    mocker: MockerFixture,
    data: tuple[
        Optional[float], Optional[float], Optional[float], Optional[float], Optional[float]
    ],
    expected_result: Sequence[tuple[int, str, Sequence[tuple]]],
) -> None:
    mocker.patch(
        "cmk.base.item_state.get_value_store",
        return_value={"df./fake.delta": (100, 954)},
    )
    assert (
        list(
            df_check_filesystem_single_coroutine(
                "/fake",
                *data,
                FILESYSTEM_DEFAULT_PARAMS,
                this_time=123,
            )
        )
        == expected_result
    )
