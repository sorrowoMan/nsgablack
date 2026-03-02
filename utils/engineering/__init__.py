"""
Engineering utilities (config, logging, experiment result container).

These are generic "glue" helpers that are not algorithm-specific.
"""

from __future__ import annotations

from .config_loader import load_config, merge_dicts, apply_config, ConfigError
from .experiment import ExperimentResult
from .logging_config import configure_logging, JsonFormatter
from .error_policy import report_soft_error
from .schema_version import (
    SCHEMA_VERSIONS,
    SchemaVersionError,
    expected_schema_version,
    require_schema,
    schema_check,
    stamp_schema,
)

__all__ = [
    "load_config",
    "merge_dicts",
    "apply_config",
    "ConfigError",
    "ExperimentResult",
    "configure_logging",
    "JsonFormatter",
    "report_soft_error",
    "SCHEMA_VERSIONS",
    "SchemaVersionError",
    "expected_schema_version",
    "require_schema",
    "schema_check",
    "stamp_schema",
]
