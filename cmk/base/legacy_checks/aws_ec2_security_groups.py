#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.


from cmk.agent_based.legacy.v0_unstable import LegacyCheckDefinition
from cmk.base.check_legacy_includes.aws import parse_aws

check_info = {}


def inventory_aws_ec2_security_groups(parsed):
    if parsed:
        yield None, {"groups": [group["GroupId"] for group in parsed]}


def check_aws_ec2_security_groups(item, params, parsed):
    for group in parsed:
        state = 0
        descr = group.get("Description")
        if descr:
            prefix = "[%s] " % descr
        else:
            prefix = ""
        infotext = "{}{}: {}".format(prefix, group["GroupName"], group["GroupId"])
        if group["GroupId"] not in params["groups"]:
            infotext += " (has changed)"
            state = 2
        yield state, infotext


check_info["aws_ec2_security_groups"] = LegacyCheckDefinition(
    name="aws_ec2_security_groups",
    parse_function=parse_aws,
    service_name="AWS/EC2 Security Groups",
    discovery_function=inventory_aws_ec2_security_groups,
    check_function=check_aws_ec2_security_groups,
    check_default_parameters={},
)
