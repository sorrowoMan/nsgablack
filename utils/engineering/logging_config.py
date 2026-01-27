"""Logging configuration helpers with optional JSON output."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional


class JsonFormatter(logging.Formatter):
    """Format log records as JSON strings."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(
    level: str = "INFO",
    *,
    json_format: bool = False,
    log_file: Optional[str] = None,
    force: bool = False,
) -> logging.Logger:
    """Configure root logger with optional JSON formatting."""
    logger = logging.getLogger()
    if force:
        for handler in list(logger.handlers):
            logger.removeHandler(handler)

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if not logger.handlers:
        handler: logging.Handler
        if log_file:
            handler = logging.FileHandler(log_file, encoding="utf-8")
        else:
            handler = logging.StreamHandler()

        formatter = JsonFormatter() if json_format else logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
