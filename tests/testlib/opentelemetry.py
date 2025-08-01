#!/usr/bin/env python3
# Copyright (C) 2025 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.
import enum
import logging
import os
import signal
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from tests.testlib.common.repo import repo_path
from tests.testlib.common.utils import wait_until
from tests.testlib.site import Site
from tests.testlib.utils import execute

logger = logging.getLogger(__name__)

OPENTELEMETRY_DIR = Path("tmp/check_mk/otel_collector")


class ScriptFileName(enum.Enum):
    OTEL_HTTP = "opentelemetry_http.py"
    OTEL_GRPC = "opentelemetry_grpc.py"
    PROMETHEUS = "opentelemetry_prometheus.py"

    def __str__(self):
        return self.value


@contextmanager
def opentelemetry_app(
    script_file_name: ScriptFileName, additional_args: list[str] | None = None
) -> Iterator[subprocess.Popen]:
    """Context manager to run an OpenTelemetry application script, handles its lifecycle,
    and raises errors if execution fails."""
    scripts_folder = repo_path() / "tests" / "scripts"
    script_path = scripts_folder / str(script_file_name)
    env = os.environ.copy()
    # by default, OpenTelemetry SDK is disabled in system tests
    env["OTEL_SDK_DISABLED"] = "false"

    command = ["python", str(script_path)]
    if additional_args:
        command.extend(additional_args)

    logger.info("Starting OpenTelemetry application with script: %s", script_file_name)
    with execute(
        command,
        start_new_session=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    ) as process:
        try:
            yield process
        finally:
            logger.info("Terminating OpenTelemetry application")
            process.send_signal(signal.SIGINT)
            stdout, stderr = process.communicate()
            logger.info(f"OpenTelemetry application output:\n{stdout.strip()}")
            if process.returncode != 0 or stderr:
                error_message = (
                    f"OpenTelemetry application encountered an issue.\n"
                    f"Exit code: {process.returncode}\n"
                    f"Error output:\n{stderr.strip()}"
                )
                logger.error(error_message)
                raise RuntimeError(
                    "Failed to execute OpenTelemetry application. Check logs for details."
                )


def wait_for_opentelemetry_data(
    site: Site, host_name: str, timeout: int = 90, interval: int = 5
) -> None:
    """Wait until OpenTelemetry data is available for the specified host."""
    opentelemetry_data_path = OPENTELEMETRY_DIR / f"host_monitoring/{host_name}"
    wait_until(
        lambda: site.file_exists(opentelemetry_data_path), timeout=timeout, interval=interval
    )


def delete_opentelemetry_data(site: Site) -> None:
    """Delete OpenTelemetry data for the site."""
    host_monitoring_data_path = OPENTELEMETRY_DIR / "host_monitoring"
    if site.file_exists(host_monitoring_data_path):
        site.delete_dir(host_monitoring_data_path)

    autocompleter_data_path = OPENTELEMETRY_DIR / "autocompleter"
    for file in site.listdir(autocompleter_data_path):
        site.delete_file(autocompleter_data_path / file)
