"""从真实本地源码生成中文读本；只读组件文件，不构建或运行 Solver。"""
from hashlib import sha256
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main():
    sources = [ROOT / name for name in ("project_config.py", "run_project.py", "run_and_report.py")]
    for case in sorted((ROOT / "cases").iterdir()):
        if not case.is_dir() or case.name == "__pycache__":
            continue
        sources.extend(sorted(path for path in case.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
            and (path.suffix in {".py", ".toml"} or path.name in {".case", "context_keys.json"})))
    lines = ["# 综合装配 Project：真实源码读本", "",
             "由 write_source_book.py 直接读取同目录源码生成；每节给出真实文件、SHA-256 和完整文本。",
             "不在本文件中维护另一套可执行实现。修改源码后可重新生成，阅读时以链接的实际文件为准。", "",
             "建议配合 [装配讲解](ASSEMBLY_GUIDE_CN.md) 使用。", "",
             "共享框架实现继续从包复用，后文只收录本 Project 的本地代码，不复制整个框架。", "",
             "## 共享实现索引", "",
             "- ComposableSolver：[core/composable_solver.py](../../../core/composable_solver.py)",
             "- Problem：[core/base.py](../../../core/base.py)",
             "- RepresentationPipeline：[representation/base.py](../../../representation/base.py)",
             "- UniformInitializer／GaussianMutation／ContextGaussianMutation／ClipRepair：[representation/continuous.py](../../../representation/continuous.py)",
             "- UnitBinding：[units/contracts.py](../../../units/contracts.py)",
             "- PopulationUnit：[units/collections.py](../../../units/collections.py)",
             "- PopulationChange／成员操作：[units/population_operations.py](../../../units/population_operations.py)",
             "- Unit builders：[representation/structure_builders.py](../../../representation/structure_builders.py)",
             "- NSGA2Adapter：[adapters/nsga2/adapter.py](../../../adapters/nsga2/adapter.py)",
             "- VNSAdapter：[adapters/vns/adapter.py](../../../adapters/vns/adapter.py)",
             "- MOEADAdapter：[adapters/moead/adapter.py](../../../adapters/moead/adapter.py)",
             "- PatternSearchAdapter：[adapters/pattern_search/adapter.py](../../../adapters/pattern_search/adapter.py)",
             "- BiasModule：[bias/bias_module.py](../../../bias/bias_module.py)",
             "- DomainBias：[bias/core/base.py](../../../bias/core/base.py)",
             "- BudgetController：[core/control_plane.py](../../../core/control_plane.py)",
             "- Plugin：[plugins/base.py](../../../plugins/base.py)",
             "- CheckpointResumePlugin：[plugins/system/checkpoint_resume.py](../../../plugins/system/checkpoint_resume.py)",
             "- ParetoArchivePlugin：[plugins/runtime/pareto_archive.py](../../../plugins/runtime/pareto_archive.py)",
             "- SolutionPool：[core/state/solution_pool.py](../../../core/state/solution_pool.py)",
             "- Pool 调用期操作：[adapters/change_pool.py](../../../adapters/change_pool.py)",
             "- 局部自然编排：[adapters/search_plan.py](../../../adapters/search_plan.py)",
             "- 池任务与结果收据：[adapters/pool_tasks.py](../../../adapters/pool_tasks.py)",
             "- 原始可行性接纳：[core/evaluation_acceptance.py](../../../core/evaluation_acceptance.py)",
             "- 求解结果边界：[core/solver_result.py](../../../core/solver_result.py)",
             "- Project runner：[project/project_runner.py](../../../project/project_runner.py)，转发 BlackBase 正式底座。", "",
             "## 文件目录", ""]
    for path in sources:
        relative = path.relative_to(ROOT).as_posix()
        lines.append(f"- [{relative}]({relative})")
    for path in sources:
        relative = path.relative_to(ROOT).as_posix()
        raw = path.read_bytes()
        content = raw.decode("utf-8-sig").rstrip()
        language = "python" if path.suffix == ".py" else "toml" if path.suffix == ".toml" else "text"
        lines += ["", f"## {relative}", "", f"真实文件：[{relative}]({relative})。", "",
                  f"SHA-256：`{sha256(raw).hexdigest()}`。", "", f"```{language}", content, "```"]
    target = ROOT / "SOURCE_CODE_CN.md"
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{target}: {len(sources)} 个源码／声明文件")


if __name__ == "__main__":
    main()
