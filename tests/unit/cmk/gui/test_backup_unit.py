#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

import pytest

import cmk.utils.paths
from cmk.ccc.user import UserId
from cmk.crypto.password import Password
from cmk.gui.backup.pages import ModeBackupEditKey
from cmk.gui.logged_in import user


@pytest.mark.usefixtures("request_context")
def test_backup_key_create_web(monkeypatch: pytest.MonkeyPatch) -> None:
    with monkeypatch.context() as m:
        m.setattr(user, "id", UserId("dingdöng"))
        store_path = cmk.utils.paths.default_config_dir / "backup_keys.mk"

        assert not store_path.exists()
        mode = ModeBackupEditKey()

        # First create a backup key
        mode._create_key(
            alias="älias", passphrase=Password("passphra$e"), use_git=False, default_key_size=1024
        )

        assert store_path.exists()

        # Then test key existence
        test_mode = ModeBackupEditKey()
        keys = test_mode.key_store.load()
        assert len(keys) == 1

        assert store_path.exists()
        store_path.unlink()
