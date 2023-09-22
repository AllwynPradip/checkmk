#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

# fmt: off
# mypy: disable-error-code=var-annotated
from cmk.base.plugins.agent_based.ucd_mem import parse_ucd_mem

checkname = "ucd_mem"


parsed = parse_ucd_mem(
    [
        [
            [
                "64313712",
                "3845212",
                "8388604",
                "8388604",
                "12233816",
                "16000",
                "3163972",
                "30364",
                "10216780",
                "1",
                "foobar",
                "some error message",
            ]
        ]
    ]
)

discovery = {"": [("", {})]}

checks = {
    "": [
        (
            None,
            {
                "levels_ram": ("perc_used", (20.0, 30.0)),
            },
            [
                (1, "Error: foobar", []),
                (
                    2,
                    "RAM: 78.09% - 47.9 GiB of 61.3 GiB (warn/crit at 20.00%/30.00% used)",
                    [
                        (
                            "mem_used",
                            51426668544,
                            13171448217.6,
                            19757172326.399998,
                            0,
                            65857241088,
                        ),
                        (
                            "mem_used_percent",
                            78.08810040384546,
                            20.0,
                            29.999999999999996,
                            0.0,
                            None,
                        ),
                    ],
                ),
                (0, "Swap: 0% - 0 B of 8.00 GiB", [("swap_used", 0, None, None, 0, 8589930496)]),
                (0, "Total virtual memory: 69.08% - 47.9 GiB of 69.3 GiB", []),
                (0, "Swap error: some error message", []),
            ],
        )
    ]
}
