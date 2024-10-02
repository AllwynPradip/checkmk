#!/usr/bin/env python3
# Copyright (C) 2024 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.


from cmk.gui.fields.utils import BaseSchema

from cmk import fields


class QuickSetupStageRequest(BaseSchema):
    form_data = fields.Dict(
        required=True,
        example={},
        description="The form data entered by the user.",
    )


class QuickSetupRequest(BaseSchema):
    quick_setup_id = fields.String(
        required=True,
        description="The quick setup id",
        example="aws",
    )

    stages = fields.List(
        fields.Nested(
            QuickSetupStageRequest,
            required=True,
            description="A stage id and its components",
        ),
        example=[{"form_data": {}}, {"form_data": {}}],
        description="A list of stages",
    )


class QuickSetupFinalSaveRequest(BaseSchema):
    button_id = fields.String(
        required=True,
        description="Unique id of the save button clicked by the user",
        example="save",
    )
    stages = fields.List(
        fields.Nested(
            QuickSetupStageRequest,
            required=True,
            description="A stage id and it's form data",
        ),
        example=[{"stage_data": []}, {"stage_data": []}],
        description="A list of stages' form data",
    )
