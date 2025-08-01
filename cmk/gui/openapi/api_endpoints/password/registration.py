#!/usr/bin/env python3
# Copyright (C) 2025 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.
from cmk.gui.openapi.api_endpoints.password.endpoint_family import PASSWORD_FAMILY
from cmk.gui.openapi.framework.registry import VersionedEndpointRegistry
from cmk.gui.openapi.restful_objects.endpoint_family import EndpointFamilyRegistry

from .create_password import ENDPOINT_CREATE_PASSWORD
from .delete_password import ENDPOINT_DELETE_PASSWORD
from .list_passwords import ENDPOINT_LIST_PASSWORDS
from .show_password import ENDPOINT_SHOW_PASSWORD
from .update_password import ENDPOINT_UPDATE_PASSWORD


def register(
    versioned_endpoint_registry: VersionedEndpointRegistry,
    endpoint_family_registry: EndpointFamilyRegistry,
    *,
    ignore_duplicates: bool,
) -> None:
    endpoint_family_registry.register(PASSWORD_FAMILY, ignore_duplicates=ignore_duplicates)
    versioned_endpoint_registry.register(
        ENDPOINT_LIST_PASSWORDS,
        ignore_duplicates=ignore_duplicates,
    )
    versioned_endpoint_registry.register(
        ENDPOINT_SHOW_PASSWORD,
        ignore_duplicates=ignore_duplicates,
    )
    versioned_endpoint_registry.register(
        ENDPOINT_DELETE_PASSWORD,
        ignore_duplicates=ignore_duplicates,
    )
    versioned_endpoint_registry.register(
        ENDPOINT_CREATE_PASSWORD,
        ignore_duplicates=ignore_duplicates,
    )
    versioned_endpoint_registry.register(
        ENDPOINT_UPDATE_PASSWORD,
        ignore_duplicates=ignore_duplicates,
    )
