#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

# WATO
#
# This file contain actual page handlers and Setup modes. It does HTML creation
# and implement AJAX handlers. It uses classes, functions and globals
# from watolib.py.

#   .--README--------------------------------------------------------------.
#   |               ____                _                                  |
#   |              |  _ \ ___  __ _  __| |  _ __ ___   ___                 |
#   |              | |_) / _ \/ _` |/ _` | | '_ ` _ \ / _ \                |
#   |              |  _ <  __/ (_| | (_| | | | | | | |  __/                |
#   |              |_| \_\___|\__,_|\__,_| |_| |_| |_|\___|                |
#   |                                                                      |
#   +----------------------------------------------------------------------+
#   | A few words about the implementation details of Setup.                |
#   `----------------------------------------------------------------------'

# [1] Files and Folders
# Setup organizes hosts in folders. A wato folder is represented by a
# OS directory. If the folder contains host definitions, then in that
# directory a file name "hosts{.mk|.cfg}" is kept.
# The directory hierarchy of Setup is rooted at etc/check_mk/conf.d/wato.
# All files in and below that directory are kept by Setup. Setup does not
# touch any other files or directories in conf.d.
# A *path* in Setup means a relative folder path to that directory. The
# root folder has the empty path (""). Folders are separated by slashes.
# Each directory contains a file ".wato" which keeps information needed
# by Setup but not by Checkmk itself.

# [3] Convention for variable names:
# site_id     --> The id of a site, None for the local site in non-distributed setup
# site        --> The dictionary datastructure of a site
# host_name   --> A string containing a host name
# host        --> An instance of the class Host
# folder_path --> A relative specification of a folder (e.g. "linux/prod")
# folder      --> An instance of the class Folder

# .
#   .--Init----------------------------------------------------------------.
#   |                           ___       _ _                              |
#   |                          |_ _|_ __ (_) |_                            |
#   |                           | || '_ \| | __|                           |
#   |                           | || | | | | |_                            |
#   |                          |___|_| |_|_|\__|                           |
#   |                                                                      |
#   +----------------------------------------------------------------------+
#   | Importing, Permissions, global variables                             |
#   `----------------------------------------------------------------------'

# A huge number of imports are here to be compatible with old GUI plugins. Once we dropped support
# for them, we can remove this here and the imports
# flake8: noqa
# pylint: disable=unused-import
from typing import Any

import cmk.utils.paths
import cmk.utils.version as cmk_version
from cmk.utils.exceptions import MKGeneralException

import cmk.gui.background_job as background_job
import cmk.gui.forms as forms
import cmk.gui.gui_background_job as gui_background_job
import cmk.gui.plugins.wato.utils
import cmk.gui.sites as sites
import cmk.gui.userdb as userdb
import cmk.gui.utils as utils
import cmk.gui.valuespec
import cmk.gui.view_utils
import cmk.gui.watolib as watolib
import cmk.gui.watolib.attributes
import cmk.gui.watolib.changes
import cmk.gui.watolib.config_domain_name
import cmk.gui.watolib.config_hostname
import cmk.gui.watolib.host_attributes
import cmk.gui.watolib.hosts_and_folders
import cmk.gui.watolib.rulespecs
import cmk.gui.watolib.sites
import cmk.gui.watolib.timeperiods
import cmk.gui.watolib.translation
import cmk.gui.watolib.user_scripts
import cmk.gui.watolib.utils
import cmk.gui.weblib as weblib
from cmk.gui.cron import register_job
from cmk.gui.htmllib.html import html
from cmk.gui.i18n import _
from cmk.gui.log import logger
from cmk.gui.pages import Page, page_registry
from cmk.gui.permissions import Permission, permission_registry
from cmk.gui.plugins.wato import sync_remote_sites
from cmk.gui.table import table_element
from cmk.gui.type_defs import PermissionName
from cmk.gui.utils.html import HTML
from cmk.gui.visuals.filter import FilterRegistry
from cmk.gui.watolib.activate_changes import update_config_generation

if cmk_version.edition() is cmk_version.Edition.CME:
    import cmk.gui.cme.managed as managed  # pylint: disable=no-name-in-module
else:
    managed = None  # type: ignore[assignment]

from cmk.gui.plugins.wato.utils import (
    Levels,
    monitoring_macro_help,
    PredictiveLevels,
    register_check_parameters,
    register_hook,
    register_notification_parameters,
    RulespecGroupCheckParametersApplications,
    RulespecGroupCheckParametersDiscovery,
    RulespecGroupCheckParametersEnvironment,
    RulespecGroupCheckParametersHardware,
    RulespecGroupCheckParametersNetworking,
    RulespecGroupCheckParametersOperatingSystem,
    RulespecGroupCheckParametersPrinters,
    RulespecGroupCheckParametersStorage,
    RulespecGroupCheckParametersVirtualization,
    UserIconOrAction,
)
from cmk.gui.watolib.translation import HostnameTranslation

# Has to be kept for compatibility with pre 1.6 register_rule() and register_check_parameters()
# calls in the Setup plugin context
subgroup_networking = RulespecGroupCheckParametersNetworking().sub_group_name
subgroup_storage = RulespecGroupCheckParametersStorage().sub_group_name
subgroup_os = RulespecGroupCheckParametersOperatingSystem().sub_group_name
subgroup_printing = RulespecGroupCheckParametersPrinters().sub_group_name
subgroup_environment = RulespecGroupCheckParametersEnvironment().sub_group_name
subgroup_applications = RulespecGroupCheckParametersApplications().sub_group_name
subgroup_virt = RulespecGroupCheckParametersVirtualization().sub_group_name
subgroup_hardware = RulespecGroupCheckParametersHardware().sub_group_name
subgroup_inventory = RulespecGroupCheckParametersDiscovery().sub_group_name

import cmk.gui.watolib.config_domains

# Make some functions of watolib available to Setup plugins without using the
# watolib module name. This is mainly done for compatibility reasons to keep
# the current plugin API functions working
import cmk.gui.watolib.network_scan
import cmk.gui.watolib.read_only
from cmk.gui.plugins.wato.utils.main_menu import (  # Kept for compatibility with pre 1.6 plugins
    MainMenu,
    register_modules,
    WatoModule,
)
from cmk.gui.wato.page_handler import page_handler
from cmk.gui.watolib.hosts_and_folders import ajax_popup_host_action_menu
from cmk.gui.watolib.main_menu import MenuItem
from cmk.gui.watolib.mode import mode_registry, mode_url, redirect, WatoMode
from cmk.gui.watolib.sites import LivestatusViaTCP

from ._permissions import PermissionSectionWATO as PermissionSectionWATO
from .pages._rule_conditions import DictHostTagCondition as DictHostTagCondition
from .pages._rule_conditions import LabelCondition as LabelCondition
from .pages._simple_modes import SimpleEditMode as SimpleEditMode
from .pages._simple_modes import SimpleListMode as SimpleListMode
from .pages._simple_modes import SimpleModeType as SimpleModeType

# .
#   .--Plugins-------------------------------------------------------------.
#   |                   ____  _             _                              |
#   |                  |  _ \| |_   _  __ _(_)_ __  ___                    |
#   |                  | |_) | | | | |/ _` | | '_ \/ __|                   |
#   |                  |  __/| | |_| | (_| | | | | \__ \                   |
#   |                  |_|   |_|\__,_|\__, |_|_| |_|___/                   |
#   |                                 |___/                                |
#   +----------------------------------------------------------------------+
#   | Prepare plugin-datastructures and load Setup plugins                  |
#   '----------------------------------------------------------------------'

modes: dict[str, Any] = {}


def load_plugins() -> None:
    """Plugin initialization hook (Called by cmk.gui.main_modules.load_plugins())"""
    _register_pre_21_plugin_api()
    # Initialize watolib things which are needed before loading the Setup plugins.
    # This also loads the watolib plugins.
    watolib.load_watolib_plugins()

    utils.load_web_plugins("wato", globals())

    if modes:
        raise MKGeneralException(
            _("Deprecated Setup modes found: %r. They need to be refactored to new API.")
            % list(modes.keys())
        )


def _register_pre_21_plugin_api() -> None:  # pylint: disable=too-many-branches
    """Register pre 2.1 "plugin API"

    This was never an official API, but the names were used by builtin and also 3rd party plugins.

    Our builtin plugin have been changed to directly import from the .utils module. We add these old
    names to remain compatible with 3rd party plugins for now.

    In the moment we define an official plugin API, we can drop this and require all plugins to
    switch to the new API. Until then let's not bother the users with it.

    CMK-12228
    """
    # Needs to be a local import to not influence the regular plugin loading order
    import cmk.gui.plugins.wato as api_module
    import cmk.gui.plugins.wato.datasource_programs as datasource_programs

    for name, value in [
        ("PermissionSectionWATO", PermissionSectionWATO),
    ]:
        api_module.__dict__[name] = cmk.gui.plugins.wato.utils.__dict__[name] = value

    for name in (
        "ABCHostAttributeNagiosText",
        "ABCHostAttributeValueSpec",
        "ABCMainModule",
        "BinaryHostRulespec",
        "BinaryServiceRulespec",
        "CheckParameterRulespecWithItem",
        "CheckParameterRulespecWithoutItem",
        "ContactGroupSelection",
        "FullPathFolderChoice",
        "HostGroupSelection",
        "HostRulespec",
        "HostTagCondition",
        "HTTPProxyInput",
        "HTTPProxyReference",
        "MigrateToIndividualOrStoredPassword",
        "is_wato_slave_site",
        "Levels",
        "main_module_registry",
        "MainMenu",
        "MainModuleTopic",
        "MainModuleTopicAgents",
        "MainModuleTopicBI",
        "MainModuleTopicEvents",
        "MainModuleTopicExporter",
        "MainModuleTopicGeneral",
        "MainModuleTopicHosts",
        "MainModuleTopicMaintenance",
        "MainModuleTopicServices",
        "MainModuleTopicUsers",
        "make_confirm_link",
        "ManualCheckParameterRulespec",
        "MenuItem",
        "monitoring_macro_help",
        "multifolder_host_rule_match_conditions",
        "notification_parameter_registry",
        "NotificationParameter",
        "IndividualOrStoredPassword",
        "PluginCommandLine",
        "PredictiveLevels",
        "register_check_parameters",
        "register_hook",
        "register_modules",
        "register_notification_parameters",
        "ReplicationPath",
        "RulespecGroup",
        "RulespecGroupCheckParametersApplications",
        "RulespecGroupCheckParametersDiscovery",
        "RulespecGroupCheckParametersEnvironment",
        "RulespecGroupCheckParametersHardware",
        "RulespecGroupCheckParametersNetworking",
        "RulespecGroupCheckParametersOperatingSystem",
        "RulespecGroupCheckParametersPrinters",
        "RulespecGroupCheckParametersStorage",
        "RulespecGroupCheckParametersVirtualization",
        "RulespecGroupEnforcedServicesApplications",
        "RulespecGroupEnforcedServicesEnvironment",
        "RulespecGroupEnforcedServicesHardware",
        "RulespecGroupEnforcedServicesNetworking",
        "RulespecGroupEnforcedServicesOperatingSystem",
        "RulespecGroupEnforcedServicesStorage",
        "RulespecGroupEnforcedServicesVirtualization",
        "RulespecSubGroup",
        "ServiceGroupSelection",
        "ServiceRulespec",
        "UserIconOrAction",
        "valuespec_check_plugin_selection",
        "WatoModule",
    ):
        api_module.__dict__[name] = cmk.gui.plugins.wato.utils.__dict__[name]
    for name in (
        "mode_registry",
        "mode_url",
        "redirect",
        "WatoMode",
    ):
        api_module.__dict__[name] = globals()[name]
    for name in (
        "IPMIParameters",
        "SNMPCredentials",
    ):
        api_module.__dict__[name] = cmk.gui.watolib.attributes.__dict__[name]
    for name in ("add_change",):
        api_module.__dict__[name] = cmk.gui.watolib.changes.__dict__[name]
    for name in (
        "ConfigDomainCACertificates",
        "ConfigDomainCore",
        "ConfigDomainGUI",
        "ConfigDomainOMD",
    ):
        api_module.__dict__[name] = cmk.gui.watolib.config_domains.__dict__[name]
    for name in ("ConfigHostname",):
        api_module.__dict__[name] = cmk.gui.watolib.config_hostname.__dict__[name]
    for name in (
        "host_attribute_registry",
        "host_attribute_topic_registry",
        "HostAttributeTopicAddress",
        "HostAttributeTopicBasicSettings",
        "HostAttributeTopicCustomAttributes",
        "HostAttributeTopicDataSources",
        "HostAttributeTopicHostTags",
        "HostAttributeTopicManagementBoard",
        "HostAttributeTopicMetaData",
        "HostAttributeTopicNetworkScan",
    ):
        api_module.__dict__[name] = cmk.gui.watolib.host_attributes.__dict__[name]
    for name in (
        "folder_preserving_link",
        "make_action_link",
    ):
        api_module.__dict__[name] = cmk.gui.watolib.hosts_and_folders.__dict__[name]
    for name in (
        "register_rule",
        "Rulespec",
        "rulespec_group_registry",
        "rulespec_registry",
    ):
        api_module.__dict__[name] = cmk.gui.watolib.rulespecs.__dict__[name]
    globals().update({"register_rule": cmk.gui.watolib.rulespecs.register_rule})

    for name in ("LivestatusViaTCP",):
        api_module.__dict__[name] = cmk.gui.watolib.sites.__dict__[name]
    for name in ("TimeperiodSelection",):
        api_module.__dict__[name] = cmk.gui.watolib.timeperiods.__dict__[name]
    for name in (
        "HostnameTranslation",
        "ServiceDescriptionTranslation",
    ):
        api_module.__dict__[name] = cmk.gui.watolib.translation.__dict__[name]
    for name in (
        "user_script_choices",
        "user_script_title",
    ):
        api_module.__dict__[name] = cmk.gui.watolib.user_scripts.__dict__[name]
    for name in (
        "ABCConfigDomain",
        "config_domain_registry",
        "config_variable_group_registry",
        "config_variable_registry",
        "ConfigVariable",
        "ConfigVariableGroup",
        "register_configvar",
        "sample_config_generator_registry",
        "SampleConfigGenerator",
        "wato_fileheader",
    ):
        api_module.__dict__[name] = cmk.gui.watolib.config_domain_name.__dict__[name]
    for name in ("rule_option_elements",):
        api_module.__dict__[name] = cmk.gui.valuespec.__dict__[name]

    # Avoid needed imports, see CMK-12147
    globals().update(
        {
            "Age": cmk.gui.valuespec.Age,
            "Alternative": cmk.gui.valuespec.Alternative,
            "Dictionary": cmk.gui.valuespec.Dictionary,
            "FixedValue": cmk.gui.valuespec.FixedValue,
            "Filesize": cmk.gui.valuespec.Filesize,
            "ListOfStrings": cmk.gui.valuespec.ListOfStrings,
            "MonitoredHostname": cmk.gui.valuespec.MonitoredHostname,
            "MonitoringState": cmk.gui.valuespec.MonitoringState,
            "Password": cmk.gui.valuespec.Password,
            "Percentage": cmk.gui.valuespec.Percentage,
            "RegExpUnicode": cmk.gui.valuespec.RegExpUnicode,
            "TextAscii": cmk.gui.valuespec.TextAscii,
            "TextUnicode": cmk.gui.valuespec.TextUnicode,
            "Transform": cmk.gui.valuespec.Transform,
        }
    )

    for name in (
        "multisite_dir",
        "site_neutral_path",
        "wato_root_dir",
    ):
        api_module.__dict__[name] = cmk.gui.watolib.utils.__dict__[name]

    for name in (
        "RulespecGroupDatasourcePrograms",
        "RulespecGroupDatasourceProgramsOS",
        "RulespecGroupDatasourceProgramsApps",
        "RulespecGroupDatasourceProgramsCloud",
        "RulespecGroupDatasourceProgramsContainer",
        "RulespecGroupDatasourceProgramsCustom",
        "RulespecGroupDatasourceProgramsHardware",
        "RulespecGroupDatasourceProgramsTesting",
    ):
        datasource_programs.__dict__[name] = cmk.gui.plugins.wato.special_agents.common.__dict__[
            name
        ]
