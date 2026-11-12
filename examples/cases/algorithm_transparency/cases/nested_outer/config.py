"""本 Case 仅声明共享工厂、PairSpec 注册入口和资源需求。"""
from dataclasses import dataclass, field
from benchmarks.transparency_case import make_benchmark_case
from benchmarks.transparency_registry import specs


@dataclass(frozen=True)
class CaseConfig:
    mode: str = "nested"
    case_factory: str = "benchmarks.transparency_case:make_benchmark_case"
    pair_registry: str = "benchmarks.transparency_registry:specs"
    resource_request: dict = field(default_factory=lambda: {
        "threads": 1, "workers": 1, "gpus": 0, "backend": "local"})


def get_case_config():
    return CaseConfig()


def get_component_registry():
    """每次返回独立注册表；不引用生成器的 starter 示例文件。"""
    return {"case_factory": make_benchmark_case, "pair_specs": specs}
