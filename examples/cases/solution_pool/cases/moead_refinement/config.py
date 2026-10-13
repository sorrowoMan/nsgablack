"""Case 组件默认选择；资源需求由 Project 配置。"""
from dataclasses import dataclass


@dataclass(frozen=True)
class CaseConfig:
    problem_key: str = "two_centers"
    pipeline_key: str = "shared"
    adapter_key: str = "moead_ga_vns"
    resource_request: dict | None = None


def get_case_config():
    return CaseConfig()
