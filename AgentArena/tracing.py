"""Traceloop + OpenTelemetry setup for run visibility."""

from __future__ import annotations

import logging

from config import OTEL_SERVICE_NAME, TRACELOOP_API_KEY, TRACELOOP_APP_NAME

try:
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import ConsoleLogExporter, SimpleLogRecordProcessor
    from opentelemetry.sdk.resources import Resource
    from traceloop.sdk import Traceloop
    _TRACING_AVAILABLE = True
except ImportError:
    _TRACING_AVAILABLE = False


class _OtelOnlyFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        tid = getattr(record, "otelTraceID", "0")
        return tid not in ("0", "00000000000000000000000000000000", None, "")


def _make_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter("[%(levelname)s] %(name)s — %(message)s"))
        logger.addHandler(handler)
    return logger


agent_logger = _make_logger("arena.agent")
task_logger = _make_logger("arena.task")


def init_tracing() -> None:
    if not _TRACING_AVAILABLE:
        print("[TRACE] Traceloop not installed — pip install traceloop-sdk opentelemetry-sdk")
        return

    Traceloop.init(
        app_name=TRACELOOP_APP_NAME,
        api_key=TRACELOOP_API_KEY or None,
        disable_batch=True,
        telemetry_enabled=False,
    )

    log_provider = LoggerProvider(
        resource=Resource.create({"service.name": OTEL_SERVICE_NAME})
    )
    exporter: ConsoleLogExporter | object = ConsoleLogExporter()
    if TRACELOOP_API_KEY:
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter

        exporter = OTLPLogExporter(
            endpoint="https://api.traceloop.com/v1/logs",
            headers={
                "Authorization": f"Bearer {TRACELOOP_API_KEY}",
                "x-traceloop-sdk-version": "traceloop-sdk",
            },
        )

    log_provider.add_log_record_processor(SimpleLogRecordProcessor(exporter))
    for logger in (agent_logger, task_logger):
        handler = LoggingHandler(logger_provider=log_provider)
        handler.setLevel(logging.INFO)
        handler.addFilter(_OtelOnlyFilter())
        logger.addHandler(handler)

    print("[TRACE] Traceloop initialised.")
