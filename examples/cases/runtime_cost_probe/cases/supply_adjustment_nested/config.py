"""This Case's resource declaration; Project L0 remains the grant owner."""
from dataclasses import dataclass


@dataclass(frozen=True)
class CaseConfig:
    resource_request: dict


def get_case_config():
    return CaseConfig({"threads": 1, "workers": 1, "gpus": 0, "backend": "local",
                       "memory_mb": 1536, "capabilities": ["production_inner", "nested_eval"]})
