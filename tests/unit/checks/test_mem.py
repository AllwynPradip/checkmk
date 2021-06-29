#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2021 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

import pytest
from cmk.base.plugins.agent_based.mem import parse_proc_meminfo_bytes


@pytest.mark.parametrize('section, parsed', [
    ([['MemTotal:', '24707592', 'kB'], ['MemFree:', '441224', 'kB'], ['Buffers:', '320672', 'kB'],
      ['Cached:', '19981008', 'kB'], ['SwapCached:', '6172', 'kB'], ['Active:', '8756876', 'kB'],
      ['Inactive:', '13360444', 'kB'], ['Active(anon):', '1481236', 'kB'],
      ['Inactive(anon):', '371260', 'kB'], ['Active(file):', '7275640', 'kB'],
      ['Inactive(file):', '12989184', 'kB'], ['Unevictable:', '964808', 'kB'],
      ['Mlocked:', '964808', 'kB'], ['SwapTotal:', '16777212', 'kB'],
      ['SwapFree:', '16703328', 'kB'], ['Dirty:', '4408124', 'kB'], ['Writeback:', '38020', 'kB'],
      ['AnonPages:', '2774444', 'kB'], ['Mapped:', '69456', 'kB'], ['Shmem:', '33772', 'kB'],
      ['Slab:', '861028', 'kB'], ['SReclaimable:', '756236', 'kB'], ['SUnreclaim:', '104792', 'kB'],
      ['KernelStack:', '4176', 'kB'], ['PageTables:', '15892', 'kB'], ['NFS_Unstable:', '0', 'kB'],
      ['Bounce:', '0', 'kB'], ['WritebackTmp:', '0', 'kB'], ['CommitLimit:', '39014044', 'kB'],
      ['Committed_AS:', '3539808', 'kB'], ['VmallocTotal:', '34359738367', 'kB'],
      ['VmallocUsed:', '347904', 'kB'], ['VmallocChunk:', '34346795572', 'kB'],
      ['HardwareCorrupted:', '6', 'kB'], ['AnonHugePages:', '0', 'kB'], ['HugePages_Total:', '0'],
      ['HugePages_Free:', '0'], ['HugePages_Rsvd:', '0'], ['HugePages_Surp:', '0'],
      ['Hugepagesize:', '2048', 'kB'], ['DirectMap4k:', '268288', 'kB'],
      ['DirectMap2M:', '8112128', 'kB'], ['DirectMap1G:', '16777216', 'kB']], {
          'MemTotal': 25300574208,
          'MemFree': 451813376,
          'Buffers': 328368128,
          'Cached': 20460552192,
          'SwapCached': 6320128,
          'Active': 8967041024,
          'Inactive': 13681094656,
          'Active(anon)': 1516785664,
          'Inactive(anon)': 380170240,
          'Active(file)': 7450255360,
          'Inactive(file)': 13300924416,
          'Unevictable': 987963392,
          'Mlocked': 987963392,
          'SwapTotal': 17179865088,
          'SwapFree': 17104207872,
          'Dirty': 4513918976,
          'Writeback': 38932480,
          'AnonPages': 2841030656,
          'Mapped': 71122944,
          'Shmem': 34582528,
          'Slab': 881692672,
          'SReclaimable': 774385664,
          'SUnreclaim': 107307008,
          'KernelStack': 4276224,
          'PageTables': 16273408,
          'NFS_Unstable': 0,
          'Bounce': 0,
          'WritebackTmp': 0,
          'CommitLimit': 39950381056,
          'Committed_AS': 3624763392,
          'VmallocTotal': 35184372087808,
          'VmallocUsed': 356253696,
          'VmallocChunk': 35171118665728,
          'HardwareCorrupted': 6144,
          'AnonHugePages': 0,
          'HugePages_Total': 0,
          'HugePages_Free': 0,
          'HugePages_Rsvd': 0,
          'HugePages_Surp': 0,
          'Hugepagesize': 2097152,
          'DirectMap4k': 274726912,
          'DirectMap2M': 8306819072,
          'DirectMap1G': 17179869184
      }),
])
def test_cpu_threads_regression(section, parsed):
    assert parsed == parse_proc_meminfo_bytes(section)
