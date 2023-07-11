#!/usr/bin/env python3
# Copyright (C) 2022 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

import pytest_mock

from tests.unit.cmk.special_agents.agent_kube.factory import (
    api_to_agent_daemonset,
    APIDaemonSetFactory,
    APIPodFactory,
)

from cmk.special_agents import agent_kube
from cmk.special_agents.utils_kubernetes.agent_handlers.common import (
    AnnotationNonPatternOption,
    CheckmkHostSettings,
)
from cmk.special_agents.utils_kubernetes.agent_handlers.daemonset_handler import create_api_sections


def daemon_sets_api_sections() -> set[str]:
    return {
        "kube_pod_resources_v1",
        "kube_memory_resources_v1",
        "kube_cpu_resources_v1",
        "kube_daemonset_info_v1",
        "kube_update_strategy_v1",
        "kube_daemonset_replicas_v1",
        "kube_controller_spec_v1",
    }


def test_write_daemon_sets_api_sections_registers_sections_to_be_written(
    mocker: pytest_mock.MockFixture,
) -> None:
    write_sections_mock = mocker.patch("cmk.special_agents.utils_kubernetes.common.write_sections")
    daemon_set = api_to_agent_daemonset(APIDaemonSetFactory.build(), pods=[APIPodFactory.build()])
    sections = create_api_sections(
        daemon_set,
        CheckmkHostSettings(
            cluster_name="cluster",
            kubernetes_cluster_hostname="host",
            annotation_key_pattern=AnnotationNonPatternOption.ignore_all,
        ),
        "daemonset",
    )
    agent_kube.common.write_sections(sections)
    assert {
        section.section_name for section in list(write_sections_mock.call_args[0][0])
    } == daemon_sets_api_sections()
    assert write_sections_mock.call_count == 1
