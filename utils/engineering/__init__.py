"""
Engineering utilities (config, logging, experiment result container).

These are generic "glue" helpers that are not algorithm-specific.
"""

from __future__ import annotations

from .config_loader import load_config, merge_dicts, apply_config, ConfigError
from .experiment import ExperimentResult
from .logging_config import configure_logging, JsonFormatter
from .run_contracts import (
    RUN_SURFACE_CONTRACT_VERSION,
    ArtifactRecord,
    AssemblyRecord,
    RunRecord,
    SurfaceRecord,
    make_artifact_record,
    make_assembly_record,
    make_run_record,
    make_surface_record,
    stable_json_dumps,
    stable_signature,
)
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
    "RUN_SURFACE_CONTRACT_VERSION",
    "SurfaceRecord",
    "AssemblyRecord",
    "ArtifactRecord",
    "RunRecord",
    "make_surface_record",
    "make_assembly_record",
    "make_artifact_record",
    "make_run_record",
    "stable_json_dumps",
    "stable_signature",
    "SCHEMA_VERSIONS",
    "SchemaVersionError",
    "expected_schema_version",
    "require_schema",
    "schema_check",
    "stamp_schema",
]
