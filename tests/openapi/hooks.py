#!/usr/bin/env python3
# Copyright (C) 2023 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.
import json
import logging
from typing import Any

import schemathesis
from requests.structures import CaseInsensitiveDict

from tests.openapi import settings
from tests.openapi.response import fix_response, problem_response
from tests.openapi.schema import add_formats_and_patterns, require_properties, update_property

logger = logging.getLogger(__name__)


@schemathesis.hooks.register("before_load_schema")
def hook_before_load_schema(  # pylint: disable=too-many-branches
    context: schemathesis.hooks.HookContext, raw_schema: dict[str, Any]
) -> None:
    """Modify the raw schema before loading it.

    This can be used to suppress known schema issues that would affect test data generation
    (e.g. define value patterns, add required properties or define response status codes).
    """
    logger.debug("INIT: before_load_schema handler")

    # save the unchanged schema to a temporary file
    with open("/tmp/schema.json", "w") as f:
        json.dump(raw_schema, f, indent=2)

    # SCHEMA modifications
    require_properties(raw_schema, "InputRuleObject", ["raw_value", "conditions"], "CMK-TODO")
    require_properties(raw_schema, "LicenseSettings", ["settings"], "CMK-14100")

    require_properties(raw_schema, "UpdateContactGroup", ["attributes"], "CMK-14291")
    require_properties(raw_schema, "UpdateHostGroup", ["attributes"], "CMK-14291")
    require_properties(raw_schema, "UpdateServiceGroup", ["attributes"], "CMK-14291")

    require_properties(raw_schema, "CheckboxWithStrValue", ["state"], "CMK-TODO", merge=False)
    require_properties(
        raw_schema, "NotificationBulkingCheckbox", ["state"], "CMK-TODO", merge=False
    )

    update_property(raw_schema, "BulkDeleteHost", "entries", {"minItems": 1}, "CMK-14259")

    update_property(
        raw_schema,
        "TimeAllowedRange",
        "start",
        {"pattern": "^\\d\\d:\\d\\d(:\\d\\d)?$"},
        "CMK-14314",
    )
    update_property(
        raw_schema,
        "TimeAllowedRange",
        "end",
        {"pattern": "^\\d\\d:\\d\\d(:\\d\\d)?$"},
        "CMK-14314",
    )

    # NOTE: CMK-12182 is mostly done, but fixing InputPassword was apparently overlooked
    update_property(
        raw_schema,
        "InputPassword",
        "ident",
        {"pattern": "^[a-zA-Z0-9][a-zA-Z0-9_-]+$"},
        "CMK-12182",
    )

    update_property(
        raw_schema,
        "InputHostTagGroup",
        "ident",
        {"pattern": "^[a-zA-Z_]+[-0-9a-zA-Z_]$"},
        "CMK-14263",
    )

    update_property(
        raw_schema,
        "HostExtensionsEffectiveAttributes",
        "snmp_community",
        {"nullable": True},
        "CMK-TODO",
    )
    update_property(
        raw_schema,
        "HostViewAttribute",
        "snmp_community",
        {"nullable": True},
        "CMK-TODO",
    )

    update_property(
        raw_schema,
        "HostExtensions",
        "effective_attributes",
        {"nullable": True},
        "CMK-14110",
    )
    update_property(
        raw_schema,
        "NetworkScanResult",
        "start",
        {"nullable": True},
        "CMK-14261",
    )
    update_property(
        raw_schema,
        "NetworkScanResult",
        "end",
        {"nullable": True},
        "CMK-14261",
    )

    update_property(
        raw_schema,
        "CreateFolder",
        "name",
        {"pattern": "^[-_ a-zA-Z0-9.]+$"},
        "CMK-14381",
    )

    update_property(
        raw_schema,
        "NotificationPlugin",
        "notify_plugin",
        {"$ref": "#/components/schemas/PluginWithParams"},
        "CMK-14375",
    )
    for property_name in (
        "the_following_users",
        "members_of_contact_groups",
        "explicit_email_addresses",
        "restrict_by_contact_groups",
    ):
        update_property(
            raw_schema,
            "ContactSelectionAttributes",
            property_name,
            {"$ref": "#/components/schemas/Checkbox"},
            "CMK-14375.1",
        )
    for schema_name in ("ConditionsAttributes", "RuleConditions"):
        for property_name in (
            "match_sites",
            "match_folder",
            "match_host_tags",
            "match_host_labels",
            "match_host_groups",
            "match_hosts",
            "match_exclude_hosts",
            "match_service_labels",
            "match_service_groups",
            "match_exclude_service_groups",
            "match_service_groups_regex",
            "match_exclude_service_groups_regex",
            "match_services",
            "match_exclude_services",
            "match_check_types",
            "match_plugin_output",
            "match_contact_groups",
            "match_service_levels",
            "match_only_during_time_period",
            "match_host_event_type",
            "match_service_event_type",
            "restrict_to_notification_numbers",
            "throttle_periodic_notifications",
            "match_notification_comment",
            "event_console_alerts",
        ):
            update_property(
                raw_schema,
                schema_name,
                property_name,
                {"$ref": "#/components/schemas/Checkbox"},
                "CMK-14375.2",
            )

    for schema_name in (
        "FolderUpdateAttribute",
        "FolderViewAttribute",
        "FolderCreateAttribute",
        "HostExtensionsEffectiveAttributes",
        "HostViewAttribute",
        "HostCreateAttribute",
        "HostUpdateAttribute",
        "ClusterCreateAttribute",
    ):
        update_property(
            raw_schema,
            schema_name,
            "management_ipmi_credentials",
            {"nullable": True},
            "CMK-TODO",
        )

    # SCHEMA modifications: additionalProperties
    # control the creation of additionalProperties in the root level of schema object definitions:
    # * do not allow any additionalProperties by default
    # * make sure additionalProperties of type "string" match the default string pattern
    schemas = raw_schema["components"]["schemas"]
    for schema_name in [
        _
        for _ in schemas
        if _
        not in (
            "HostConfig",
            "CollectionItem",
            "RulesetCollection",
            "Link",
            "HostExtensionsEffectiveAttributes",
        )
    ]:
        if not set(schemas[schema_name]).intersection(
            ("additionalProperties", "oneOf", "anyOf", "allOf", "not")
        ):
            schemas[schema_name]["additionalProperties"] = False
        elif (
            "additionalProperties" in schemas[schema_name]
            and isinstance(schemas[schema_name]["additionalProperties"], dict)
            and schemas[schema_name]["additionalProperties"].get("type") == "string"
            and not schemas[schema_name]["additionalProperties"].get("pattern")
        ):
            schemas[schema_name]["additionalProperties"][
                "pattern"
            ] = settings.default_string_pattern

    # PATH modifications
    paths = raw_schema["paths"]
    for endpoint in [
        {"path": _path, "method": _method} for _path in paths for _method in paths[_path]
    ]:
        path = endpoint["path"]
        method = endpoint["method"].lower()
        responses = paths[path][method]["responses"]
        if "UNDEFINED-HTTP500" in settings.suppressed_issues and not set(responses).intersection(
            {"5XX", "500"}
        ):
            logger.warning(
                "%s %s: Suppressed undefined status code 500! #UNDEFINED-HTTP500",
                method.upper(),
                path,
            )
            responses.update(problem_response("500", "Internal Server Error"))
        if "UNDEFINED-HTTP400" in settings.suppressed_issues and not set(responses).intersection(
            {"4XX", "400"}
        ):
            logger.warning(
                "%s %s: Suppressed undefined status code 400!",
                method.upper(),
                path,
            )
            responses.update(problem_response("400", "Bad request"))
        if (
            "UNDEFINED-HTTP404" in settings.suppressed_issues
            and method in ("get", "put", "patch", "delete")
            and not "404" in responses
        ):
            logger.warning(
                "%s %s: Suppressed undefined status code 404!",
                method.upper(),
                path,
            )
            responses.update(problem_response("404", "Not found"))
    if "CMK-12421" in settings.suppressed_issues:
        paths["/domain-types/activation_run/actions/activate-changes/invoke"]["post"][
            "responses"
        ].update(problem_response("204", "No Content"))

    # ignore some endpoints (via deprecating them) to avoid failures during parametrization
    for path, methods in {
        "/objects/rule/{rule_id}/actions/move/invoke": ("post",),
        "/objects/bi_rule/{rule_id}": ("post", "put"),
        "/objects/notification_rule/{rule_id}": ("put",),
        "/objects/notification_rule/{rule_id}/actions/delete/invoke": ("post",),
        "/domain-types/rule/collections/all": ("post",),
        "/domain-types/metric/actions/filter/invoke": ("post",),  # internal endpoint
    }.items():
        for method in methods:
            raw_schema["paths"][path][method].update({"deprecated": True})

    add_formats_and_patterns(raw_schema)

    # save the update schema to a temporary file
    with open("/tmp/schema.updated.json", "w") as f:
        json.dump(raw_schema, f, indent=2)


@schemathesis.hooks.register("before_call")
def hook_before_call(
    context: schemathesis.hooks.HookContext,
    case: schemathesis.models.Case,
) -> None:
    """Modify the case before execution.

    This can be used to override the headers or other generic properties.
    """
    logger.debug("%s %s: before_call handler", case.method, case.path)
    if case.headers is None:
        case.headers = CaseInsensitiveDict({})
    case.headers["Content-Type"] = "application/json"
    case.headers["If-Match"] = "*"


@schemathesis.hooks.register("after_call")
def hook_after_call(  # pylint: disable=too-many-branches
    context: schemathesis.hooks.HookContext,
    case: schemathesis.models.Case,
    response: schemathesis.utils.GenericResponse,
) -> None:
    """Modify the case after execution but before validation.

    This can be used to analyze and modify the response before validation
    (e.g. to suppress response validation errors).
    """
    logger.debug("%s %s: after_call handler", case.method, case.path)

    # generic: invalid JSON response
    if "/download" not in case.path:
        if case.path == "/domain-types/licensing/actions/configure/invoke":
            fix_response(
                case,
                response,
                status_code=-204,
                valid_body=False,
                body={},
                set_body={"links": []},
                ticket_id="CMK-14101",
            )
        else:
            fix_response(
                case,
                response,
                status_code=-204,
                valid_body=False,
                body={},
                set_body={
                    "title": response.reason,
                    "status": response.status_code,
                    "detail": response.reason,
                },
                ticket_id="INVALID-JSON",
            )
    fix_response(
        case,
        response,
        method="GET",
        path="/domain-types/audit_log/collections/all",
        status_code=200,
        set_body={"links": []},
        ticket_id="CMK-14403",
    )

    # generic: empty response Content-Type
    fix_response(
        case,
        response,
        empty_content_type=True,
        valid_content_type=False,
        update_headers={"Content-Type": "{auto}"},
        ticket_id="CMK-11886",
    )
    # generic: invalid (but not empty) response Content-Type
    fix_response(
        case,
        response,
        empty_content_type=False,
        valid_content_type=False,
        update_headers={"Content-Type": "{auto}"},
        ticket_id="CMK-11886",
    )

    # incomplete 200 responses
    fix_response(
        case,
        response,
        method="GET",
        path="/objects/ruleset/{ruleset_name}",
        status_code=200,
        update_body={"extensions": {"folder": "/"}},
        ticket_id="CMK-TODO",
    )
    fix_response(
        case,
        response,
        method="GET",
        path="/domain-types/[^/]+/collections/all",
        status_code=200,
        valid_body=True,
        object_type="ruleset",
        update_items={
            "value": {"href": "", "method": "GET", "rel": "", "type": "application/json"}
        },
        ticket_id="CMK-TODO",
    )

    # incomplete 404 responses
    fix_response(
        case,
        response,
        method="POST",
        path="/domain-types/host_config/actions/wait-for-completion/invoke",
        status_code=404,
        body={"title": "No running renaming job was found", "status": 404},
        set_body={"title": "No running renaming job was found", "status": 404, "detail": ""},
        ticket_id="CMK-14273",
    )

    # invalid status: 500 instead of 400
    fix_response(
        case,
        response,
        method="POST|PUT",
        path="/objects/bi_aggregation/{aggregation_id}",
        status_code=500,
        traceback=".*\nKeyError:.*",
        valid_body=True,
        set_status_code=400,
        update_headers={"Content-Type": "{problem}"},
        set_body={"title": "Bad Request", "status": 400, "detail": "Bad Request"},
        ticket_id="CMK-14416",
    )
    fix_response(
        case,
        response,
        method="POST",
        path="/domain-types/metric/actions/filter/invoke",
        status_code=500,
        body={"detail": "There is no graph template with the id .*"},
        set_status_code=400,
        update_body={"title": "Bad Request", "status": 400},
        ticket_id="CMK-TODO",
    )
    fix_response(
        case,
        response,
        method="GET",
        path="/objects/service_discovery/{host_name}",
        body={"detail": "Error running automation call <tt>service-discovery-preview</tt>.*"},
        status_code=500,
        set_status_code=400,
        set_body={
            "title": "Bad Request",
            "status": 400,
            "detail": "Failed to lookup IPv4 address via DNS.",
        },
        ticket_id="CMK-13216",
    )
    fix_response(
        case,
        response,
        method="POST",
        path="/domain-types/service_discovery_run/actions/start/invoke",
        body={"detail": "Error running automation call <tt>service-discovery-preview</tt>.*"},
        status_code=500,
        set_status_code=400,
        set_body={
            "title": "Bad Request",
            "status": 400,
            "detail": "Failed to lookup IPv4 address via DNS.",
        },
        ticket_id="CMK-13216",
    )
    fix_response(
        case,
        response,
        method="PUT",
        path="/objects/host/{host_name}/actions/update_discovery_phase/invoke",
        body={"detail": "Error running automation call <tt>service-discovery-preview</tt>.*"},
        status_code=500,
        set_status_code=400,
        set_body={
            "title": "Bad Request",
            "status": 400,
            "detail": "Failed to lookup IPv4 address via DNS.",
        },
        ticket_id="CMK-13216",
    )

    # invalid status: 500 instead of 401
    fix_response(
        case,
        response,
        method="POST",
        path="/objects/folder_config/{folder}/actions/move/invoke",
        body={"detail": "AssertionError: . Crash report generated. Please submit."},
        status_code=500,
        set_status_code=400,
        set_body={
            "title": "Bad Request",
            "status": 400,
            "detail": "Can not delete the root folder.",
        },
        ticket_id="CMK-14256",
    )

    # invalid status: 500 instead of 404

    # invalid status: 500 instead of 409
