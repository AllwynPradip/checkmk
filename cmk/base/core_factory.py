#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

from collections.abc import Callable, Mapping
from typing import assert_never

from cmk.base.config import LoadedConfigFragment
from cmk.base.core_config import MonitoringCore
from cmk.ccc.hostaddress import HostName
from cmk.ccc.version import Edition, edition
from cmk.fetchers.snmp import SNMPPluginStore
from cmk.utils import paths
from cmk.utils.labels import LabelManager
from cmk.utils.licensing.handler import LicensingHandler
from cmk.utils.rulesets.ruleset_matcher import RulesetMatcher
from cmk.utils.tags import TagGroupID, TagID


def get_licensing_handler_type() -> type[LicensingHandler]:
    if edition(paths.omd_root) is Edition.CRE:
        from cmk.utils.licensing.registry import get_available_licensing_handler_type
    else:
        from cmk.utils.cee.licensing.registry import (  # type: ignore[import,unused-ignore,no-redef]
            get_available_licensing_handler_type,
        )
    return get_available_licensing_handler_type()


def create_core(
    edition: Edition,
    matcher: RulesetMatcher,
    label_manager: LabelManager,
    loaded_config: LoadedConfigFragment,
    host_tags: Callable[[HostName], Mapping[TagGroupID, TagID]],
    snmp_plugin_store: SNMPPluginStore,
) -> MonitoringCore:
    match loaded_config.monitoring_core:
        case "cmc":
            from cmk.base.cee.microcore_config import (  # type: ignore[import-not-found, import-untyped, unused-ignore]
                CmcPb,
            )
            from cmk.base.configlib.cee.microcore import (  # type: ignore[import-not-found, import-untyped, unused-ignore]
                make_cmc_config,
            )

            return CmcPb(
                get_licensing_handler_type(),
                make_cmc_config(
                    edition, matcher, label_manager, loaded_config, host_tags, snmp_plugin_store
                ),
            )
        case "nagios":
            from cmk.base.core_nagios import NagiosCore

            return NagiosCore(get_licensing_handler_type())
        case other_core:
            assert_never(other_core)
