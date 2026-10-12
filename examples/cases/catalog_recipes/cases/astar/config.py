"""
Case-level component registry aggregator.

Register custom components (problem, pipeline, adapter, bias, plugin)
by key for catalog discovery and runtime selection.

For solver cases: register search-space components.
For trainer cases: additionally register model encode/decode pipeline components.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CaseConfig:
    """Aggregated component registries for this case."""
    problem_key: str = "default"
    pipeline_key: str = "default"
    adapter_key: str = "default"
    resource_request: dict | None = None


def get_case_config() -> CaseConfig:
    """Return the aggregated case configuration."""
    return CaseConfig()
