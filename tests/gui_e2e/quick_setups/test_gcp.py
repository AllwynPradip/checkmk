#!/usr/bin/env python3
# Copyright (C) 2025 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.
import logging
import os
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import expect

from tests.gui_e2e.testlib.playwright.pom.dashboard import Dashboard
from tests.gui_e2e.testlib.playwright.pom.setup.cloud_quick_setups import (
    GCPAddNewConfiguration,
    GCPConfigurationList,
    QuickSetupMultiChoice,
)
from tests.gui_e2e.testlib.playwright.pom.setup.dcd import DCD
from tests.gui_e2e.testlib.playwright.pom.setup.hosts import SetupHost
from tests.gui_e2e.testlib.playwright.pom.setup.passwords import Passwords
from tests.gui_e2e.testlib.playwright.pom.setup.ruleset import Ruleset
from tests.testlib.site import Site
from tests.testlib.utils import run

logger = logging.getLogger(__name__)


@pytest.fixture(name="fake_gcp_dump", scope="module")
def fixture_fake_gcp_dump(test_site: Site) -> Iterator[None]:
    """Fake the GCP special agent used within Checkmk site.

    Quick setup performs validation of GCP connection.
    Faking the GCP agent bypasses such validations, which are 'out-of-scope' of UI tests.
    """
    fake_agent_gcp = Path(__file__).parent / "fake_agent_gcp.py"
    gcp_agent = test_site.path("lib/python3/cmk/plugins/gcp/special_agents/agent_gcp.py")
    backup_agent = str(gcp_agent).replace(".py", ".py.bck")
    run(["cp", str(gcp_agent), backup_agent], sudo=True)
    run(["cp", str(fake_agent_gcp), str(gcp_agent)], sudo=True)
    yield
    if os.getenv("CLEANUP", "1") == "1":
        run(["cp", str(backup_agent), str(gcp_agent)], sudo=True)
        run(["rm", str(backup_agent)], sudo=True)


@pytest.fixture(name="gcp_qs_config_page")
def fixture_gcp_qs_config_page(
    fake_gcp_dump: None, dashboard_page: Dashboard, test_site: Site
) -> Iterator[GCPAddNewConfiguration]:
    """Navigate to the GCP Quick setup page and add new configuration page"""
    configuration_name = "my_gcp_account"
    folder_details = GCPAddNewConfiguration.FolderDetails(
        name="gcp_folder",
        parent="Main",
        create_new=True,
    )
    gcp_qs_config_page = GCPAddNewConfiguration(
        dashboard_page.page,
        configuration_name=configuration_name,
        folder_details=folder_details,
    )
    yield gcp_qs_config_page
    gcp_config_list_page = GCPConfigurationList(gcp_qs_config_page.page)
    activate = False
    # quick check; validation is performed in the test
    if gcp_config_list_page.configuration_row(configuration_name).count() > 0:
        gcp_config_list_page.delete_configuration(configuration_name)
        activate = True

    list_hosts_page = SetupHost(gcp_config_list_page.page)
    # the quick setup could have failed before the folder gets created
    if list_hosts_page.folder_icon(folder_details.name).count() > 0:
        list_hosts_page.delete_folder(folder_details.name)
        activate = True

    if activate:  # only activate if we deleted the quick setup or folder
        list_hosts_page.activate_changes(test_site)


@pytest.mark.xfail(reason="Bug CMK-24545", strict=True, raises=AssertionError)
def test_minimal_configuration(gcp_qs_config_page: GCPAddNewConfiguration, test_site: Site) -> None:
    """Validate setup of a GCP configuration using 'Quick setup: GCP'"""
    config_name = gcp_qs_config_page.configuration_name
    config_name_pattern = re.compile(config_name)
    host_name = "gcp_host"
    password_name = f"{config_name}_password"  # this is auto-generated by Checkmk

    # Stage 1
    gcp_qs_config_page.specify_stage_one_details(
        project_id="my_gcp_project",
        json_credentials='{"no": "idea"}',
    )

    gcp_qs_config_page.validate_button_text_and_goto_next_qs_stage(current_stage=1)

    # Stage 2
    gcp_qs_config_page.specify_stage_two_details(
        host_name,
        site_name=test_site.id,
    )

    gcp_qs_config_page.validate_button_text_and_goto_next_qs_stage(current_stage=2)

    # Stage 3
    gcp_qs_config_page.specify_stage_three_details(
        services=QuickSetupMultiChoice([], ["HTTP(S) load balancer"]),
    )

    gcp_qs_config_page.validate_button_text_and_goto_next_qs_stage(current_stage=3)

    # Stage 4
    gcp_qs_config_page.click_test_configuration_button()
    # TODO: change to new text once available
    expect(
        gcp_qs_config_page.main_area.locator().get_by_text("GCP services found!"),
        message="Expected GCP services to be found after the connection test!",
    ).to_be_visible()
    gcp_qs_config_page.save_quick_setup()

    logger.info("Validate GCP configuration is listed.")
    config_list_page = gcp_qs_config_page.list_configuration_page()
    expect(
        config_list_page.configuration_row(config_name),
        message="Expected the new GCP Quick setup to be listed!",
    ).to_be_visible()

    logger.info("Validate GCP folder and host is setup.")
    list_hosts_page = SetupHost(config_list_page.page)
    list_hosts_page.click_and_wait(
        list_hosts_page.get_link(gcp_qs_config_page.folder_details.name),
        expected_locator=list_hosts_page.get_link(host_name),
    )

    logger.info("Validate GCP rule is setup.")
    list_gcp_rules_page = Ruleset(
        list_hosts_page.page, "Google Cloud Platform (GCP)", "VM, cloud, container", exact_rule=True
    )
    expect(
        list_gcp_rules_page.rule_source(rule_id=0),
        message="Expected the GCP rule to be created!",
    ).to_have_text(config_name_pattern)
    expect(
        list_gcp_rules_page.get_link(config_name, exact=False),
        message="Expected the Quick setup to be linked on the rule page!",
    ).to_be_visible()

    logger.info("Validate GCP password is setup.")
    list_passwords_page = Passwords(list_gcp_rules_page.page)
    expect(
        list_passwords_page.password_source(password_name),
        message="Expected the GCP password to be created!",
    ).to_have_text(config_name_pattern)
    expect(
        list_passwords_page.get_link(config_name, exact=False),
        message="Expected the Quick setup to be linked on the password page!",
    ).to_be_visible()

    if test_site.edition.is_raw_edition():
        logger.info("Skipping DCD validation for raw edition.")
    else:
        logger.info("Validate GCP DCD connection is setup.")
        dcd_page = DCD(list_passwords_page.page)
        expect(
            dcd_page.connection_row(gcp_qs_config_page.configuration_name),
            message="Expected a DCD connection for the GCP Quick setup to exist!",
        ).to_be_visible()
