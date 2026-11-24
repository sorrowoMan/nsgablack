"""标准透明性 Case 薄入口，真实配对执行位于公共 benchmark 组件。"""
from benchmarks.transparency_case import make_benchmark_case


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    return make_benchmark_case("matrix", mode="matrix", defaults={}, config=config,
        resource_context=resource_context, component_overrides=component_overrides)
