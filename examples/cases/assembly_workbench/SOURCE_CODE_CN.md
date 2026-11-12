# 综合装配 Project：真实源码读本

由 write_source_book.py 直接读取同目录源码生成；每节给出真实文件、SHA-256 和完整文本。
不在本文件中维护另一套可执行实现。修改源码后可重新生成，阅读时以链接的实际文件为准。

建议配合 [装配讲解](ASSEMBLY_GUIDE_CN.md) 使用。

共享框架实现继续从包复用，后文只收录本 Project 的本地代码，不复制整个框架。

## 共享实现索引

- ComposableSolver：[core/composable_solver.py](../../../core/composable_solver.py)
- Problem：[core/base.py](../../../core/base.py)
- RepresentationPipeline：[representation/base.py](../../../representation/base.py)
- UniformInitializer／GaussianMutation／ContextGaussianMutation／ClipRepair：[representation/continuous.py](../../../representation/continuous.py)
- UnitBinding：[units/contracts.py](../../../units/contracts.py)
- PopulationUnit：[units/collections.py](../../../units/collections.py)
- PopulationChange／成员操作：[units/population_operations.py](../../../units/population_operations.py)
- Unit builders：[representation/structure_builders.py](../../../representation/structure_builders.py)
- NSGA2Adapter：[adapters/nsga2/adapter.py](../../../adapters/nsga2/adapter.py)
- VNSAdapter：[adapters/vns/adapter.py](../../../adapters/vns/adapter.py)
- MOEADAdapter：[adapters/moead/adapter.py](../../../adapters/moead/adapter.py)
- PatternSearchAdapter：[adapters/pattern_search/adapter.py](../../../adapters/pattern_search/adapter.py)
- BiasModule：[bias/bias_module.py](../../../bias/bias_module.py)
- DomainBias：[bias/core/base.py](../../../bias/core/base.py)
- BudgetController：[core/control_plane.py](../../../core/control_plane.py)
- Plugin：[plugins/base.py](../../../plugins/base.py)
- CheckpointResumePlugin：[plugins/system/checkpoint_resume.py](../../../plugins/system/checkpoint_resume.py)
- ParetoArchivePlugin：[plugins/runtime/pareto_archive.py](../../../plugins/runtime/pareto_archive.py)
- SolutionPool：[core/state/solution_pool.py](../../../core/state/solution_pool.py)
- Pool 调用期操作：[adapters/change_pool.py](../../../adapters/change_pool.py)
- 局部自然编排：[adapters/search_plan.py](../../../adapters/search_plan.py)
- 池任务与结果收据：[adapters/pool_tasks.py](../../../adapters/pool_tasks.py)
- 原始可行性接纳：[core/evaluation_acceptance.py](../../../core/evaluation_acceptance.py)
- 求解结果边界：[core/solver_result.py](../../../core/solver_result.py)
- Project runner：[project/project_runner.py](../../../project/project_runner.py)，转发 BlackBase 正式底座。

## 文件目录

- [project_config.py](project_config.py)
- [run_project.py](run_project.py)
- [run_and_report.py](run_and_report.py)
- [cases/directions/.case](cases/directions/.case)
- [cases/directions/__init__.py](cases/directions/__init__.py)
- [cases/directions/adapter/__init__.py](cases/directions/adapter/__init__.py)
- [cases/directions/adapter/composition.py](cases/directions/adapter/composition.py)
- [cases/directions/bias/__init__.py](cases/directions/bias/__init__.py)
- [cases/directions/build_solver.py](cases/directions/build_solver.py)
- [cases/directions/build_trainer.py](cases/directions/build_trainer.py)
- [cases/directions/catalog/entries/plugin.toml](cases/directions/catalog/entries/plugin.toml)
- [cases/directions/catalog/entries/problem.toml](cases/directions/catalog/entries/problem.toml)
- [cases/directions/config.py](cases/directions/config.py)
- [cases/directions/evaluation/__init__.py](cases/directions/evaluation/__init__.py)
- [cases/directions/pipeline/__init__.py](cases/directions/pipeline/__init__.py)
- [cases/directions/pipeline/main.py](cases/directions/pipeline/main.py)
- [cases/directions/plugins/__init__.py](cases/directions/plugins/__init__.py)
- [cases/directions/plugins/trace.py](cases/directions/plugins/trace.py)
- [cases/directions/problem/__init__.py](cases/directions/problem/__init__.py)
- [cases/directions/problem/two_targets.py](cases/directions/problem/two_targets.py)
- [cases/directions/run_solver.py](cases/directions/run_solver.py)
- [cases/directions/run_trainer.py](cases/directions/run_trainer.py)
- [cases/directions/runtime/__init__.py](cases/directions/runtime/__init__.py)
- [cases/directions/solver/__init__.py](cases/directions/solver/__init__.py)
- [cases/hybrid_search/.case](cases/hybrid_search/.case)
- [cases/hybrid_search/__init__.py](cases/hybrid_search/__init__.py)
- [cases/hybrid_search/adapter/__init__.py](cases/hybrid_search/adapter/__init__.py)
- [cases/hybrid_search/adapter/composition.py](cases/hybrid_search/adapter/composition.py)
- [cases/hybrid_search/adapter/operations.py](cases/hybrid_search/adapter/operations.py)
- [cases/hybrid_search/bias/__init__.py](cases/hybrid_search/bias/__init__.py)
- [cases/hybrid_search/build_solver.py](cases/hybrid_search/build_solver.py)
- [cases/hybrid_search/build_trainer.py](cases/hybrid_search/build_trainer.py)
- [cases/hybrid_search/catalog/entries/components.toml](cases/hybrid_search/catalog/entries/components.toml)
- [cases/hybrid_search/config.py](cases/hybrid_search/config.py)
- [cases/hybrid_search/evaluation/__init__.py](cases/hybrid_search/evaluation/__init__.py)
- [cases/hybrid_search/evaluation/provider.py](cases/hybrid_search/evaluation/provider.py)
- [cases/hybrid_search/pipeline/__init__.py](cases/hybrid_search/pipeline/__init__.py)
- [cases/hybrid_search/pipeline/main.py](cases/hybrid_search/pipeline/main.py)
- [cases/hybrid_search/pipeline/population.py](cases/hybrid_search/pipeline/population.py)
- [cases/hybrid_search/pipeline/repair.py](cases/hybrid_search/pipeline/repair.py)
- [cases/hybrid_search/plugins/__init__.py](cases/hybrid_search/plugins/__init__.py)
- [cases/hybrid_search/plugins/trace.py](cases/hybrid_search/plugins/trace.py)
- [cases/hybrid_search/problem/__init__.py](cases/hybrid_search/problem/__init__.py)
- [cases/hybrid_search/problem/recipe.py](cases/hybrid_search/problem/recipe.py)
- [cases/hybrid_search/run_solver.py](cases/hybrid_search/run_solver.py)
- [cases/hybrid_search/run_trainer.py](cases/hybrid_search/run_trainer.py)
- [cases/hybrid_search/runtime/__init__.py](cases/hybrid_search/runtime/__init__.py)
- [cases/hybrid_search/solver/__init__.py](cases/hybrid_search/solver/__init__.py)
- [cases/inner_response/.case](cases/inner_response/.case)
- [cases/inner_response/__init__.py](cases/inner_response/__init__.py)
- [cases/inner_response/adapter/__init__.py](cases/inner_response/adapter/__init__.py)
- [cases/inner_response/bias/__init__.py](cases/inner_response/bias/__init__.py)
- [cases/inner_response/build_solver.py](cases/inner_response/build_solver.py)
- [cases/inner_response/build_trainer.py](cases/inner_response/build_trainer.py)
- [cases/inner_response/catalog/entries/pipeline.toml](cases/inner_response/catalog/entries/pipeline.toml)
- [cases/inner_response/catalog/entries/plugin.toml](cases/inner_response/catalog/entries/plugin.toml)
- [cases/inner_response/catalog/entries/problem.toml](cases/inner_response/catalog/entries/problem.toml)
- [cases/inner_response/config.py](cases/inner_response/config.py)
- [cases/inner_response/evaluation/__init__.py](cases/inner_response/evaluation/__init__.py)
- [cases/inner_response/pipeline/__init__.py](cases/inner_response/pipeline/__init__.py)
- [cases/inner_response/pipeline/main.py](cases/inner_response/pipeline/main.py)
- [cases/inner_response/pipeline/operators.py](cases/inner_response/pipeline/operators.py)
- [cases/inner_response/plugins/__init__.py](cases/inner_response/plugins/__init__.py)
- [cases/inner_response/plugins/trace.py](cases/inner_response/plugins/trace.py)
- [cases/inner_response/problem/__init__.py](cases/inner_response/problem/__init__.py)
- [cases/inner_response/problem/response.py](cases/inner_response/problem/response.py)
- [cases/inner_response/run_solver.py](cases/inner_response/run_solver.py)
- [cases/inner_response/run_trainer.py](cases/inner_response/run_trainer.py)
- [cases/inner_response/runtime/__init__.py](cases/inner_response/runtime/__init__.py)
- [cases/inner_response/solver/__init__.py](cases/inner_response/solver/__init__.py)
- [cases/inner_response/solver/case.py](cases/inner_response/solver/case.py)
- [cases/outer_nested/.case](cases/outer_nested/.case)
- [cases/outer_nested/__init__.py](cases/outer_nested/__init__.py)
- [cases/outer_nested/adapter/__init__.py](cases/outer_nested/adapter/__init__.py)
- [cases/outer_nested/bias/__init__.py](cases/outer_nested/bias/__init__.py)
- [cases/outer_nested/build_solver.py](cases/outer_nested/build_solver.py)
- [cases/outer_nested/build_trainer.py](cases/outer_nested/build_trainer.py)
- [cases/outer_nested/catalog/entries/plugin.toml](cases/outer_nested/catalog/entries/plugin.toml)
- [cases/outer_nested/catalog/entries/problem.toml](cases/outer_nested/catalog/entries/problem.toml)
- [cases/outer_nested/config.py](cases/outer_nested/config.py)
- [cases/outer_nested/evaluation/__init__.py](cases/outer_nested/evaluation/__init__.py)
- [cases/outer_nested/pipeline/__init__.py](cases/outer_nested/pipeline/__init__.py)
- [cases/outer_nested/pipeline/main.py](cases/outer_nested/pipeline/main.py)
- [cases/outer_nested/plugins/__init__.py](cases/outer_nested/plugins/__init__.py)
- [cases/outer_nested/plugins/trace.py](cases/outer_nested/plugins/trace.py)
- [cases/outer_nested/problem/__init__.py](cases/outer_nested/problem/__init__.py)
- [cases/outer_nested/problem/nested.py](cases/outer_nested/problem/nested.py)
- [cases/outer_nested/run_solver.py](cases/outer_nested/run_solver.py)
- [cases/outer_nested/run_trainer.py](cases/outer_nested/run_trainer.py)
- [cases/outer_nested/runtime/__init__.py](cases/outer_nested/runtime/__init__.py)
- [cases/outer_nested/solver/__init__.py](cases/outer_nested/solver/__init__.py)
- [cases/outer_nested/solver/case.py](cases/outer_nested/solver/case.py)

## project_config.py

真实文件：[project_config.py](project_config.py)。

SHA-256：`82e5d923dc45e599f99b043eac6da259333ceb2acdb922edd7a1f255f48b66b4`。

```python
"""先并行求解，再带权威 Artifact 进入真正的嵌套 Case；L0 只在 Project。"""
PROJECT_NAME = "assembly_workbench"

L0 = {
    "namespace": "assembly_workbench",
    "offer": {"threads": 4, "workers": 4, "gpus": 0, "backend": "local", "device_tokens": []},
    "policy": {"mode": "strict", "max_workers": 4, "max_threads": 4,
               "gpu_sharing": "exclusive", "cpu_oversubscribe": False},
    "default_request": {"threads": 1, "workers": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto", "execution_backend": "local",
    "lease_backend": "sqlite", "lease_path": ".blackbase/l0_leases.sqlite",
    "lease_ttl_seconds": 30, "lease_heartbeat_seconds": 10,
    "artifacts": {"path": ".blackbase/artifacts", "allow_unsafe_serializers": False},
    "budgets": {"evaluations": 256},
}

SEARCH_REQUEST = {"threads": 1, "workers": 1, "gpus": 0, "backend": "local"}
NESTED_REQUEST = {"threads": 2, "workers": 2, "gpus": 0, "backend": "local"}
BASELINE_INPUTS = {"hybrid_summary": "hybrid_search.summary", "directions_summary": "directions.summary"}

STAGES = [
    {"name": "searches", "policy": "parallel", "max_workers": 2,
     "cases": ["hybrid_search", "directions"],
     "case_modes": {"hybrid_search": "build", "directions": "build"},
     "resource_requests": {"hybrid_search": SEARCH_REQUEST, "directions": SEARCH_REQUEST}},
    {"name": "nested", "policy": "serial", "cases": ["outer_nested"],
     "case_modes": {"outer_nested": "build"},
     "input_artifacts": {"outer_nested": BASELINE_INPUTS},
     "resource_requests": {"outer_nested": NESTED_REQUEST}},
    {"name": "hybrid_only", "policy": "serial", "cases": ["hybrid_search"]},
    {"name": "provider_path", "policy": "serial", "cases": ["hybrid_search"],
     "component_overrides": {"hybrid_search": {"config": {"evaluation_mode": "provider"}}}},
    {"name": "directions_only", "policy": "serial", "cases": ["directions"]},
    {"name": "directions_random", "policy": "serial", "cases": ["directions"],
     "component_overrides": {"directions": {"config": {"direction_sample": 2}}}},
    {"name": "parallel_refinement", "policy": "serial", "cases": ["directions"],
     "component_overrides": {"directions": {"config": {"refinement_layout": "parallel"}}}},
    {"name": "inner_only", "policy": "serial", "cases": ["inner_response"]},
    {"name": "nested_only", "policy": "serial", "cases": ["outer_nested"],
     "resource_requests": {"outer_nested": NESTED_REQUEST}},
    {"name": "workflow", "policy": "dag", "max_workers": 2,
     "cases": ["hybrid_search", "directions", "outer_nested"],
     "case_modes": {name: "build" for name in ("hybrid_search", "directions", "outer_nested")},
     "input_artifacts": {"outer_nested": BASELINE_INPUTS},
     "resource_requests": {"hybrid_search": SEARCH_REQUEST,
                           "directions": SEARCH_REQUEST, "outer_nested": NESTED_REQUEST}},
]

GROUPS = {
    "default": {"stages": ["searches", "nested"]},
    "dag": {"stages": ["workflow"]},
    "hybrid": {"stages": ["hybrid_only"]},
    "provider": {"stages": ["provider_path"]},
    "directions": {"stages": ["directions_only"]},
    "random_directions": {"stages": ["directions_random"]},
    "parallel_refiners": {"stages": ["parallel_refinement"]},
    "inner": {"stages": ["inner_only"]},
    "nested": {"stages": ["nested_only"]},
}
```

## run_project.py

真实文件：[run_project.py](run_project.py)。

SHA-256：`c44d88246da7275246736859b7924e1fecba9ed4ab53436ba7a3571efa87496c`。

```python
"""标准 Project CLI；--group 切换装配场景，--check --build-check 检查真实构建。"""
from pathlib import Path
from nsgablack.project.project_runner import main


if __name__ == "__main__":
    raise SystemExit(main(Path(__file__).resolve().parent))
```

## run_and_report.py

真实文件：[run_and_report.py](run_and_report.py)。

SHA-256：`ffb97b02c0491dac8ff9402e862d94f4d82183efdf9a7005d738127f63b60f15`。

```python
"""调用正式 Project runner，校验运行身份后整理教学报告；不实现搜索或调度。"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from nsgablack.project.project_runner import execute_project
from nsgablack.utils.engineering.file_io import atomic_write_text


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"


def write_json(path, payload):
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False))


def summarize(project, *, wall_seconds):
    if project["exit_code"] or project["status"] != "ok":
        raise RuntimeError("Project failed; inspect results/project_result.json")
    cases = {}
    for case in project["cases"]:
        name, identity = case["request"]["case_name"], case["identity"]
        if not case["ok"] or identity["project_run_id"] != project["run_id"]:
            raise ValueError(f"{name}: Case did not succeed in this Project run")
        resources = case["resource_usage"]
        if not resources["binding"]["current"]:
            raise ValueError(f"{name}: effective L0 resource binding is stale")
        if "summary" not in case["artifact_publications"]:
            raise ValueError(f"{name}: no authoritative summary publication")
        output = case["output"]
        runtime_state = case["metadata"].get("runtime_state", {})
        assembled = {key: runtime_state[key] for key in (
            "case_class", "problem", "pipeline", "adapter", "initializer", "mutator", "repair",
            "providers", "provider_names", "plugin_names", "adapter_components") if key in runtime_state}
        trace_path = RESULTS / name / "trace.json"
        trace = None
        if trace_path.is_file():
            trace = json.loads(trace_path.read_text(encoding="utf-8-sig"))
            if not trace["run_id"].startswith(identity["case_run_id"] + ":solver-run:"):
                raise ValueError(f"{name}: trace belongs to an older/different run")
        cases[name] = {
            "case_run_id": identity["case_run_id"], "status": case["status"],
            "logical_steps": output["report"]["steps"],
            "evaluations": output["report"]["evaluation_count"],
            "best_solution": output.get("best_solution"),
            "best_objectives": output.get("best_objectives"),
            "best_candidate_token": output.get("best_candidate_token"),
            "assembled": assembled,
            "grant": resources["authorized_grant"],
            "namespace": resources["effective_context"]["namespace"],
            "resource_binding_current": True,
            "started_at": case["started_at"], "finished_at": case["finished_at"],
            "artifact_refs": case["artifact_refs"],
            "artifact_publications": case["artifact_publications"],
            "input_bindings": case["request"]["input_artifact_bindings"],
            "trace_file": None if trace is None else str(trace_path.relative_to(ROOT)),
        }
    topology = {"project_group": project["group"], "top_level_cases": list(cases)}
    if {"hybrid_search", "directions", "outer_nested"}.issubset(cases):
        first = [cases["hybrid_search"], cases["directions"]]
        overlap = max(0., min(row["finished_at"] for row in first)
                      - max(row["started_at"] for row in first))
        outer = cases["outer_nested"]
        if outer["started_at"] < max(row["finished_at"] for row in first):
            raise ValueError("outer Case started before its upstream publications completed")
        bindings = outer["input_bindings"]
        expected = {"hybrid_summary": "hybrid_search.summary", "directions_summary": "directions.summary"}
        if set(bindings) != set(expected):
            raise ValueError("outer Case is missing one declared authoritative input")
        for name, key in expected.items():
            if bindings[name] != project["artifact_bindings"][key]:
                raise ValueError("downstream ArtifactBinding differs from the producer publication")
        topology.update(lifecycle_overlap_seconds=overlap,
                        observed_parallel_lifecycles=overlap > 0.,
                        upstream_artifacts_verified=True, downstream_after_both=True)
    return {"project_run_id": project["run_id"], "group": project["group"],
            "status": project["status"], "wall_seconds": wall_seconds,
            "manifest_path": project["manifest_path"], "cases": cases,
            "topology": topology,
            "artifact_names": sorted(project["artifact_registry"]),
            "scope": "装配、交接、授权与运行身份验证；不比较不同问题上的算法性能"}


def write_report(summary):
    lines = ["# 综合装配 Project：本次实际结果", "",
             f"Project run：`{summary['project_run_id']}`；group：`{summary['group']}`。", "",
             f"正式 manifest：`{summary['manifest_path']}`。", ""]
    for name, case in summary["cases"].items():
        assembled = case["assembled"]
        component_line = ", ".join(f"{key}={assembled[key]}" for key in (
            "case_class", "problem", "pipeline", "adapter") if key in assembled)
        best = case["best_solution"]
        candidate = best.get("values") if isinstance(best, dict) else best
        grant = {key: case["grant"][key] for key in ("threads", "workers", "gpus", "backend")}
        published = sorted(case["artifact_publications"])
        archives = sum(name.startswith("evaluation-evidence-archive-") for name in published)
        named = [name for name in published if not name.startswith("evaluation-evidence-archive-")]
        lines += [f"## {name}", "",
                  f"- `{case['logical_steps']}` 次逻辑提交，`{case['evaluations']}` 次本层求值。",
                  f"- 最终候选：`{candidate}`；选择目标：`{case['best_objectives']}`。",
                  f"- 实际装配：`{component_line}`。",
                  f"- Plugins：`{assembled.get('plugin_names', [])}`；Providers：`{assembled.get('provider_names', [])}`。",
                  f"- L0 grant：`{grant}`，binding.current=`true`。",
                  f"- namespace：`{case['namespace']}`。",
                  f"- 权威发布：`{named}`，另有 `{archives}` 份求值证据归档。", ""]
    topology = summary["topology"]
    if "lifecycle_overlap_seconds" in topology:
        lines += ["## Project 交接", "",
                  f"- 两个上游 Case 生命周期重叠 `{topology['lifecycle_overlap_seconds']:.6f}` 秒。",
                  "- outer_nested 在两个上游发布完成后启动，输入绑定与生产者权威发布一致。",
                  "- 生命周期重叠不是 CPU 利用率或性能加速比测量。", ""]
    lines += ["## 如何读这些结果", "",
              "hybrid_search 的 raw 与 selection 不同：Bias 改软评分，原始约束接纳单独判断。",
              "directions 不加 Bias，保留多目标原始反馈，投影只用于任务比较。",
              "outer_nested 的本层求值次数是外层候选数；内层求解的开销与收据在 nested 报告中单独列出。",
              "各 Case 的目标含义不同，不用一个 best 分数对它们排优劣。", "",
              "- [结构化汇总](results/summary.json)",
              "- [完整正式返回值](results/project_result.json)",
              "- [主 Case 提交轨迹](results/hybrid_search/trace.json)",
              "- [方向与投影轨迹](results/directions/trace.json)",
              "- [装配教程](README.md)", "",
              "trace 是观察报告；跨 Case 使用 ArtifactBinding，不能把 JSON 文件名当权威引用。", ""]
    atomic_write_text(ROOT / "RESULTS_CN.md", "\n".join(lines))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", default="default")
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args(argv)
    if args.report_only:
        project = json.loads((RESULTS / "project_result.json").read_text(encoding="utf-8"))
        timing = json.loads((RESULTS / "timing.json").read_text(encoding="utf-8"))
        if timing["project_run_id"] != project["run_id"]:
            raise ValueError("timing and Project result are from different runs")
        wall_seconds = timing["wall_seconds"]
    else:
        started = time.perf_counter()
        result = execute_project(ROOT, group=args.group)
        project = result.as_dict()
        wall_seconds = time.perf_counter() - started
        write_json(RESULTS / "project_result.json", project)
        write_json(RESULTS / "timing.json", {"project_run_id": project["run_id"],
                                           "wall_seconds": wall_seconds})
        if not result.ok:
            return result.exit_code or 1
    summary = summarize(project, wall_seconds=wall_seconds)
    write_json(RESULTS / "summary.json", summary)
    write_report(summary)
    print(json.dumps({"project_run_id": project["run_id"], "group": project["group"],
                      "cases": {name: {key: case[key] for key in ("logical_steps", "evaluations")}
                                for name, case in summary["cases"].items()},
                      "report": str(ROOT / "RESULTS_CN.md")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

## cases/directions/.case

真实文件：[cases/directions/.case](cases/directions/.case)。

SHA-256：`80f43707116a8fa2067cb132e65362ec651b013937966eb5013827673cb2e6b1`。

```text
name = directions
kind = solver
framework = nsgablack
```

## cases/directions/__init__.py

真实文件：[cases/directions/__init__.py](cases/directions/__init__.py)。

SHA-256：`ccf166fe0dbcec0f26f3eaaadb1e1848cb84d3dc4858d3416e1ca098082ae0b2`。

```python
"""按方向投影的两层局部精修 Case。"""
```

## cases/directions/adapter/__init__.py

真实文件：[cases/directions/adapter/__init__.py](cases/directions/adapter/__init__.py)。

SHA-256：`a765db0f006cc3ff2f3838e0dd6c55353973ec2c79d1b546a23633f5ae332095`。

```python
from .composition import build_adapter

__all__ = ["build_adapter"]
```

## cases/directions/adapter/composition.py

真实文件：[cases/directions/adapter/composition.py](cases/directions/adapter/composition.py)。

SHA-256：`c1eb35e8e6605372f32246febbdedb99529310cf8bf184fb80809e85296108f1`。

```python
"""相同的池任务接上 VNS 和 Pattern Search，不私写嵌套求解循环。"""
from nsgablack.adapters import (
    MOEADAdapter, MultiStrategyConfig, PatternSearchAdapter, PoolTaskSpec,
    SearchPlanAdapter, StrategySpec, VNSAdapter, multi, serial, stage, subpools,
)
from nsgablack.representation import ContextGaussianMutation, GaussianMutation, UniformInitializer


def fine_results(control, context):
    """只交回本次任务的最终选择；不把历次已接纳试探当作结果。"""
    del context
    return control.adapter.get_pool_task_results(control, "fine")


def parallel_results(control, context):
    """两个独立精修分支的精确最终引用，按明确分支顺序交回。"""
    del context
    root = control.adapter
    return (root.get_pool_task_results(control, "coarse")
            + root.get_pool_task_results(control, "fine"))


def build_adapter(settings):
    moead = MOEADAdapter(
        name="direction_owner", population_size=settings.directions, batch_size=3,
        neighborhood_size=3, decomposition="tchebycheff", random_seed=settings.seed,
        initializer=UniformInitializer(low=-2.0, high=2.0),
        mutator=GaussianMutation(sigma=0.3),
    )
    coarse = VNSAdapter(name="coarse_vns", batch_size=1, base_sigma=0.35,
        restart_on_stagnation=False, mutator=ContextGaussianMutation(base_sigma=0.35))
    # The task/return wiring is unchanged if this instance is replaced with
    # another projection-capable refiner. Pattern Search polls two directions
    # in one dimension; its native geometry remains owned by this Adapter.
    fine = PatternSearchAdapter(name="fine_pattern", max_directions=1, step_size=0.08)
    directions = (subpools.all(moead) if settings.direction_sample is None
                  else subpools.random(settings.direction_sample, moead))
    parallel = settings.refinement_layout == "parallel"
    refinements = (multi(stage("coarse"), stage("fine")) if parallel
                   else serial(stage("coarse"), stage("fine")))
    return SearchPlanAdapter(
        serial(stage("moead", steps=settings.bootstrap_steps, label="search"),
               refinements, stage("moead", label="return")),
        strategies=[
            StrategySpec(moead, "moead", pool_task=PoolTaskSpec(parallel_results if parallel else fine_results,
                mode="compete", phases=("return",), shuffle=False)),
            StrategySpec(coarse, "coarse", pool_task=PoolTaskSpec(directions,
                count=1, steps=settings.local_steps, output=None, shuffle=False)),
            StrategySpec(fine, "fine", pool_task=PoolTaskSpec(directions if parallel else subpools.all(coarse),
                count=1, steps=settings.local_steps, output=None, shuffle=False)),
        ], config=MultiStrategyConfig(total_batch_size=settings.router_budget, adapt_weights=False),
        name="direction_plan",
    )
```

## cases/directions/bias/__init__.py

真实文件：[cases/directions/bias/__init__.py](cases/directions/bias/__init__.py)。

SHA-256：`6f316c853ed72180d7738ea5e56aab196623473ebaa38046d3ecd6595a7b57a4`。

```python
"""本例不叠加 Bias，便于直接对账原始双目标与方向投影。"""
```

## cases/directions/build_solver.py

真实文件：[cases/directions/build_solver.py](cases/directions/build_solver.py)。

SHA-256：`adf04cd9ccb528be021f3885010282ee3e0d1918ea956b0c728bee70b3a356bb`。

```python
"""本 Case 唯一装配入口：Problem/Pipeline/Adapter/Plugin 都是显式组件。"""
from pathlib import Path

from nsgablack.core import ComposableSolver
from nsgablack.plugins import ParetoArchivePlugin
from nsgablack.project import apply_solver_component_overrides

from .adapter import build_adapter
from .config import DirectionsConfig
from .pipeline import build_pipeline
from .plugins import DirectionTrace
from .problem import build_problem


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    overrides = dict(component_overrides or {})
    settings = DirectionsConfig(**{**dict(config or {}), **dict(overrides.pop("config", {}))})
    output_dir = (Path(settings.output_dir) if settings.output_dir is not None
                  else Path(__file__).resolve().parents[2] / "results" / "directions")
    solver = ComposableSolver(problem=build_problem(), representation_pipeline=build_pipeline(),
        adapter=build_adapter(settings), resource_context=resource_context,
        plugin_strict=True, snapshot_strict=True)
    solver.set_random_seed(settings.seed)
    solver.set_max_steps(settings.max_steps)
    solver.add_plugin(ParetoArchivePlugin())
    solver.add_plugin(DirectionTrace(output_dir=output_dir, settings=settings))
    apply_solver_component_overrides(solver, overrides)
    return solver
```

## cases/directions/build_trainer.py

真实文件：[cases/directions/build_trainer.py](cases/directions/build_trainer.py)。

SHA-256：`99f765e75df055fdefa2b0a2bbdc035a77c5669466fcb9bbd15da6e21a2b468f`。

```python
from .build_solver import build_solver as build_trainer
```

## cases/directions/catalog/entries/plugin.toml

真实文件：[cases/directions/catalog/entries/plugin.toml](cases/directions/catalog/entries/plugin.toml)。

SHA-256：`175365677b7b23ae0596e08a228891f6bb7a157c0c0b3f760652359d7b9c8b50`。

```toml
[[entry]]
key = "project.plugin.workbench_direction_trace"
title = "DirectionTrace"
kind = "plugin"
import_path = "plugins.trace:DirectionTrace"
tags = ["project", "example", "plugin", "observe", "finalization", "subpool", "lineage"]
summary = "只读汇总方向与精修证据，经 Case 最终事务发布 summary，并保存观察轨迹。"
context_requires = []
context_provides = []
context_mutates = []
context_cache = []
context_notes = ["观察文件不替代 Artifact；summary 经共享 Case finalization 事务发布，严格失败可否决。"]
use_when = ["核对嵌套方向精修与精确最终结果交付时。"]
minimal_wiring = ["from cases.directions.plugins import DirectionTrace", "solver.add_plugin(DirectionTrace(output_dir=path, settings=settings))"]
required_companions = ["nsgablack.core:ComposableSolver"]
config_keys = ["output_dir", "settings"]
example_entry = "cases.directions.build_solver:build_solver"
```

## cases/directions/catalog/entries/problem.toml

真实文件：[cases/directions/catalog/entries/problem.toml](cases/directions/catalog/entries/problem.toml)。

SHA-256：`d3adfbc4f0861021fcf5198415608321776c0c8dc0618ccd019f2857ac5c2960`。

```toml
[[entry]]
key = "project.problem.workbench_directions"
title = "DirectionProblem"
kind = "tool"
import_path = "problem.two_targets:DirectionProblem"
tags = ["project", "example", "problem", "multi_objective"]
summary = "双目标 f=[(x-1)^2,(x+1)^2]，供方向投影与精修结果对账。"
context_requires = []
context_provides = []
context_mutates = []
context_cache = []
context_notes = ["只定义原始目标与边界约束。"]
use_when = ["展示 MOEA/D、VNS、Pattern Search 的同池装配时。"]
minimal_wiring = ["from cases.directions.problem import DirectionProblem", "problem = DirectionProblem()"]
required_companions = []
config_keys = []
example_entry = "cases.directions.build_solver:build_solver"
```

## cases/directions/config.py

真实文件：[cases/directions/config.py](cases/directions/config.py)。

SHA-256：`0e76684547293725768fa3ae1c3e51d8cebba01a63b8bab9d4b116d21ef60ec8`。

```python
"""算法规模与视图抽样；它们都不是解池容量。"""
from dataclasses import dataclass


@dataclass(frozen=True)
class DirectionsConfig:
    seed: int = 23
    directions: int = 3
    direction_sample: int | None = None
    refinement_layout: str = "serial"
    bootstrap_steps: int = 2
    local_steps: int = 2
    router_budget: int = 6
    output_dir: str | None = None

    def __post_init__(self):
        for name in ("seed", "directions", "bootstrap_steps", "local_steps", "router_budget"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        if self.directions < 3 or self.bootstrap_steps < 2 or self.local_steps < 2:
            raise ValueError("this example needs three directions and baseline plus search updates")
        if self.router_budget < self.directions:
            raise ValueError("router_budget must fit the bootstrap population")
        if self.direction_sample is not None and (type(self.direction_sample) is not int
                or not 1 <= self.direction_sample <= self.directions):
            raise ValueError("direction_sample must be None or within the direction count")
        if self.output_dir is not None and (not isinstance(self.output_dir, str) or not self.output_dir.strip()):
            raise ValueError("output_dir must be a nonempty path string")
        if self.refinement_layout not in {"serial", "parallel"}:
            raise ValueError("refinement_layout must be serial or parallel")
        if self.refinement_layout == "parallel" and self.router_budget < max(4, 2 * self.selected_directions):
            raise ValueError("parallel router_budget must fit both poll proposals and all final returns")

    @property
    def selected_directions(self):
        return self.directions if self.direction_sample is None else self.direction_sample

    @property
    def max_steps(self):
        # Every seed gets its own baseline and local updates. Final winners
        # return together through one ordinary MOEA/D competition update.
        branches = 2 if self.refinement_layout == "serial" else 1
        return self.bootstrap_steps + branches * self.selected_directions * self.local_steps + 1
```

## cases/directions/evaluation/__init__.py

真实文件：[cases/directions/evaluation/__init__.py](cases/directions/evaluation/__init__.py)。

SHA-256：`ee3882a59d14f52b0e5c53257e15aeb870e9e89823d9c618ad41757dcd4920b1`。

```python
"""使用 Problem 的标准求值路径。"""
```

## cases/directions/pipeline/__init__.py

真实文件：[cases/directions/pipeline/__init__.py](cases/directions/pipeline/__init__.py)。

SHA-256：`2b7e90eec58336e81c6e3b8eddd64aacb65d8f17ac25bb88c72ff9ee82914efb`。

```python
from .main import build_pipeline

__all__ = ["build_pipeline"]
```

## cases/directions/pipeline/main.py

真实文件：[cases/directions/pipeline/main.py](cases/directions/pipeline/main.py)。

SHA-256：`e989a82df608d0c760eadbd40e3ae30276c2cbd0563b13a418a7e434cd22c872`。

```python
"""所有算法复用同一问题修复；不复制整条 Pipeline。"""
from nsgablack.representation import ClipRepair, RepresentationPipeline


def build_pipeline():
    return RepresentationPipeline(repair=ClipRepair(low=-2.0, high=2.0))
```

## cases/directions/plugins/__init__.py

真实文件：[cases/directions/plugins/__init__.py](cases/directions/plugins/__init__.py)。

SHA-256：`538e569fdac41de3c87aa24afde38129b61bc1eddb489a7c0b44c1f4f0979226`。

```python
from .trace import DirectionTrace

__all__ = ["DirectionTrace"]
```

## cases/directions/plugins/trace.py

真实文件：[cases/directions/plugins/trace.py](cases/directions/plugins/trace.py)。

SHA-256：`0c09b8be518b5c8aaec4e9c61b24bd1769d2d4b11e8dfe6c4575b487b09b7207`。

```python
"""有界只读轨迹；正式权威结果仍由标准 Case/Project 发布。"""
from collections.abc import Mapping
from dataclasses import asdict
import json
from pathlib import Path

from blackbase.participation import ParticipationContract
from nsgablack.adapters import StrategyOrigin
from nsgablack.adapters.subpools import adapter_path
from nsgablack.plugins.base import Plugin
from nsgablack.utils.engineering.file_io import atomic_write_text


def data_copy(value):
    return json.loads(json.dumps(value, allow_nan=False))


class DirectionTrace(Plugin):
    participation = ParticipationContract(vetoes=("finalization",))
    state_recovery_level = "L1"
    state_recovery_notes = "Bounded committed observations with an explicit JSON state codec."
    context_requires = context_provides = context_mutates = context_cache = ()
    context_notes = ("Read-only pool, task and Unit observations; never constructs a Unit.",)

    def __init__(self, *, output_dir, settings):
        super().__init__(name="direction_trace")
        self.output_dir, self.settings = Path(output_dir), settings
        self.run_id, self.initial, self.records = None, None, []
        self.last_sequence, self.last_evaluations = 0, 0

    def _roles(self):
        root, pool = self.solver.adapter, self.solver.solution_pool
        rows = []
        for unit in root.units:
            wrapper, inner = unit.adapter, unit.adapter.inner
            path = adapter_path(root, inner)
            views = pool.subpools_created_by(path)
            rows.append(dict(role=unit.role, owner_path=list(path), adapter_type=type(inner).__name__,
                task=wrapper.task_status,
                unit_exists=getattr(inner, "algorithm_unit", None) is not None,
                current_unit_exists=getattr(inner, "current_unit", None) is not None,
                neighborhood_unit_exists=getattr(inner, "neighborhood_unit", None) is not None,
                views=[dict(descriptor=pool.subpool_descriptor(name),
                    projection=pool.subpool_metadata(name).get("projection")) for name in views]))
        return rows

    def on_solver_init(self, solver):
        if self.run_id != solver.run_session.run_id:
            self.run_id, self.records = solver.run_session.run_id, []
            self.last_sequence, self.last_evaluations = 0, 0
            self.initial = dict(clock=solver.solution_pool.timestamp.as_dict(), roles=self._roles())

    def on_generation_committed(self, generation, outcome):
        del generation
        if not outcome.get("committed", False) or len(self.records) >= self.settings.max_steps:
            raise ValueError("direction trace expects one bounded committed observation")
        solver, pool = self.solver, self.solver.solution_pool
        refs = tuple(ref for ref in pool.select()
                     if pool.stamp_for(ref).sequence > self.last_sequence)
        phases = {origin.phase for state in pool.read(refs).semantic_states
                  for origin in StrategyOrigin.from_candidate(state)}
        if not phases or (len(phases) > 1 and phases != {"coarse", "fine"}):
            raise ValueError("direction plan observed unexpected proposal phases")
        phase = next(iter(phases)) if len(phases) == 1 else "parallel"
        evaluations = int(solver.evaluation_count)
        self.records.append(dict(step=int(solver.run_progress_steps), phase=phase, phases=sorted(phases),
            evaluation_delta=evaluations - self.last_evaluations,
            evaluations=evaluations, clock=pool.timestamp.as_dict(),
            accepted_refs=[ref.as_dict() for ref in refs], roles=self._roles()))
        self.last_sequence, self.last_evaluations = pool.timestamp.sequence, evaluations

    def _values(self, refs):
        pool = self.solver.solution_pool
        raw_f, raw_v = pool.read_raw_feedback(refs)
        return dict(refs=[ref.as_dict() for ref in refs],
            candidates=pool.read(refs).numeric_matrix.tolist(),
            raw_objectives=raw_f.tolist(), raw_violations=raw_v.tolist())

    def _summary(self):
        """Read committed results without evaluating or changing pool owners."""
        solver, root, pool = self.solver, self.solver.adapter, self.solver.solution_pool
        tasks, views, receipts = {}, {}, {}
        for unit in root.units:
            wrapper, inner = unit.adapter, unit.adapter.inner
            tasks[unit.role] = wrapper.task_status
            receipts[unit.role] = wrapper.get_state()["pool_task"].get("result_views", [])
            path = adapter_path(root, inner)
            views[unit.role] = [dict(name=name, metadata=pool.subpool_metadata(name),
                descriptor=pool.subpool_descriptor(name), **self._values(pool.subpool_refs(name)))
                for name in pool.subpools_created_by(path)]
        producer = next(unit.adapter.inner for unit in root.units if unit.role == "moead")
        population = self._values(producer.get_population_solution_refs(solver))
        population["adapter_objectives"] = producer.pop_F.tolist()
        archive = solver.get_plugin("pareto_archive")
        pareto = dict(size=archive.total_archive_size(),
            candidates=[] if archive.archive_X is None else archive.archive_X.tolist(),
            raw_objectives=[] if archive.archive_F is None else archive.archive_F.tolist())
        returned_roles = ("coarse", "fine") if self.settings.refinement_layout == "parallel" else ("fine",)
        final_refs = tuple(ref for role in returned_roles for ref in root.get_pool_task_results(solver, role))
        return dict(schema="assembly_workbench.directions/v1", run_id=self.run_id,
            settings=asdict(self.settings), refinement_layout=self.settings.refinement_layout,
            returned_roles=list(returned_roles), logical_steps=int(solver.run_progress_steps),
            evaluations=int(solver.evaluation_count), plan_completed=root.cursor.completed,
            pool_id=pool.pool_id, clock=pool.timestamp.as_dict(), tasks=tasks,
            views=views, result_receipts=receipts, final_results=self._values(final_refs),
            final_population=population, pareto=pareto,
            resource_binding_current=bool(getattr(solver, "resource_binding_audit", {}).get("current", False)))

    def on_solver_finalization_prepare(self, result):
        del result
        runtime = self.solver.case_runtime
        if runtime is None:
            return
        summary = self._summary()
        runtime.begin_finalization_transaction("case_finalization").publish(
            "summary", summary, serializer="json", kind="case-summary",
            metadata={"schema": summary["schema"]})

    def on_solver_finalized(self, result):
        del result
        summary = self._summary()
        trace = {**self.get_state(), "summary": summary}
        for name, payload in (("trace.json", trace), ("summary.json", summary)):
            atomic_write_text(self.output_dir / name,
                json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False))

    def get_state(self):
        return data_copy(dict(schema="assembly_workbench.direction_trace/v1",
            max_records=self.settings.max_steps, run_id=self.run_id, initial=self.initial,
            records=self.records, last_sequence=self.last_sequence,
            last_evaluations=self.last_evaluations))

    def set_state(self, state):
        if not isinstance(state, Mapping) or state.get("schema") != "assembly_workbench.direction_trace/v1":
            raise ValueError("invalid direction trace state")
        saved = data_copy(dict(state))
        if saved.get("max_records") != self.settings.max_steps or not isinstance(saved.get("records"), list):
            raise ValueError("direction trace capacity mismatch")
        if len(saved["records"]) > self.settings.max_steps:
            raise ValueError("direction trace capacity exceeded")
        self.run_id, self.initial, self.records = saved["run_id"], saved["initial"], saved["records"]
        self.last_sequence, self.last_evaluations = saved["last_sequence"], saved["last_evaluations"]
```

## cases/directions/problem/__init__.py

真实文件：[cases/directions/problem/__init__.py](cases/directions/problem/__init__.py)。

SHA-256：`68ba50d8328cf2d6ebf9638b52781415582b89303abc80b7a5e2225a6fe31feb`。

```python
from .two_targets import DirectionProblem, build_problem

__all__ = ["DirectionProblem", "build_problem"]
```

## cases/directions/problem/two_targets.py

真实文件：[cases/directions/problem/two_targets.py](cases/directions/problem/two_targets.py)。

SHA-256：`d48f734f846aad4b06dbd742a2982b3857e058df7b58f839742fb51288ee872e`。

```python
"""双目标始终属于 Problem；方向视图只改变局部搜索的比较含义。"""
import numpy as np
from nsgablack.core import BlackBoxProblem


class DirectionProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="direction_targets", dimension=1, objectives=["min", "min"],
                         bounds={"x": (-2.0, 2.0)})

    def evaluate(self, candidate):
        x = float(np.asarray(candidate).reshape(-1)[0])
        return [(x - 1.0) ** 2, (x + 1.0) ** 2]

    def evaluate_constraints(self, candidate):
        return [max(0.0, abs(float(np.asarray(candidate).reshape(-1)[0])) - 2.0)]


def build_problem():
    return DirectionProblem()
```

## cases/directions/run_solver.py

真实文件：[cases/directions/run_solver.py](cases/directions/run_solver.py)。

SHA-256：`0319c22b89e09726f624f19613b2522bf59f73bafad26cb6a8c77d68d4bdf875`。

```python
"""标准 Case CLI；直接运行、--check 与 Project 调用共用装配入口。"""
from blackbase.project import run_standard_case_cli


def main(argv=None):
    return run_standard_case_cli(__file__, framework="nsgablack", argv=argv)


if __name__ == "__main__":
    raise SystemExit(main())
```

## cases/directions/run_trainer.py

真实文件：[cases/directions/run_trainer.py](cases/directions/run_trainer.py)。

SHA-256：`4f99f55e1e24fa5f03008d1f38de8f0357f6f05e1ab3ee7af12043fa92ce8917`。

```python
from .run_solver import main
```

## cases/directions/runtime/__init__.py

真实文件：[cases/directions/runtime/__init__.py](cases/directions/runtime/__init__.py)。

SHA-256：`b22c923e5c8fd5884c2c70a2adc673fbb191fad5fdd61de994ecda79b9b61539`。

```python
"""资源由 Project 注入，不在 Case 内分配全局 lease。"""
```

## cases/directions/solver/__init__.py

真实文件：[cases/directions/solver/__init__.py](cases/directions/solver/__init__.py)。

SHA-256：`8cf64df39bd960f7a3a3c34a844632b046f4085a778a84576afc06a471ae4d36`。

```python
"""复用 ComposableSolver 控制面。"""
```

## cases/hybrid_search/.case

真实文件：[cases/hybrid_search/.case](cases/hybrid_search/.case)。

SHA-256：`14b84f266f057938d363566826bc902bdce494749e16380a6fdd157b3e10720e`。

```text
name = hybrid_search
kind = solver
framework = nsgablack
```

## cases/hybrid_search/__init__.py

真实文件：[cases/hybrid_search/__init__.py](cases/hybrid_search/__init__.py)。

SHA-256：`e5546a7d103be31863cd56f0fd90dd96077a6b754c72cfe42fc1e6a747f05beb`。

```python
"""带约束的配方搜索：Problem/Pipeline/Unit/Adapter/Bias/Plugin 完整装配。"""
```

## cases/hybrid_search/adapter/__init__.py

真实文件：[cases/hybrid_search/adapter/__init__.py](cases/hybrid_search/adapter/__init__.py)。

SHA-256：`a765db0f006cc3ff2f3838e0dd6c55353973ec2c79d1b546a23633f5ae332095`。

```python
from .composition import build_adapter

__all__ = ["build_adapter"]
```

## cases/hybrid_search/adapter/composition.py

真实文件：[cases/hybrid_search/adapter/composition.py](cases/hybrid_search/adapter/composition.py)。

SHA-256：`d91b9dc6c85e3d2c0851fa403016319762a9abc814d7a369d01c48149cd28c4a`。

```python
"""以 GA→VNS→GA 返回竞争表达两轮混合搜索。"""
from functools import partial

from nsgablack.adapters import MultiStrategyConfig, NSGA2Adapter, PoolTaskSpec, StrategySpec, VNSAdapter
from nsgablack.adapters.search_plan import SearchPlanAdapter, repeat, serial, stage
from nsgablack.units import UnitBinding

from ..pipeline.population import RecipePopulationBuilder
from .operations import choose_members_and_elite, crossover_then_mutate, select_elite, select_refined


def build_adapter(settings):
    ga = NSGA2Adapter(name="ga", population_size=settings.population_size,
        offspring_size=settings.population_size,
        unit_binding=UnitBinding(RecipePopulationBuilder()),
        change=partial(crossover_then_mutate, sigma=settings.ga_sigma),
        selector=partial(choose_members_and_elite, count=settings.population_size,
                         elite_count=settings.elite_count))
    vns = VNSAdapter(name="vns", batch_size=1, k_max=3, base_sigma=settings.vns_sigma,
                     scale=1.5, max_sigma=0.3, restart_on_stagnation=False)
    plan = SearchPlanAdapter(repeat(times=settings.rounds, body=serial(
        stage("ga", steps=settings.ga_steps, label="ga"),
        stage("vns", label="vns"), stage("ga", label="return"))),
        strategies=[
            StrategySpec(ga, "ga", pool_task=PoolTaskSpec(select_refined, mode="compete",
                phases=("return",), count="all", shuffle=False, change_sources=("elite",))),
            StrategySpec(vns, "vns", pool_task=PoolTaskSpec(select_elite, mode="refine",
                count="all", steps=settings.local_steps, shuffle=False, output="refined")),
        ], config=MultiStrategyConfig(total_batch_size=settings.population_size, adapt_weights=False),
        name="recipe_search")
    return plan
```

## cases/hybrid_search/adapter/operations.py

真实文件：[cases/hybrid_search/adapter/operations.py](cases/hybrid_search/adapter/operations.py)。

SHA-256：`df45e7ee493756c23b147bda3b1616e964c339932a37cf33a6985f982016b52f`。

```python
"""普通函数表达变化和选择；没有私有求解循环，也不直接发布候选。"""
from functools import partial

import numpy as np
from nsgablack.adapters import ChangeBatchResult, ChangeResult, Pool


def crossover_then_mutate(request, *, rng, sigma):
    left, right = request.parents
    alpha = rng.uniform(0.2, 0.8, size=left.shape)
    crossed = (alpha * left + (1. - alpha) * right,
               (1. - alpha) * left + alpha * right)
    children = [ChangeResult(child + rng.normal(0., sigma, size=child.shape))
                for child in crossed[:request.max_outputs]]
    return ChangeBatchResult(tuple(children))


def selection_key(pool):
    return np.column_stack((pool.violations > 1e-9, np.maximum(pool.violations, 0.),
                            pool.objectives[:, 0]))


def best(pool, *, count, rng):
    del rng
    return pool.top(min(count, len(pool)), key=selection_key)


def choose_members_and_elite(pool, *, count, elite_count, rng):
    # 主结果决定 GA 成员，副集合只保存其精英引用，两者一次提交。
    members = pool.chosen(partial(best, count=count), rng=rng)
    elite = Pool(parent=members, name="elite")
    elite.inject(members.chosen(partial(best, count=elite_count), rng=rng), replace=True)
    return members


def select_elite(control, context):
    return control.solution_pool.subpool_refs("elite")


def select_refined(control, context):
    return control.adapter.get_pool_task_results(control, "vns")
```

## cases/hybrid_search/bias/__init__.py

真实文件：[cases/hybrid_search/bias/__init__.py](cases/hybrid_search/bias/__init__.py)。

SHA-256：`5d905af569646317832ac537b604956370f0b4a7549714a980d5a2f810de01e0`。

```python
import numpy as np

from nsgablack.bias import BiasModule, DomainBias


class BalancedMixBias(DomainBias):
    """偏好原料比例较均衡；只改变选择评分，不改变 Problem 原始成本。"""
    objective_independent = True
    context_notes = "Soft imbalance penalty in the selection view; no context I/O."

    def __init__(self, weight=0.15):
        super().__init__(name="balanced_mix", weight=weight, mandatory=False)

    def compute(self, x, context):
        values = np.asarray(x, dtype=float)
        return float((values[0] - values[1]) ** 2)


def build_bias(weight):
    result = BiasModule()
    result.add(BalancedMixBias(weight))
    return result
```

## cases/hybrid_search/build_solver.py

真实文件：[cases/hybrid_search/build_solver.py](cases/hybrid_search/build_solver.py)。

SHA-256：`ac5f93abe129bfbf5bf0092aa2b7a52ab740d55e6d867371a317f435e1a196ca`。

```python
"""唯一装配入口：组件先组合，实际运行由正式 Case/Project 托管。"""
from pathlib import Path

from nsgablack.core import ComposableSolver
from nsgablack.core.control_plane import BudgetController
from nsgablack.core.evaluation_acceptance import FeasibleEvaluationAcceptance
from nsgablack.plugins import CheckpointResumeConfig, CheckpointResumePlugin
from nsgablack.project import apply_solver_component_overrides

from .adapter import build_adapter
from .bias import build_bias
from .config import HybridConfig
from .evaluation import RecipeProvider
from .pipeline import build_pipeline
from .plugins import WorkbenchTrace
from .problem import RecipeProblem


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    overrides = dict(component_overrides or {})
    settings = HybridConfig(**{**dict(config or {}), **dict(overrides.pop("config", {}))})
    output = (Path(settings.output_dir) if settings.output_dir is not None
              else Path(__file__).resolve().parents[2] / "results" / "hybrid_search")
    pipeline, _repair = build_pipeline(settings.vns_sigma)
    solver = ComposableSolver(RecipeProblem(), representation_pipeline=pipeline,
        adapter=build_adapter(settings), bias_module=build_bias(settings.bias_weight),
        resource_context=resource_context, snapshot_strict=True, plugin_strict=True)
    solver.set_random_seed(settings.seed)
    solver.set_max_steps(settings.max_steps)
    solver.set_evaluation_acceptance_policy(FeasibleEvaluationAcceptance())
    solver.register_controller(BudgetController(max_evaluations=settings.evaluation_budget))
    if settings.evaluation_mode == "provider":
        solver.register_evaluation_provider(RecipeProvider())
    solver.add_plugin(CheckpointResumePlugin(config=CheckpointResumeConfig(
        checkpoint_dir=str(output / "checkpoints"), save_every=settings.checkpoint_every,
        save_on_finish=True, keep_last=3, trusted_roots=(str((output / "checkpoints").resolve()),))))
    solver.add_plugin(WorkbenchTrace(output, settings.max_steps))
    apply_solver_component_overrides(solver, overrides)
    return solver
```

## cases/hybrid_search/build_trainer.py

真实文件：[cases/hybrid_search/build_trainer.py](cases/hybrid_search/build_trainer.py)。

SHA-256：`99f765e75df055fdefa2b0a2bbdc035a77c5669466fcb9bbd15da6e21a2b468f`。

```python
from .build_solver import build_solver as build_trainer
```

## cases/hybrid_search/catalog/entries/components.toml

真实文件：[cases/hybrid_search/catalog/entries/components.toml](cases/hybrid_search/catalog/entries/components.toml)。

SHA-256：`e4dfec3f6dfa7951afa282e1d9933cdf71cef4663087219fbc4609a539bf3a16`。

```toml
# Case-local paths are resolved under cases.hybrid_search by the Project registry.
[[entry]]
key = "project.problem.workbench_recipe"
title = "RecipeProblem"
kind = "tool"
import_path = "problem.recipe:RecipeProblem"
tags = ["project", "example", "problem", "constraints", "recipe"]
summary = "两维配方成本与盒约束、总量约束；独立定义原始求值。"
context_requires = []
context_provides = []
context_mutates = []
context_cache = []
context_notes = ["不读取 Unit 或算法状态，不使用选择偏好修改原始求值。"]
use_when = ["核对问题语义与搜索、偏好、硬接纳的边界时。"]
minimal_wiring = ["from cases.hybrid_search.problem import RecipeProblem", "problem = RecipeProblem()"]
required_companions = []
config_keys = []
example_entry = "cases.hybrid_search.build_solver:build_solver"

[[entry]]
key = "project.pipeline.workbench_recipe"
title = "RecipePipeline"
kind = "representation"
import_path = "pipeline.main:RecipePipeline"
tags = ["project", "example", "pipeline", "checkpoint", "codec"]
summary = "共享问题管线，显式保存初始化器、变异器 RNG 与修复观察计数。"
context_requires = []
context_provides = []
context_mutates = []
context_cache = []
context_notes = ["各叶组件状态由本例显式 codec 保存；不假设框架递归复制任意组件图。"]
use_when = ["需要完整复现本例管线的随机状态与观察状态时。"]
minimal_wiring = ["from cases.hybrid_search.pipeline import build_pipeline", "pipeline, repair = build_pipeline(0.06)"]
required_companions = ["nsgablack.representation:RepresentationPipeline"]
config_keys = ["initializer", "mutator", "repair"]
example_entry = "cases.hybrid_search.build_solver:build_solver"

[[entry]]
key = "project.pipeline.workbench_recipe_repair"
title = "RecipeRepair"
kind = "representation"
import_path = "pipeline.repair:RecipeRepair"
tags = ["project", "example", "pipeline", "repair", "constraints"]
summary = "将候选修复到坐标 [0,1] 与总量不超过 1.2；只处理候选值。"
context_requires = []
context_provides = []
context_mutates = []
context_cache = []
context_notes = ["calls/changed 仅为观察计数；不拥有成员选择、求值或池发布。"]
use_when = ["两个算法共享同一问题可行性处理时。"]
minimal_wiring = ["from cases.hybrid_search.pipeline import RecipeRepair", "repair = RecipeRepair()"]
required_companions = ["project.pipeline.workbench_recipe"]
config_keys = []
example_entry = "cases.hybrid_search.build_solver:build_solver"

[[entry]]
key = "project.unit.workbench_recipe_population"
title = "RecipePopulation"
kind = "tool"
import_path = "pipeline.population:RecipePopulation"
tags = ["project", "example", "unit", "population", "members"]
summary = "在标准种群上增加逐成员年龄，按 PopulationChange 精确传播。"
context_requires = []
context_provides = []
context_mutates = []
context_cache = []
context_notes = ["新增成员年龄为零，既存成员在环境选择中加一；不放进共享 context。"]
use_when = ["演示新增成员字段、来源索引与恢复 codec 时。"]
minimal_wiring = ["from cases.hybrid_search.pipeline.population import RecipePopulationBuilder", "binding = UnitBinding(RecipePopulationBuilder())"]
required_companions = ["project.unit.workbench_recipe_population_builder"]
config_keys = ["unit_id", "member_age"]
example_entry = "cases.hybrid_search.build_solver:build_solver"

[[entry]]
key = "project.unit.workbench_recipe_population_builder"
title = "RecipePopulationBuilder"
kind = "representation"
import_path = "pipeline.population:RecipePopulationBuilder"
tags = ["project", "example", "unit", "builder", "codec"]
summary = "按所属 GA 的需要构建年龄种群，复用标准 Unit 数据 codec。"
context_requires = []
context_provides = []
context_mutates = []
context_cache = []
context_notes = ["配置 builder 不创建运行 Unit；不在构建时修复候选。"]
use_when = ["在不修改 NSGA-II 源码的情况下扩展种群结构时。"]
minimal_wiring = ["from cases.hybrid_search.pipeline.population import RecipePopulationBuilder", "binding = UnitBinding(RecipePopulationBuilder())"]
required_companions = ["nsgablack.units:UnitBinding", "nsgablack.adapters:NSGA2Adapter"]
config_keys = []
example_entry = "cases.hybrid_search.build_solver:build_solver"

[[entry]]
key = "project.bias.workbench_balanced_mix"
title = "BalancedMixBias"
kind = "bias"
import_path = "bias:BalancedMixBias"
tags = ["project", "example", "bias", "soft_preference"]
summary = "对两原料不均衡程度添加软偏好，只作用于选择评分。"
context_requires = []
context_provides = []
context_mutates = []
context_cache = []
context_notes = ["原始成本与约束仍由 Problem 定义；硬可行性接纳不使用软化结果。"]
use_when = ["演示 raw 与 selection 反馈分离时。"]
minimal_wiring = ["from cases.hybrid_search.bias import build_bias", "bias = build_bias(0.15)"]
required_companions = ["nsgablack.bias:BiasModule"]
config_keys = ["weight"]
example_entry = "cases.hybrid_search.build_solver:build_solver"

[[entry]]
key = "project.provider.workbench_recipe"
title = "RecipeProvider"
kind = "tool"
import_path = "evaluation.provider:RecipeProvider"
tags = ["project", "example", "evaluation", "provider", "equivalent"]
summary = "显式注册的等价向量化求值 Provider，使用同一配方公式与原始约束。"
context_requires = []
context_provides = []
context_mutates = []
context_cache = []
context_notes = ["can_handle 是交付承诺；命中后不调用 Problem.evaluate，求值仍计入运行预算。"]
use_when = ["通过 evaluation_mode=provider 观察正式求值短路时。"]
minimal_wiring = ["from cases.hybrid_search.evaluation import RecipeProvider", "solver.register_evaluation_provider(RecipeProvider())"]
required_companions = ["project.problem.workbench_recipe"]
config_keys = []
example_entry = "cases.hybrid_search.build_solver:build_solver"

[[entry]]
key = "project.plugin.workbench_hybrid_trace"
title = "WorkbenchTrace"
kind = "plugin"
import_path = "plugins.trace:WorkbenchTrace"
tags = ["project", "example", "plugin", "observe", "finalization", "artifact"]
summary = "观察已提交池与 Unit，在严格 finalization 检查后事务发布 summary。"
context_requires = []
context_provides = []
context_mutates = []
context_cache = []
context_notes = ["不为了观察而创建 Unit；trace.json 是报告，summary Artifact 通过正式收据交付。"]
use_when = ["核对搜索阶段、精确引用、年龄、raw/selection 与最终发布一致性时。"]
minimal_wiring = ["from cases.hybrid_search.plugins import WorkbenchTrace", "solver.add_plugin(WorkbenchTrace(output_dir=path, max_records=settings.max_steps))"]
required_companions = ["nsgablack.core:ComposableSolver"]
config_keys = ["output_dir", "max_records"]
example_entry = "cases.hybrid_search.build_solver:build_solver"
```

## cases/hybrid_search/config.py

真实文件：[cases/hybrid_search/config.py](cases/hybrid_search/config.py)。

SHA-256：`1dbfe05920d5d13b2734c0523da783ba5e1be49f8b4cd55fbe296d359710f8e2`。

```python
"""仅声明用户选择；种群大小、精英数和母池历史容量不是一回事。"""
from dataclasses import dataclass


@dataclass(frozen=True)
class HybridConfig:
    seed: int = 23
    population_size: int = 6
    ga_steps: int = 2
    elite_count: int = 2
    local_steps: int = 2
    rounds: int = 2
    ga_sigma: float = 0.12
    vns_sigma: float = 0.06
    bias_weight: float = 0.15
    evaluation_budget: int = 80
    evaluation_mode: str = "problem"
    output_dir: str | None = None
    checkpoint_every: int = 4

    def __post_init__(self):
        for key in ("population_size", "ga_steps", "elite_count", "local_steps", "rounds",
                    "evaluation_budget", "checkpoint_every"):
            if type(getattr(self, key)) is not int or getattr(self, key) < 1:
                raise ValueError(f"{key} must be a positive integer")
        if self.population_size < 2 or self.elite_count > self.population_size:
            raise ValueError("population_size >= 2 and elite_count <= population_size are required")
        if self.ga_sigma <= 0 or self.vns_sigma <= 0 or self.bias_weight < 0:
            raise ValueError("mutation scales must be positive and bias_weight nonnegative")
        if self.evaluation_mode not in {"problem", "provider"}:
            raise ValueError("evaluation_mode must be problem or provider")

    @property
    def max_steps(self):
        # 留一次空尝试报告计划完成；不会因此多记一个逻辑步骤。
        return self.rounds * (self.ga_steps + self.elite_count * self.local_steps + 1) + 1
```

## cases/hybrid_search/evaluation/__init__.py

真实文件：[cases/hybrid_search/evaluation/__init__.py](cases/hybrid_search/evaluation/__init__.py)。

SHA-256：`0ed1027d6253de49bb63673d5dd2d84fafe4db80fc661b5603d09497dfa30ed7`。

```python
from .provider import RecipeProvider

__all__ = ["RecipeProvider"]
```

## cases/hybrid_search/evaluation/provider.py

真实文件：[cases/hybrid_search/evaluation/provider.py](cases/hybrid_search/evaluation/provider.py)。

SHA-256：`2d2676edac19fe13a9aa72d3ad2441a85a39284e5b86b5ffab7c570982673f91`。

```python
"""可选的等价向量化 Provider；使用同一问题公式，不调用 Problem.evaluate。"""
import numpy as np

from ..problem import RecipeProblem, recipe_cost


class RecipeProvider:
    name = "recipe_vectorized"
    semantic_mode = "equivalent"
    priority = 50
    allow_inner = False

    def can_handle_population(self, solver, population, context):
        return isinstance(solver.problem, RecipeProblem)

    def evaluate_population(self, solver, population, context):
        values = np.asarray(population, dtype=float)
        return recipe_cost(values).reshape(-1, 1), np.maximum(
            solver.problem.evaluate_constraints(values), 0.).sum(axis=1)

    def can_handle_individual(self, solver, x, context):
        return isinstance(solver.problem, RecipeProblem)

    def evaluate_individual(self, solver, x, context, individual_id=None):
        objectives, violations = self.evaluate_population(solver, np.asarray(x).reshape(1, -1), context)
        return objectives[0], float(violations[0])
```

## cases/hybrid_search/pipeline/__init__.py

真实文件：[cases/hybrid_search/pipeline/__init__.py](cases/hybrid_search/pipeline/__init__.py)。

SHA-256：`0c86bee898260efb9080c3ea3db6d374193ff1841626a5124d322b901ae62d4d`。

```python
"""问题管线公开入口；装配在 main，Unit 构建规则保持独立。"""
from .main import RecipePipeline, build_pipeline
from .repair import RecipeRepair
__all__ = ["build_pipeline", "RecipeRepair", "RecipePipeline"]
```

## cases/hybrid_search/pipeline/main.py

真实文件：[cases/hybrid_search/pipeline/main.py](cases/hybrid_search/pipeline/main.py)。

SHA-256：`25dd913f1a9f3884cc548a7a8c3b4f2c7f20134fbb3cd651b05978abe5b1daa9`。

```python
"""问题管线的规范装配入口，显式保存本例有状态叶组件。"""
from nsgablack.representation import ContextGaussianMutation, RepresentationPipeline, UniformInitializer

from .repair import RecipeRepair


class RecipePipeline(RepresentationPipeline):
    """为本 Case 实际使用的三个有状态组件显式提供 checkpoint codec。"""
    state_recovery_level = "L1"
    state_recovery_notes = "Restores initializer/mutator RNG and repair observation counters."

    def get_state(self):
        return {"schema": "assembly_workbench.recipe_pipeline/v1",
                "initializer": self.initializer.get_state(),
                "mutator": self.mutator.get_state(), "repair": self.problem_repair.get_state()}

    def set_state(self, state):
        if (set(state) != {"schema", "initializer", "mutator", "repair"}
                or state["schema"] != "assembly_workbench.recipe_pipeline/v1"):
            raise ValueError("incompatible recipe pipeline state")
        self.initializer.set_state(state["initializer"])
        self.mutator.set_state(state["mutator"])
        self.problem_repair.set_state(state["repair"])


def build_pipeline(sigma):
    # 初始值有意覆盖边界外区域，让运行结果能验证 repair 确实工作。
    repair = RecipeRepair()
    return RecipePipeline(initializer=UniformInitializer(-0.2, 1.2),
        mutator=ContextGaussianMutation(base_sigma=sigma), repair=repair), repair
```

## cases/hybrid_search/pipeline/population.py

真实文件：[cases/hybrid_search/pipeline/population.py](cases/hybrid_search/pipeline/population.py)。

SHA-256：`393e4920f5c29eb27a8b54b105b354e3279c380e5ce6e4ca5cb729705dc91e14`。

```python
"""扩展成员年龄；Adapter 不猜测新增字段的更新规则。"""
from dataclasses import dataclass, field

import numpy as np
from nsgablack.representation import PopulationUnitBuilder
from nsgablack.units import PopulationUnit, UnitSchema


@dataclass
class RecipePopulation(PopulationUnit):
    member_age: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=int))
    member_fields = ("member_age",)
    schema = UnitSchema("assembly_workbench.recipe_population",
        required_fields=(*PopulationUnit.schema.required_fields, "member_age"),
        candidate_projection=False)

    def on_members_changed(self, change):
        increment = int(change.operation == "selection")
        return {"member_age": np.asarray([0 if index is None else self.member_age[index] + increment
            for index in change.previous_member_indices], dtype=int)}

    def validate(self):
        super().validate()
        if self.member_age.dtype.kind not in "iu" or np.any(self.member_age < 0):
            raise ValueError("member ages must be nonnegative integers")


class RecipePopulationBuilder(PopulationUnitBuilder):
    unit_type = RecipePopulation
    compatible_schemas = (PopulationUnit.schema,)
```

## cases/hybrid_search/pipeline/repair.py

真实文件：[cases/hybrid_search/pipeline/repair.py](cases/hybrid_search/pipeline/repair.py)。

SHA-256：`2d0c3b473f3780fa78a5aebf301a5896b5bde82146d680c544317dd2edf3c281`。

```python
"""只处理候选可行性；不选择成员、不求值、不访问算法 Unit。"""
from typing import ClassVar

import numpy as np
from blackbase.representation import RepresentationCapabilities
from nsgablack.representation.base import RepresentationComponentContract


class RecipeRepair(RepresentationComponentContract):
    representation_capabilities: ClassVar = RepresentationCapabilities(
        frozenset({"repair"}), repair_idempotent=True)
    state_recovery_level = "L1"
    state_recovery_notes = "Restores detached observation counters; the repair itself is deterministic."
    context_notes = "Clips box bounds and projects total recipe amount to 1.2."

    def __init__(self):
        self.calls = self.changed = 0

    def repair(self, candidate, context=None):
        before = np.asarray(candidate, dtype=float)
        result = np.clip(before, 0., 1.)
        if float(result.sum()) > 1.2:
            result *= 1.2 / float(result.sum())
        self.calls += 1
        self.changed += int(not np.array_equal(before, result))
        return result

    def validate(self, candidate, context=None):
        x = np.asarray(candidate, dtype=float)
        return bool(x.shape == (2,) and np.all(np.isfinite(x)) and np.all(x >= -1e-12)
                    and np.all(x <= 1. + 1e-12) and x.sum() <= 1.2 + 1e-12)

    def get_state(self):
        return {"schema": "assembly_workbench.recipe_repair/v1", "calls": self.calls,
                "changed": self.changed}

    def set_state(self, state):
        if (state.get("schema") != "assembly_workbench.recipe_repair/v1"
                or type(state.get("calls")) is not int or type(state.get("changed")) is not int
                or not 0 <= state["changed"] <= state["calls"]):
            raise ValueError("invalid recipe repair observation state")
        self.calls, self.changed = state["calls"], state["changed"]
```

## cases/hybrid_search/plugins/__init__.py

真实文件：[cases/hybrid_search/plugins/__init__.py](cases/hybrid_search/plugins/__init__.py)。

SHA-256：`6ed864d92dad87d2ff5762c4dd25477b05a81f90c0fd5dee5f3030bde3304bb9`。

```python
from .trace import WorkbenchTrace

__all__ = ["WorkbenchTrace"]
```

## cases/hybrid_search/plugins/trace.py

真实文件：[cases/hybrid_search/plugins/trace.py](cases/hybrid_search/plugins/trace.py)。

SHA-256：`938387c77c4b8f5b6c535d164707efb7267e5c02d2aac04c9f52eda9c4fe01aa`。

```python
"""观察实际装配与提交；最终发布前只检查一致性，不改变算法。"""
from __future__ import annotations

import json
from pathlib import Path

from blackbase.participation import ParticipationContract
from nsgablack.plugins.base import Plugin
from nsgablack.utils.engineering.file_io import atomic_write_text
from ..problem import recipe_cost


def detached(value):
    return json.loads(json.dumps(value, allow_nan=False))


class WorkbenchTrace(Plugin):
    participation = ParticipationContract(vetoes=("finalization",))
    state_recovery_level = "L1"
    state_recovery_notes = "Restores bounded JSON observations; never copies live components."
    context_notes = "Reads committed Pool/Unit/Authority and validates final publication."

    def __init__(self, output_dir, max_records):
        super().__init__(name="workbench_trace", priority=100)
        self.output_dir, self.max_records = Path(output_dir), max_records
        self.run_id, self.initial, self.final = None, None, None
        self.records, self.components = [], []

    def _tree(self):
        def visit(owner, path):
            yield path, owner
            for index, child in enumerate(owner.step_transaction_children()):
                yield from visit(child, f"{path}/{index}:{child.name}")
        return list(visit(self.solver.adapter, self.solver.adapter.name))

    def _read(self):
        solver, pool = self.solver, self.solver.solution_pool
        owners = self._tree()
        ga = next(item for _path, item in owners if item.name == "ga")
        vns_task = next(unit.adapter for unit in solver.adapter.units if unit.role == "vns")
        unit = ga.algorithm_unit  # 只观察，绝不为了日志调用 ensure_unit。
        refs = () if unit is None else tuple(ga.get_population_solution_refs(solver))
        raw_f, raw_v = pool.read_raw_feedback(refs)
        elite = pool.subpool_refs("elite") if pool.has_subpool("elite") else ()
        refined = (solver.adapter.get_pool_task_results(solver, "vns")
                   if vns_task.task_status["status"] == "done" else ())
        phases = sorted({task["phase"] for task in solver.adapter.get_runtime_context_projection(
            solver).get("unit_tasks", {}).values()})
        identity = solver.get_population_authority_identity()
        repair_component = solver.representation_pipeline.problem_repair
        return {"phase": phases, "evaluations": int(solver.evaluation_count),
            "problem_calls": int(solver.problem.evaluation_count),
            "pool_records": pool.record_count, "pool_sequence": pool.timestamp.sequence,
            "pool_initial_refs": [ref.as_dict() for ref in pool.select(stage="initial")],
            "authority_epoch": None if identity is None else identity.epoch,
            "ga_unit_exists": unit is not None,
            "member_age": [] if unit is None else unit.member_age.tolist(),
            "member_refs": [ref.as_dict() for ref in refs],
            "raw_objectives": raw_f.tolist(), "raw_violations": raw_v.tolist(),
            "selection_objectives": [] if unit is None else unit.objectives.tolist(),
            "elite_refs": [ref.as_dict() for ref in elite],
            "refinement_request": vns_task.task_status["request"],
            "refined_selected_refs": [ref.as_dict() for ref in refined],
            "repair": {"calls": repair_component.calls, "changed": repair_component.changed}}

    def on_solver_init(self, solver):
        run_id = solver.run_session.run_id
        if self.run_id != run_id:
            self.run_id, self.initial, self.final = run_id, None, None
            self.records = []
        self.components = [{"path": path, "type": f"{type(owner).__module__}.{type(owner).__name__}"}
                           for path, owner in self._tree()]
        self.components += [{"path": "plugin", "type": type(plugin).__name__}
                            for plugin in solver.plugin_manager.plugins]
        self.components += [{"path": "evaluation_provider", "type": type(provider).__name__}
                            for provider in solver.evaluation_mediator.list_providers()]
        self.components += [{"path": path, "type": type(owner).__name__} for path, owner in (
            ("problem", solver.problem), ("pipeline", solver.representation_pipeline),
            ("bias", solver.bias_module))]
        if self.initial is None:
            self.initial = self._read()

    def on_generation_committed(self, generation, outcome):
        if len(self.records) >= self.max_records:
            raise ValueError("workbench trace capacity exceeded")
        self.records.append({"generation": int(generation), **self._read()})

    def on_solver_finalization_prepare(self, result):
        solver = self.solver
        authority = solver.get_population_authority_identity()
        if authority is not None and solver.snapshot_store.read_verified(authority.snapshot).data.get(
                "solution_pool_ref") != solver.solution_pool.publication_ref():
            raise ValueError("final authority and Pool manifest disagree")
        incumbent = solver.get_incumbent()
        if incumbent is not None and not solver.problem.is_valid(incumbent.candidate):
            raise ValueError("final recipe is not feasible")
        runtime = getattr(solver, "case_runtime", None)
        if runtime is not None and runtime.artifact_publisher is not None:
            runtime.begin_finalization_transaction("case_finalization").publish("summary", {
                "case": "hybrid_search", "run_id": self.run_id, "steps": solver.run_progress_steps,
                "evaluations": solver.evaluation_count,
                "best_candidate": None if incumbent is None else incumbent.candidate.tolist(),
                "raw_objective_recomputed": None if incumbent is None else float(recipe_cost(incumbent.candidate)),
                "raw_objective_source": "analytical_recomputation_for_report",
                "selection_objectives": None if incumbent is None else incumbent.objectives.tolist(),
                "components": self.components}, serializer="json", kind="workbench-summary")

    def on_solver_finalized(self, result):
        self.final = self._read()
        self.final["checkpoint"] = next(plugin.latest_checkpoint_path
            for plugin in self.solver.plugin_manager.plugins if plugin.name == "checkpoint_resume")
        atomic_write_text(self.output_dir / "trace.json", json.dumps(self.get_state(),
                          ensure_ascii=False, indent=2, allow_nan=False))

    def get_state(self):
        return detached({"schema": "assembly_workbench.hybrid_trace/v1", "run_id": self.run_id,
            "max_records": self.max_records, "components": self.components,
            "initial": self.initial, "records": self.records, "final": self.final})

    def set_state(self, state):
        if (state.get("schema") != "assembly_workbench.hybrid_trace/v1"
                or state.get("max_records") != self.max_records or len(state["records"]) > self.max_records):
            raise ValueError("incompatible hybrid trace state")
        values = detached(state)
        self.run_id, self.initial, self.final = values["run_id"], values["initial"], values["final"]
        self.records, self.components = values["records"], values["components"]
```

## cases/hybrid_search/problem/__init__.py

真实文件：[cases/hybrid_search/problem/__init__.py](cases/hybrid_search/problem/__init__.py)。

SHA-256：`dc66ff07fe8ea46d0f28ebe575702b75a206029009a900afd4869a17a0b42b9d`。

```python
from .recipe import RecipeProblem, recipe_cost

__all__ = ["RecipeProblem", "recipe_cost"]
```

## cases/hybrid_search/problem/recipe.py

真实文件：[cases/hybrid_search/problem/recipe.py](cases/hybrid_search/problem/recipe.py)。

SHA-256：`20a16baa1d0b4ae9ea735f5119a946bcf118f529bf461d1a0b6aea3677197191`。

```python
"""两种原料的投料比例；容量是硬约束，均衡偏好另交 Bias。"""
import numpy as np

from nsgablack.core import BlackBoxProblem


def recipe_cost(candidate):
    x = np.asarray(candidate, dtype=float)
    return (x[..., 0] - 0.85) ** 2 + 1.6 * (x[..., 1] - 0.65) ** 2 + 0.03 * x.sum(axis=-1)


class RecipeProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="双原料配方", dimension=2, objectives=["minimize"],
                         bounds=[(0., 1.), (0., 1.)])

    def evaluate(self, candidate):
        return [float(recipe_cost(candidate))]

    def evaluate_constraints(self, candidate):
        x = np.asarray(candidate, dtype=float)
        return np.stack((-x[..., 0], -x[..., 1], x[..., 0] - 1., x[..., 1] - 1.,
                         x.sum(axis=-1) - 1.2), axis=-1)
```

## cases/hybrid_search/run_solver.py

真实文件：[cases/hybrid_search/run_solver.py](cases/hybrid_search/run_solver.py)。

SHA-256：`4f21b83eb9fa539f83721443134b8ed18689687d686de99aeed3b574b2584db3`。

```python
"""正式标准 Case CLI，支持 --check / --build-check。"""
from blackbase.project import run_standard_case_cli


def main(argv=None):
    return run_standard_case_cli(__file__, framework="nsgablack", argv=argv)


if __name__ == "__main__":
    raise SystemExit(main())
```

## cases/hybrid_search/run_trainer.py

真实文件：[cases/hybrid_search/run_trainer.py](cases/hybrid_search/run_trainer.py)。

SHA-256：`70310dae533a94919ec3b2c56d9abed07aee029439318856271e3d4897bb47ee`。

```python
from .run_solver import main


if __name__ == "__main__":
    raise SystemExit(main())
```

## cases/hybrid_search/runtime/__init__.py

真实文件：[cases/hybrid_search/runtime/__init__.py](cases/hybrid_search/runtime/__init__.py)。

SHA-256：`4aa588e298d01871d23acc6d1a74d8abc331369f7cd148681545785e879c32ff`。

```python
"""本 Case 消费 Project 的 ResourceContext，不私自分配全局资源。"""
```

## cases/hybrid_search/solver/__init__.py

真实文件：[cases/hybrid_search/solver/__init__.py](cases/hybrid_search/solver/__init__.py)。

SHA-256：`bb76955f2e2cd8a7b509ac23e2f2c9bec7cdd6ec4ef316e0f5fed23717ca69f2`。

```python
"""使用框架 ComposableSolver，不派生私有控制面。"""
```

## cases/inner_response/.case

真实文件：[cases/inner_response/.case](cases/inner_response/.case)。

SHA-256：`8cdfb3878b786e5d4fba99eb5ba3cb8266e1f75d971e188c96d2c4248ecf77ac`。

```text
name = inner_response
kind = solver
framework = nsgablack
```

## cases/inner_response/__init__.py

真实文件：[cases/inner_response/__init__.py](cases/inner_response/__init__.py)。

SHA-256：`c9cd0f94b05b0324d9efadc891fd84e84f2fe8c2f79d92a2d86b9fe38d5af8f9`。

```python
"""inner_response standard Case."""
```

## cases/inner_response/adapter/__init__.py

真实文件：[cases/inner_response/adapter/__init__.py](cases/inner_response/adapter/__init__.py)。

SHA-256：`7ca1679ba7673fe878c244b44d5c1f69c567d4c3aecba65916403055844e943f`。

```python
from nsgablack.adapters import VNSAdapter

def build_adapter():
    return VNSAdapter(name="response_vns", batch_size=1, restart_on_stagnation=False)
```

## cases/inner_response/bias/__init__.py

真实文件：[cases/inner_response/bias/__init__.py](cases/inner_response/bias/__init__.py)。

SHA-256：`76f9b0d60c2899c996187e5a026790f1fd0b877684920c1d6c03992675318125`。

```python
"""本例无需额外bias组件；使用框架标准契约。"""
```

## cases/inner_response/build_solver.py

真实文件：[cases/inner_response/build_solver.py](cases/inner_response/build_solver.py)。

SHA-256：`e0d87e26ae8a4afc8e171fcbc50c2cc6f7ccf4a864e1334e6f6cba52bcd69537`。

```python
"""唯一装配入口；接受父 Project 派生的资源授权。"""
from pathlib import Path
from nsgablack.core import ComposableSolver
from nsgablack.project import apply_solver_component_overrides
from .config import DemoConfig
from .problem import ResponseProblem
from .pipeline import build_pipeline
from .adapter import build_adapter
from .plugins import ResponseTracePlugin
from .solver import ResponseCase

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    overrides = dict(component_overrides or {})
    settings = DemoConfig(**{**dict(config or {}), **dict(overrides.pop("config", {}))})
    payload = overrides.pop("inner_task_payload", None)
    output_dir = Path(overrides.pop("output_dir",
        Path(__file__).resolve().parents[2] / "results" / "inner_response"))
    solver = ComposableSolver(ResponseProblem(), adapter=build_adapter(),
        representation_pipeline=build_pipeline(), resource_context=resource_context,
        plugin_strict=True, snapshot_strict=True)
    solver.set_random_seed(settings.seed)
    solver.set_max_steps(settings.steps)
    solver.add_plugin(ResponseTracePlugin(output_dir))
    apply_solver_component_overrides(solver, overrides)
    return ResponseCase(solver, settings, output_dir, payload=payload)
```

## cases/inner_response/build_trainer.py

真实文件：[cases/inner_response/build_trainer.py](cases/inner_response/build_trainer.py)。

SHA-256：`99f765e75df055fdefa2b0a2bbdc035a77c5669466fcb9bbd15da6e21a2b468f`。

```python
from .build_solver import build_solver as build_trainer
```

## cases/inner_response/catalog/entries/pipeline.toml

真实文件：[cases/inner_response/catalog/entries/pipeline.toml](cases/inner_response/catalog/entries/pipeline.toml)。

SHA-256：`5f95774976e5df3e3efd7531c54d5345b06b0f6cd493b25e3f5b1f442aae3ae3`。

```toml
[[entry]]
key = "project.pipeline.response_operators"
title = "ResponseOperators"
kind = "representation"
import_path = "pipeline.operators:ResponseOperators"
tags = ["project", "pipeline", "init", "mutate"]
summary = "根据当前条件生成基准并向目标移动，不内嵌 repair 或求值。"
context_requires = ["vns_k"]
context_provides = []
context_mutates = []
context_cache = []
context_notes = ["条件标量由 Case 显式绑定；邻域参数 vns_k 是 Adapter 的调用局部输入。"]
use_when = ["手算两步响应以验证真实后继反馈。"]
minimal_wiring = ["from cases.inner_response.pipeline.operators import ResponseOperators", "operator = ResponseOperators()"]
required_companions = ["nsgablack.representation:RepresentationPipeline"]
config_keys = []
example_entry = "cases.inner_response.build_solver:build_solver"
```

## cases/inner_response/catalog/entries/plugin.toml

真实文件：[cases/inner_response/catalog/entries/plugin.toml](cases/inner_response/catalog/entries/plugin.toml)。

SHA-256：`cd53dc15634271b439a3efd9e19203fa951023348468e1af3d186c56a39320e0`。

```toml
[[entry]]
key = "project.plugin.inner_response_trace"
title = "ResponseTracePlugin"
kind = "plugin"
import_path = "plugins.trace:ResponseTracePlugin"
tags = ["project", "plugin", "observe", "nested"]
summary = "只读记录已提交逻辑步骤；不触发额外求值或改变候选。"
context_requires = []
context_provides = []
context_mutates = []
context_cache = []
context_notes = ["本地文件是观察副本；权威 Artifact 由 Case 发布事务提供。"]
use_when = ["查看外层与内层实际提交计数。"]
minimal_wiring = ["from cases.inner_response.plugins import ResponseTracePlugin", "solver.add_plugin(ResponseTracePlugin('results'))"]
required_companions = ["nsgablack.core:ComposableSolver"]
config_keys = ["output_dir"]
example_entry = "cases.inner_response.build_solver:build_solver"
```

## cases/inner_response/catalog/entries/problem.toml

真实文件：[cases/inner_response/catalog/entries/problem.toml](cases/inner_response/catalog/entries/problem.toml)。

SHA-256：`b8b525a6a392b875d25420e08c927d30098a54507d2f456a6da66247840aa95b`。

```toml
[[entry]]
key = "project.problem.inner_response"
title = "ResponseProblem"
kind = "tool"
import_path = "problem.response:ResponseProblem"
tags = ["project", "problem", "nested"]
summary = "标准嵌套示例的问题语义；候选与反馈通过正式 Case 边界交换。"
context_requires = []
context_provides = []
context_mutates = []
context_cache = []
context_notes = ["不读写共享 context，不把不同 Case 的 Pool 合并。"]
use_when = ["核对条件问题与嵌套结果的语义边界。"]
minimal_wiring = ["from cases.inner_response.problem import ResponseProblem", "problem = ResponseProblem()"]
required_companions = []
config_keys = []
example_entry = "cases.inner_response.build_solver:build_solver"
```

## cases/inner_response/config.py

真实文件：[cases/inner_response/config.py](cases/inner_response/config.py)。

SHA-256：`c5a9792dcbe9e863bf48780c8aae397113e9a20abbb038238c8770aa506acb24`。

```python
"""内层运行规模；问题条件只通过 inner_task_payload 交付。"""
from dataclasses import dataclass

@dataclass(frozen=True)
class DemoConfig:
    seed: int = 41
    steps: int = 2

    def __post_init__(self):
        if type(self.steps) is not int or self.steps < 1:
            raise ValueError("steps must be a positive integer")
```

## cases/inner_response/evaluation/__init__.py

真实文件：[cases/inner_response/evaluation/__init__.py](cases/inner_response/evaluation/__init__.py)。

SHA-256：`151306c69abcf3e96b11730931d9ee52d0c6cb2a2c1e38eb0ae0b69e8d7ff84e`。

```python
"""本例无需额外evaluation组件；使用框架标准契约。"""
```

## cases/inner_response/pipeline/__init__.py

真实文件：[cases/inner_response/pipeline/__init__.py](cases/inner_response/pipeline/__init__.py)。

SHA-256：`b7fb51f3c2989875ac0734a66f59ed8ced326eb62d427fc0d2f96567fe95ae98`。

```python
from .main import build_pipeline
```

## cases/inner_response/pipeline/main.py

真实文件：[cases/inner_response/pipeline/main.py](cases/inner_response/pipeline/main.py)。

SHA-256：`4ec20fa50c3b75a034bf9ac7c1526bcf31ce706e5451f3d6de92803749920101`。

```python
"""唯一问题管线入口；初始化、变化和可行性修复保持分离。"""
from nsgablack.representation import ClipRepair, RepresentationPipeline
from .operators import ResponseOperators

def build_pipeline():
    operator = ResponseOperators()
    return RepresentationPipeline(initializer=operator, mutator=operator,
                                  repair=ClipRepair(low=-3., high=3.))
```

## cases/inner_response/pipeline/operators.py

真实文件：[cases/inner_response/pipeline/operators.py](cases/inner_response/pipeline/operators.py)。

SHA-256：`e0849a7088aa0a66ccf81d0148ca06eb8aaabcd6d1a950485f0ff43811f97d62`。

```python
"""确定性条件初始化与向 target 靠近；问题边界仍由统一 repair 处理。"""
import numpy as np
from blackbase.representation import RepresentationCapabilities
from nsgablack.representation.base import RepresentationComponentContract
from nsgablack.context_keys import KEY_VNS_K

class ResponseOperators(RepresentationComponentContract):
    representation_capabilities = RepresentationCapabilities(frozenset({"init", "mutate"}))
    context_requires = (KEY_VNS_K,)
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Uses an explicitly bound scalar condition; never writes context."

    def __init__(self, target=.5):
        self.target = float(target)

    def set_target(self, target):
        self.target = float(target)

    def initialize(self, problem, context=None):
        return np.array([self.target + .5])

    def mutate(self, candidate, context=None):
        scale = 1. / (2. + int(context[KEY_VNS_K]))
        return self.target + scale * (np.asarray(candidate, dtype=float) - self.target)
```

## cases/inner_response/plugins/__init__.py

真实文件：[cases/inner_response/plugins/__init__.py](cases/inner_response/plugins/__init__.py)。

SHA-256：`78b996842640725f42eef629ca7f09a23a768f1a1e42c0d40ca0c4ce6dd8ea10`。

```python
from .trace import ResponseTracePlugin
```

## cases/inner_response/plugins/trace.py

真实文件：[cases/inner_response/plugins/trace.py](cases/inner_response/plugins/trace.py)。

SHA-256：`a8c3e60974af68727539a9afe62d8fc81b1ce683a10845e82db211bba6c9d788`。

```python
"""只记录已提交逻辑步；不改变算法或调用额外求值。"""
import json
from pathlib import Path
from blackbase.participation import ParticipationContract
from nsgablack.plugins.base import Plugin
from nsgablack.utils.engineering.file_io import atomic_write_text

class ResponseTracePlugin(Plugin):
    participation = ParticipationContract()
    state_recovery_level = "L1"
    state_recovery_notes = "Explicit bounded scalar observation state."
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Reads committed counters and writes only a local observation file."

    def __init__(self, output_dir):
        super().__init__(name="response_trace")
        self.output_dir = Path(output_dir)
        self.records = []
        self.run_id = None

    def on_solver_init(self, solver):
        self.solver = solver
        run_id = str(self.solver.run_session.run_id)
        if self.run_id != run_id:
            self.records = []
        self.run_id = run_id

    def on_generation_committed(self, generation, outcome):
        self.records.append({"generation": int(generation),
            "evaluations": int(self.solver.evaluation_count),
            "best_objective": float(self.solver.best_objective)})

    def on_solver_finalized(self, result):
        atomic_write_text(self.output_dir / "trace.json",
            json.dumps(self.get_state(), ensure_ascii=False, indent=2, allow_nan=False))

    def get_state(self):
        return {"schema": "assembly_workbench.response_trace/v1",
                "run_id": self.run_id, "records": [dict(row) for row in self.records]}

    def set_state(self, state):
        if state.get("schema") != "assembly_workbench.response_trace/v1":
            raise ValueError("invalid response trace state")
        self.run_id = state["run_id"]
        self.records = [dict(row) for row in state["records"]]
```

## cases/inner_response/problem/__init__.py

真实文件：[cases/inner_response/problem/__init__.py](cases/inner_response/problem/__init__.py)。

SHA-256：`9b2f088415f81d630db7b069cbb2877422e74435994ca6389f22ed4b32f98cc1`。

```python
from .response import ResponseProblem
```

## cases/inner_response/problem/response.py

真实文件：[cases/inner_response/problem/response.py](cases/inner_response/problem/response.py)。

SHA-256：`db8cbfb692eb0875dc8f40104084f2c29f0add9db5ea0aaa47e99bc9434ffd03`。

```python
"""在给定外部条件 target 下搜索响应 y；不是外层 x 的替身。"""
import numpy as np
from nsgablack.core import BlackBoxProblem

class ResponseProblem(BlackBoxProblem):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()

    def __init__(self, target=.5):
        super().__init__(name="conditional_response", dimension=1,
                         objectives=["min"], bounds=[(-3., 3.)])
        self.set_target(target)

    def set_target(self, target):
        target = float(target)
        if not np.isfinite(target) or not -2. <= target <= 2.:
            raise ValueError("response target must be finite and within [-2, 2]")
        self.target = target

    def evaluate(self, candidate):
        y = float(np.asarray(candidate).reshape(-1)[0])
        return [(y - self.target) ** 2]
```

## cases/inner_response/run_solver.py

真实文件：[cases/inner_response/run_solver.py](cases/inner_response/run_solver.py)。

SHA-256：`8c3367467d52c3df5fa0df0269fe6ec82755ce763678cde20215775a5f384f9b`。

```python
"""内层可直接运行；标准 CLI --check 不执行搜索。"""
from blackbase.project import run_standard_case_cli

def main(argv=None):
    return run_standard_case_cli(__file__, framework="nsgablack", argv=argv)

if __name__ == "__main__":
    raise SystemExit(main())
```

## cases/inner_response/run_trainer.py

真实文件：[cases/inner_response/run_trainer.py](cases/inner_response/run_trainer.py)。

SHA-256：`baa1ed97eb52ac800e55abd523a65bf3345d0f0792bcd088d1d04e35eab52fdb`。

```python
from .run_solver import main

if __name__ == "__main__":
    raise SystemExit(main())
```

## cases/inner_response/runtime/__init__.py

真实文件：[cases/inner_response/runtime/__init__.py](cases/inner_response/runtime/__init__.py)。

SHA-256：`971227f75b907cf609a813ca79cb6599899a6136f10dedbf103050213779b26c`。

```python
"""本例无需额外runtime组件；使用框架标准契约。"""
```

## cases/inner_response/solver/__init__.py

真实文件：[cases/inner_response/solver/__init__.py](cases/inner_response/solver/__init__.py)。

SHA-256：`9f6b75d10834713beec50851cb1daa9655429c4dc6278175ad20708876322599`。

```python
from .case import ResponseCase
```

## cases/inner_response/solver/case.py

真实文件：[cases/inner_response/solver/case.py](cases/inner_response/solver/case.py)。

SHA-256：`ad8aeb6efcfbddba92a7b5066933b1cc90cd703c08f8f4ddddd2d1c12a8db201`。

```python
"""标准 Case 输入与结果边界；不拥有另一个资源调度器。"""
import json
from dataclasses import replace
from pathlib import Path
from blackbase.project.case_execution import make_transport_safe
from nsgablack.utils.engineering.file_io import atomic_write_text

class ResponseCase:
    def __init__(self, solver, settings, output_dir, *, payload=None):
        self.solver, self.settings = solver, settings
        self.problem, self.adapter = solver.problem, solver.adapter
        self.pipeline = self.representation_pipeline = solver.representation_pipeline
        self.plugin_manager = solver.plugin_manager
        self.evaluation_mediator = solver.evaluation_mediator
        self.resource_context = solver.resource_context
        self.output_dir = Path(output_dir)
        self.case_runtime = None
        self.task_payload = {"target": .5, "source": "builtin"}
        if payload is not None:
            self.set_case_inputs({"inner_task_payload": payload})

    @property
    def resource_binding_audit(self):
        return getattr(self.solver, "resource_binding_audit", {})

    @resource_binding_audit.setter
    def resource_binding_audit(self, value):
        self.solver.resource_binding_audit = value

    def set_resource_context(self, value):
        self.solver.set_resource_context(value)
        self.resource_context = self.solver.resource_context
        return self

    def get_resource_context(self):
        return self.solver.get_resource_context()

    def set_case_runtime(self, runtime):
        self.case_runtime = runtime
        self.solver.set_case_runtime(runtime)
        return self

    def set_case_inputs(self, inputs):
        if set(inputs) != {"inner_task_payload"}:
            raise ValueError("inner_response requires inputs.inner_task_payload")
        payload = dict(inputs["inner_task_payload"])
        if "target" not in payload:
            raise ValueError("inner_task_payload requires target")
        self.problem.set_target(payload["target"])
        self.pipeline.mutator.set_target(self.problem.target)
        self.task_payload = payload

    def run(self):
        return self.solver.run(max_steps=self.settings.steps,
                               max_step_attempts=self.settings.steps + 2)

    def export_case_result(self, raw_output):
        result = self.solver.export_case_result(raw_output)
        state = result.best_solution
        values = state.values if hasattr(state, "values") else state
        summary = make_transport_safe({"schema": "assembly_workbench.inner_response/v1",
            "case": "inner_response", "target": self.problem.target,
            "best_response": float(values[0]),
            "best_objectives": result.best_objectives.tolist(),
            "committed_steps": int(self.solver.generation),
            "evaluation_count": int(self.solver.evaluation_count),
            "pool_id": self.solver.solution_pool.pool_id,
            "task_payload": self.task_payload,
            "identity": None if self.case_runtime is None else self.case_runtime.identity.as_dict(),
            "resource_grant": dict(self.resource_context.grant),
            "resource_binding_current": bool(dict(self.resource_binding_audit or {}).get("current", False)),
            "artifact_source": "standalone" if self.case_runtime is None else "project_authority"},
            path="inner_response.summary")
        refs = dict(result.artifact_refs)
        if self.case_runtime is not None:
            # Solver lifecycle has ended; the enclosing CaseExecutor still
            # owns its final result serialization and authority seal.
            refs["summary"] = self.case_runtime.publish_artifact("summary", summary, serializer="json",
                kind="conditional-response", metadata={"schema": summary["schema"]})
        atomic_write_text(self.output_dir / "summary.json",
            json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False))
        return replace(result, artifact_refs=refs, metadata={**dict(result.metadata), "summary": summary})
```

## cases/outer_nested/.case

真实文件：[cases/outer_nested/.case](cases/outer_nested/.case)。

SHA-256：`dc8130b02ee8867767ba974e7dae9c92061e4967f4c0752ff40d033df3f69ae0`。

```text
name = outer_nested
kind = solver
framework = nsgablack
```

## cases/outer_nested/__init__.py

真实文件：[cases/outer_nested/__init__.py](cases/outer_nested/__init__.py)。

SHA-256：`5719c034f2f786db03d02c736691046ef6fd008253dc6aa5ed093e1885edd2a5`。

```python
"""outer_nested standard Case."""
```

## cases/outer_nested/adapter/__init__.py

真实文件：[cases/outer_nested/adapter/__init__.py](cases/outer_nested/adapter/__init__.py)。

SHA-256：`a6b1c585770fc5e71cb71f85d3f4c55711b9969ae0bf4a585e165490533d556c`。

```python
from nsgablack.adapters import NSGA2Adapter

def build_adapter():
    return NSGA2Adapter(name="outer_ga", population_size=2, offspring_size=2)
```

## cases/outer_nested/bias/__init__.py

真实文件：[cases/outer_nested/bias/__init__.py](cases/outer_nested/bias/__init__.py)。

SHA-256：`76f9b0d60c2899c996187e5a026790f1fd0b877684920c1d6c03992675318125`。

```python
"""本例无需额外bias组件；使用框架标准契约。"""
```

## cases/outer_nested/build_solver.py

真实文件：[cases/outer_nested/build_solver.py](cases/outer_nested/build_solver.py)。

SHA-256：`3dc08324da51ae24efb06c835c7e1a7829034dbf25abacf56f6c91487b14d56a`。

```python
"""外层唯一装配入口；不把内层求解器变成 Adapter 叶算子。"""
from pathlib import Path
from nsgablack.core import ComposableSolver
from nsgablack.project import apply_solver_component_overrides
from .config import DemoConfig
from .problem import NestedResponseProblem
from .pipeline import build_pipeline
from .adapter import build_adapter
from .plugins import NestedTracePlugin
from .solver import NestedCase

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    overrides = dict(component_overrides or {})
    settings = DemoConfig(**{**dict(config or {}), **dict(overrides.pop("config", {}))})
    output_dir = Path(overrides.pop("output_dir",
        Path(__file__).resolve().parents[2] / "results" / "outer_nested"))
    solver = ComposableSolver(NestedResponseProblem(inner_steps=settings.inner_steps, output_dir=output_dir),
        adapter=build_adapter(), representation_pipeline=build_pipeline(),
        resource_context=resource_context, plugin_strict=True, snapshot_strict=True)
    solver.set_random_seed(settings.seed)
    solver.set_max_steps(settings.steps)
    solver.add_plugin(NestedTracePlugin(output_dir))
    apply_solver_component_overrides(solver, overrides)
    return NestedCase(solver, settings, output_dir)
```

## cases/outer_nested/build_trainer.py

真实文件：[cases/outer_nested/build_trainer.py](cases/outer_nested/build_trainer.py)。

SHA-256：`99f765e75df055fdefa2b0a2bbdc035a77c5669466fcb9bbd15da6e21a2b468f`。

```python
from .build_solver import build_solver as build_trainer
```

## cases/outer_nested/catalog/entries/plugin.toml

真实文件：[cases/outer_nested/catalog/entries/plugin.toml](cases/outer_nested/catalog/entries/plugin.toml)。

SHA-256：`2d1eb205217b3e689da37fe48e752db6dd5ded96d897c1aae9ef6e8e029fd3ba`。

```toml
[[entry]]
key = "project.plugin.outer_nested_trace"
title = "NestedTracePlugin"
kind = "plugin"
import_path = "plugins.trace:NestedTracePlugin"
tags = ["project", "plugin", "observe", "nested"]
summary = "只读记录已提交逻辑步骤；不触发额外求值或改变候选。"
context_requires = []
context_provides = []
context_mutates = []
context_cache = []
context_notes = ["本地文件是观察副本；权威 Artifact 由 Case 发布事务提供。"]
use_when = ["查看外层与内层实际提交计数。"]
minimal_wiring = ["from cases.outer_nested.plugins import NestedTracePlugin", "solver.add_plugin(NestedTracePlugin('results'))"]
required_companions = ["nsgablack.core:ComposableSolver"]
config_keys = ["output_dir"]
example_entry = "cases.outer_nested.build_solver:build_solver"
```

## cases/outer_nested/catalog/entries/problem.toml

真实文件：[cases/outer_nested/catalog/entries/problem.toml](cases/outer_nested/catalog/entries/problem.toml)。

SHA-256：`9d5cc74b764f49a302c932048f1d196fe5418d8729e56fca82f9bf8d59b71824`。

```toml
[[entry]]
key = "project.problem.outer_nested"
title = "NestedResponseProblem"
kind = "tool"
import_path = "problem.nested:NestedResponseProblem"
tags = ["project", "problem", "nested"]
summary = "标准嵌套示例的问题语义；候选与反馈通过正式 Case 边界交换。"
context_requires = []
context_provides = []
context_mutates = []
context_cache = []
context_notes = ["不读写共享 context，不把不同 Case 的 Pool 合并。"]
use_when = ["核对条件问题与嵌套结果的语义边界。"]
minimal_wiring = ["from cases.outer_nested.problem import NestedResponseProblem", "problem = NestedResponseProblem()"]
required_companions = []
config_keys = []
example_entry = "cases.outer_nested.build_solver:build_solver"
```

## cases/outer_nested/config.py

真实文件：[cases/outer_nested/config.py](cases/outer_nested/config.py)。

SHA-256：`01d75f23b11da4c5bdb851d8f1d10d3681d41d8a010372e2d4d7811b7cc38c4b`。

```python
"""外层规模与超时；内层条件通过正式调用 payload 交付。"""
from dataclasses import dataclass

@dataclass(frozen=True)
class DemoConfig:
    seed: int = 43
    steps: int = 2
    inner_steps: int = 2

    def __post_init__(self):
        if any(type(value) is not int or value < 1 for value in (self.steps, self.inner_steps)):
            raise ValueError("steps and inner_steps must be positive integers")
```

## cases/outer_nested/evaluation/__init__.py

真实文件：[cases/outer_nested/evaluation/__init__.py](cases/outer_nested/evaluation/__init__.py)。

SHA-256：`151306c69abcf3e96b11730931d9ee52d0c6cb2a2c1e38eb0ae0b69e8d7ff84e`。

```python
"""本例无需额外evaluation组件；使用框架标准契约。"""
```

## cases/outer_nested/pipeline/__init__.py

真实文件：[cases/outer_nested/pipeline/__init__.py](cases/outer_nested/pipeline/__init__.py)。

SHA-256：`b7fb51f3c2989875ac0734a66f59ed8ced326eb62d427fc0d2f96567fe95ae98`。

```python
from .main import build_pipeline
```

## cases/outer_nested/pipeline/main.py

真实文件：[cases/outer_nested/pipeline/main.py](cases/outer_nested/pipeline/main.py)。

SHA-256：`4b919936bbcf7b1360e26078040d57ddc3f3529c8c32a639bd4ae004a47000a6`。

```python
"""多个外层提案共用候选处理管线，内层条件不写入共享 context。"""
from nsgablack.representation import RepresentationPipeline, UniformInitializer, GaussianMutation, ClipRepair

def build_pipeline():
    return RepresentationPipeline(initializer=UniformInitializer(low=-1., high=1.),
        mutator=GaussianMutation(sigma=.15, low=-2., high=2.),
        repair=ClipRepair(low=-2., high=2.))
```

## cases/outer_nested/plugins/__init__.py

真实文件：[cases/outer_nested/plugins/__init__.py](cases/outer_nested/plugins/__init__.py)。

SHA-256：`85c7e388b78fdf5ca72034d70c2ae7edf73e947ed7ac6305caffcfc2235cd9f5`。

```python
from .trace import NestedTracePlugin
```

## cases/outer_nested/plugins/trace.py

真实文件：[cases/outer_nested/plugins/trace.py](cases/outer_nested/plugins/trace.py)。

SHA-256：`ad513d02efe23e1481c70622ba0ec2adb2acbb7568c3834a8a9b17d78346445b`。

```python
"""只读统计已提交步骤的内层调用数；真实成本不随外层失败回滚。"""
import json
from pathlib import Path
from blackbase.participation import ParticipationContract
from nsgablack.plugins.base import Plugin
from nsgablack.utils.engineering.file_io import atomic_write_text

class NestedTracePlugin(Plugin):
    participation = ParticipationContract()
    state_recovery_level = "L1"
    state_recovery_notes = "Explicit bounded scalar observations."
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Reads committed counters and child-call receipts; no context writes."

    def __init__(self, output_dir):
        super().__init__(name="nested_trace")
        self.output_dir = Path(output_dir)
        self.records, self.run_id = [], None

    def on_solver_init(self, solver):
        self.solver = solver
        run_id = str(self.solver.run_session.run_id)
        if self.run_id != run_id:
            self.records = []
        self.run_id = run_id

    def on_generation_committed(self, generation, outcome):
        self.records.append({"generation": int(generation),
            "outer_evaluations": int(self.solver.evaluation_count),
            "inner_calls": len(self.solver.problem.calls)})

    def on_solver_finalized(self, result):
        atomic_write_text(self.output_dir / "trace.json",
            json.dumps(self.get_state(), ensure_ascii=False, indent=2, allow_nan=False))

    def get_state(self):
        return {"schema": "assembly_workbench.nested_trace/v1", "run_id": self.run_id,
                "records": [dict(row) for row in self.records]}

    def set_state(self, state):
        if state.get("schema") != "assembly_workbench.nested_trace/v1":
            raise ValueError("invalid nested trace state")
        self.run_id = state["run_id"]
        self.records = [dict(row) for row in state["records"]]
```

## cases/outer_nested/problem/__init__.py

真实文件：[cases/outer_nested/problem/__init__.py](cases/outer_nested/problem/__init__.py)。

SHA-256：`788db5b409d1b1145718ceeea757be90a64bc4bddc92bc4a8fc8f83d3be792bc`。

```python
from .nested import NestedResponseProblem
```

## cases/outer_nested/problem/nested.py

真实文件：[cases/outer_nested/problem/nested.py](cases/outer_nested/problem/nested.py)。

SHA-256：`1d16e262565622b0719ca02288c6d17da2669c0cf9c437229fa44b3d133c6a18`。

```python
"""x 的评分委托完整的内层 Case；返回 y 不冒充外层候选 x。"""
from pathlib import Path
import numpy as np
from blackbase.project import CaseRunRequest, ExecutionControl
from blackbase.types import SolverResult
from nsgablack.core import BlackBoxProblem

class NestedResponseProblem(BlackBoxProblem):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()

    def __init__(self, *, inner_steps=2, output_dir=None):
        super().__init__(name="nested_response_design", dimension=1,
                         objectives=["min"], bounds=[(-2., 2.)])
        self.inner_steps, self.output_dir = int(inner_steps), output_dir
        self.case_runtime = None
        self.calls = []

    def set_case_runtime(self, runtime):
        self.case_runtime = runtime

    def evaluate(self, candidate):
        if self.case_runtime is None:
            raise RuntimeError("nested search requires the standard Project Case runtime")
        x = float(np.asarray(candidate).reshape(-1)[0])
        runtime = self.case_runtime
        sequence = len(self.calls)
        output = Path(self.output_dir) / "inner_calls" / f"call_{sequence:03d}"
        request = CaseRunRequest(project_name=runtime.request.project_name,
            stage_name="response_evaluation", case_name="inner_response", case_kind="solver",
            control=ExecutionControl.with_timeout(20.),
            resource_request={"threads": 1, "workers": 1, "gpus": 0, "backend": "local"},
            budget_request={"evaluations": self.inner_steps},
            component_overrides={"config": {"steps": self.inner_steps}, "output_dir": str(output)},
            inputs={"inner_task_payload": {"target": x, "outer_candidate": [x],
                    "source": "outer_nested", "sequence": sequence}},
            metadata={"edge": "outer_nested->inner_response"})
        child = runtime.invoke(request)
        child.raise_for_failure("conditional response Case failed")
        result = SolverResult.from_dict(child.output)
        state = result.best_solution
        values = state.values if hasattr(state, "values") else state
        y = float(values[0])
        inner_loss = float(np.asarray(result.best_objectives).reshape(-1)[0])
        objective = inner_loss + .05 * x ** 2
        receipt = child.artifact_publications["summary"]
        self.calls.append({"outer_candidate": [x], "best_response": y,
            "inner_loss": inner_loss, "outer_objective": objective,
            "parent_identity": runtime.identity.as_dict(), "identity": child.identity.as_dict(),
            "resource_grant": dict(child.request.resource_context.get("grant", {})),
            "parent_resource_grant": dict(runtime.resource_context.grant),
            "resource_binding_current": bool(dict(child.resource_usage.get("binding", {})).get("current", False)),
            "child_grant": child.request.child_grant.as_dict(),
            "budget_usage": dict(child.budget_usage),
            "control": child.control.as_dict(), "status": child.status,
            "started_at": child.started_at, "finished_at": child.finished_at,
            "inner_summary": dict(result.metadata["summary"]),
            "artifact_ref": child.artifact_refs["summary"].as_dict(),
            "artifact_publication": receipt.as_dict()})
        return [objective]
```

## cases/outer_nested/run_solver.py

真实文件：[cases/outer_nested/run_solver.py](cases/outer_nested/run_solver.py)。

SHA-256：`99bd0dbec62b2eae0c98e6cb051b7b2c6e807e0eec3d60a38d56fc09fe8e4fdd`。

```python
"""独立执行也委托正式 Project L0，不自行构造授权。"""
import sys
from pathlib import Path
from blackbase.project import run_standard_case_cli

def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if "--check" in args:
        return run_standard_case_cli(__file__, framework="nsgablack", argv=args)
    from nsgablack.project.project_runner import main as project_main
    return project_main(project_root=Path(__file__).resolve().parents[2],
                        argv=["--group", "nested", *args])

if __name__ == "__main__":
    raise SystemExit(main())
```

## cases/outer_nested/run_trainer.py

真实文件：[cases/outer_nested/run_trainer.py](cases/outer_nested/run_trainer.py)。

SHA-256：`baa1ed97eb52ac800e55abd523a65bf3345d0f0792bcd088d1d04e35eab52fdb`。

```python
from .run_solver import main

if __name__ == "__main__":
    raise SystemExit(main())
```

## cases/outer_nested/runtime/__init__.py

真实文件：[cases/outer_nested/runtime/__init__.py](cases/outer_nested/runtime/__init__.py)。

SHA-256：`971227f75b907cf609a813ca79cb6599899a6136f10dedbf103050213779b26c`。

```python
"""本例无需额外runtime组件；使用框架标准契约。"""
```

## cases/outer_nested/solver/__init__.py

真实文件：[cases/outer_nested/solver/__init__.py](cases/outer_nested/solver/__init__.py)。

SHA-256：`f328b268fb85e0fb5801be98a1e590fa401d0f018fc20fb0dc30763882f8e064`。

```python
from .case import NestedCase
```

## cases/outer_nested/solver/case.py

真实文件：[cases/outer_nested/solver/case.py](cases/outer_nested/solver/case.py)。

SHA-256：`e0627910bdb4d57e60bd80700c5b5101878aa8fd09a135509ed540b775c1f11b`。

```python
"""权威 Artifact 输入、标准嵌套运行和最终结果发布。"""
import json
from dataclasses import replace
from pathlib import Path
from blackbase.project.case_execution import make_transport_safe
from blackbase.resources import ArtifactPublisher
from nsgablack.utils.engineering.file_io import atomic_write_text

class NestedCase:
    def __init__(self, solver, settings, output_dir):
        self.solver, self.settings = solver, settings
        self.problem, self.adapter = solver.problem, solver.adapter
        self.pipeline = self.representation_pipeline = solver.representation_pipeline
        self.plugin_manager = solver.plugin_manager
        self.evaluation_mediator = solver.evaluation_mediator
        self.resource_context = solver.resource_context
        self.output_dir = Path(output_dir)
        self.case_runtime = None
        self.input_artifacts = {}
        self.baselines = {}

    @property
    def resource_binding_audit(self):
        return getattr(self.solver, "resource_binding_audit", {})

    @resource_binding_audit.setter
    def resource_binding_audit(self, value):
        self.solver.resource_binding_audit = value

    def set_resource_context(self, value):
        self.solver.set_resource_context(value)
        self.resource_context = self.solver.resource_context
        return self

    def get_resource_context(self):
        return self.solver.get_resource_context()

    def set_case_runtime(self, runtime):
        self.case_runtime = runtime
        self.solver.set_case_runtime(runtime)
        self.problem.set_case_runtime(runtime)
        return self

    def set_input_artifacts(self, refs):
        expected = {"hybrid_summary", "directions_summary"}
        if set(refs) != expected:
            raise ValueError("outer_nested requires both upstream summary inputs")
        self.input_artifacts = dict(refs)

    def _load_baselines(self):
        if not self.input_artifacts:
            return {"source": "builtin", "reason": "no upstream Artifacts supplied",
                    "summaries": {}, "bindings": {}}
        summaries, bindings = {}, {}
        for name, binding in self.case_runtime.request.input_artifact_bindings.items():
            receipt = binding.publication
            reader = ArtifactPublisher.from_resource_context(
                self.case_runtime.request.resource_context,
                project_run_id=receipt.project_run_id, case_run_id=receipt.case_run_id)
            summaries[name] = json.loads(reader.read_verified(binding).decode("utf-8"))
            bindings[name] = binding.as_dict()
        return {"source": "authoritative_artifacts", "summaries": summaries, "bindings": bindings}

    def run(self):
        if self.case_runtime is None:
            raise RuntimeError("use run_solver.py or the Project group 'nested' for L0-authorized nesting")
        self.baselines = self._load_baselines()
        return self.solver.run(max_steps=self.settings.steps,
                               max_step_attempts=self.settings.steps + 3)

    def export_case_result(self, raw_output):
        result = self.solver.export_case_result(raw_output)
        summary = {"schema": "assembly_workbench.outer_nested/v1", "case": "outer_nested",
            "best_objectives": result.best_objectives.tolist(),
            "committed_steps": int(self.solver.generation),
            "evaluation_count": int(self.solver.evaluation_count),
            "inner_call_count": len(self.problem.calls),
            "pool_id": self.solver.solution_pool.pool_id,
            "identity": self.case_runtime.identity.as_dict(),
            "resource_grant": dict(self.resource_context.grant),
            "resource_binding_current": bool(dict(self.resource_binding_audit or {}).get("current", False)),
            "baseline_source": self.baselines["source"]}
        report = make_transport_safe({"schema": "assembly_workbench.nested_report/v1", "summary": summary,
            "baseline_inputs": self.baselines, "calls": list(self.problem.calls),
            "semantics": {"kind": "evaluation_delegation",
                "outer_objective": "inner_loss + 0.05 * x**2",
                "baseline_use": "authoritative comparison reports, not shared mutable candidates",
                "pool_isolation": "one separate pool per Case invocation"}}, path="outer_nested.report")
        summary = report["summary"]
        refs = dict(result.artifact_refs)
        for name, value in (("summary", summary), ("nested_report", report)):
            # Enclosing Case publication is sealed after this exporter and
            # result serialization succeed, separately from Solver lifecycle.
            refs[name] = self.case_runtime.publish_artifact(name, value, serializer="json",
                kind="nested-orchestration", metadata={"schema": value["schema"]})
            atomic_write_text(self.output_dir / f"{name}.json",
                json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))
        return replace(result, artifact_refs=refs,
            metadata={**dict(result.metadata), "summary": summary, "nested_report": report})
```
