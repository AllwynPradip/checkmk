#!/usr/bin/env python3
# Copyright (C) 2025 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

"""This script demonstrates the use of OpenTelemetry for logging and metrics export via HTTP.
It sets up OpenTelemetry providers for metrics and logging, sends logs and metrics to a specified
endpoint, and handles the shutdown on termination signals."""

import argparse
import base64
import logging
import signal
import sys
import time
from collections.abc import Callable

from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.http._log_exporter import (
    OTLPLogExporter,
)
from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
    OTLPMetricExporter,
)
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource

HTTP_PORT = 4318
ENDPOINT = f"http://localhost:{HTTP_PORT}"
SERVICE_NAME = "test-service-http"
LOG_LEVEL = logging.INFO
SLEEP_DURATION = 30
HTTP_METRIC_NAME = "test_counter_http"
# Credentials for authentication
USERNAME = "username"
PASSWORD = "password"
ENCODED_CREDENTIALS = base64.b64encode(f"{USERNAME}:{PASSWORD}".encode()).decode()
AUTH_HEADERS = {"Authorization": f"Basic {ENCODED_CREDENTIALS}"}
# OpenTelemetry logs configuration
HTTP_LOG_LEVELS = ["info", "warning", "error"]
HTTP_LOG_TEXT = "Test log level %s #%d"

RESOURCE = Resource.create({"service.name": SERVICE_NAME})

console_logger = logging.getLogger("console.logger")
console_logger.addHandler(logging.StreamHandler(sys.stdout))
console_logger.setLevel(LOG_LEVEL)


def setup_metrics():
    console_logger.info("Setting up OpenTelemetry Metrics")
    metric_exporter = OTLPMetricExporter(
        endpoint=f"{ENDPOINT}/v1/metrics",
        headers=AUTH_HEADERS,
    )
    metrics_reader = PeriodicExportingMetricReader(
        exporter=metric_exporter,
    )
    meter_provider = MeterProvider(metric_readers=[metrics_reader], resource=RESOURCE)
    metrics.set_meter_provider(meter_provider)
    return metrics.get_meter("test.http.meter"), meter_provider


def setup_logging():
    console_logger.info("Setting up OpenTelemetry Logging")
    log_exporter = OTLPLogExporter(endpoint=f"{ENDPOINT}/v1/logs", headers=AUTH_HEADERS)
    log_processor = BatchLogRecordProcessor(log_exporter)
    logger_provider = LoggerProvider(resource=RESOURCE)
    logger_provider.add_log_record_processor(log_processor)
    otel_handler = LoggingHandler(logger_provider=logger_provider)

    logger = logging.getLogger("test.http.logger")
    logger.addHandler(otel_handler)
    logger.setLevel(LOG_LEVEL)
    return logger, logger_provider


def shutdown_handler(
    meter_provider: MeterProvider, logger_provider: LoggerProvider | None
) -> Callable[[object, object], None]:
    def handler(signum: object, frame: object) -> None:
        console_logger.info("Shutting down OpenTelemetry providers and exiting")
        meter_provider.shutdown()
        if logger_provider:
            logger_provider.shutdown()
        sys.exit(0)

    return handler


def main():
    parser = argparse.ArgumentParser(description="OpenTelemetry GRPC Example")
    parser.add_argument(
        "--enable-logs",
        action="store_true",
        help="Enable OpenTelemetry logs",
    )
    args = parser.parse_args()

    meter, meter_provider = setup_metrics()
    if args.enable_logs:
        logger, logger_provider = setup_logging()
        log_levels = [(level, getattr(logger, level)) for level in HTTP_LOG_LEVELS]
    else:
        logger, logger_provider = None, None

    success_shutdown_handler = shutdown_handler(meter_provider, logger_provider)
    signal.signal(signal.SIGINT, success_shutdown_handler)
    signal.signal(signal.SIGTERM, success_shutdown_handler)

    otel_counter = meter.create_counter(
        name=HTTP_METRIC_NAME,
        unit="1",
        description="A simple counter for testing",
    )

    console_logger.info("Starting sending data to %s", ENDPOINT)
    counter = 0

    while True:
        console_logger.info(f"Counter value is {counter}.")
        if logger:
            for level_name, log_method in log_levels:
                log_method(HTTP_LOG_TEXT % (level_name, counter))
        otel_counter.add(1, {"label": "test_label"})
        counter += 1
        time.sleep(SLEEP_DURATION)


if __name__ == "__main__":
    main()
