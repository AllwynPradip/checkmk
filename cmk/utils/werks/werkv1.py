#!/usr/bin/env python3
# Copyright (C) 2023 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.


import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .werk import Class, Compatibility, Edition, Level, NoWiki, RawWerk, Werk, WerkError


class RawWerkV1(BaseModel, RawWerk):
    model_config = ConfigDict(extra="forbid")

    # ATTENTION! If you change this model, you have to inform
    # the website team first! They rely on those fields.
    class_: str = Field(alias="class")
    component: str
    date: int
    level: int
    title: str
    version: str
    compatible: str
    edition: str
    knowledge: str | None = (
        None  # this field is currently not used, but kept so parsing still works
    )
    # it will be removed after the transfer to markdown werks was completed.
    state: str | None = None
    id: int
    targetversion: str | None = None
    description: list[str]

    def to_json_dict(self) -> dict[str, object]:
        return self.model_dump(by_alias=True)

    def to_werk(self) -> "Werk":
        return Werk(
            compatible=(
                Compatibility.COMPATIBLE
                if self.compatible == "compat"
                else Compatibility.NOT_COMPATIBLE
            ),
            version=self.version,
            title=self.title,
            id=self.id,
            date=datetime.datetime.fromtimestamp(self.date, tz=datetime.UTC),
            description=NoWiki(self.description),
            level=Level(self.level),
            class_=Class(self.class_),
            component=self.component,
            edition=Edition(self.edition),
        )


def load_werk_v1(content: str, werk_id: int) -> RawWerkV1:
    werk: dict[str, Any] = {
        "description": [],
        "compatible": "compat",
        "edition": "cre",
        "id": werk_id,
    }
    in_header = True
    for line in content.split("\n"):
        if in_header and not line.strip():
            in_header = False
        elif in_header:
            key, text = line.split(":", 1)
            try:
                value: int | str = int(text.strip())
            except ValueError:
                value = text.strip()
            field = key.lower()
            werk[field] = value
        else:
            werk["description"].append(line)

    while werk["description"] and werk["description"][-1] == "":
        werk["description"].pop()

    # TODO: Check if all fields have an allowed value, see .werks/config.
    try:
        return RawWerkV1.model_validate(werk)
    except ValueError as e:
        raise WerkError(f"Parsing of werk {werk_id} failed:\n{e}") from e
