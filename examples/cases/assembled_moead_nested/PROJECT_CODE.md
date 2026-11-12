# 本 Project 全部代码与配置

生成日期：2026-10-19。以下是实际文件的阅读快照。程序源码是权威；修改代码请编辑原文件。
包含全部项目 Python、本地 Catalog TOML、Case 标记和忽略配置；排除运行结果、缓存和本地 `.blackbase/`。
框架已有组件的完整实现见 [COMPONENTS.md](COMPONENTS.md)，没有复制为第二份 Case 实现。

共 27 个源码／配置文件。说明见 [README.md](README.md)，真实结果见 [RESULTS.md](RESULTS.md)。

## 文件索引

- [.gitignore](.gitignore)
- [_bootstrap.py](_bootstrap.py)
- [cases/__init__.py](cases/__init__.py)
- [cases/direction_refinement/.case](cases/direction_refinement/.case)
- [cases/direction_refinement/__init__.py](cases/direction_refinement/__init__.py)
- [cases/direction_refinement/adapter/__init__.py](cases/direction_refinement/adapter/__init__.py)
- [cases/direction_refinement/adapter/composition.py](cases/direction_refinement/adapter/composition.py)
- [cases/direction_refinement/bias/__init__.py](cases/direction_refinement/bias/__init__.py)
- [cases/direction_refinement/build_solver.py](cases/direction_refinement/build_solver.py)
- [cases/direction_refinement/build_trainer.py](cases/direction_refinement/build_trainer.py)
- [cases/direction_refinement/catalog/entries/plugin.toml](cases/direction_refinement/catalog/entries/plugin.toml)
- [cases/direction_refinement/catalog/entries/problem.toml](cases/direction_refinement/catalog/entries/problem.toml)
- [cases/direction_refinement/config.py](cases/direction_refinement/config.py)
- [cases/direction_refinement/evaluation/__init__.py](cases/direction_refinement/evaluation/__init__.py)
- [cases/direction_refinement/pipeline/__init__.py](cases/direction_refinement/pipeline/__init__.py)
- [cases/direction_refinement/pipeline/main.py](cases/direction_refinement/pipeline/main.py)
- [cases/direction_refinement/plugins/__init__.py](cases/direction_refinement/plugins/__init__.py)
- [cases/direction_refinement/plugins/trace.py](cases/direction_refinement/plugins/trace.py)
- [cases/direction_refinement/problem/__init__.py](cases/direction_refinement/problem/__init__.py)
- [cases/direction_refinement/problem/two_targets.py](cases/direction_refinement/problem/two_targets.py)
- [cases/direction_refinement/run_solver.py](cases/direction_refinement/run_solver.py)
- [cases/direction_refinement/run_trainer.py](cases/direction_refinement/run_trainer.py)
- [cases/direction_refinement/runtime/__init__.py](cases/direction_refinement/runtime/__init__.py)
- [cases/direction_refinement/solver/__init__.py](cases/direction_refinement/solver/__init__.py)
- [project_config.py](project_config.py)
- [run_and_report.py](run_and_report.py)
- [run_project.py](run_project.py)

## 1. [.gitignore](.gitignore)

源文件 SHA256：`dc0c67e07f875b4900c7e303a52bcb69d7c9550fb9fa8a331d9c89f968a16f6c`；3 行。

````text
.blackbase/
__pycache__/
*.pyc
````

## 2. [_bootstrap.py](_bootstrap.py)

源文件 SHA256：`873ea5f2cc48966f69c16f11dde4fef3987b214aa8f9a0f62c435d8aa9269ad4`；22 行。

````python
"""Path bootstrap that ensures project/framework imports work."""
from __future__ import annotations

import sys
from pathlib import Path


def ensure_importable():
    """Add project root and framework parents to sys.path."""
    root = Path(__file__).resolve().parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    # Ensure sibling framework packages are discoverable
    _nsga_parent = root.parent
    if (_nsga_parent / "nsgablack").is_dir() and str(_nsga_parent) not in sys.path:
        sys.path.insert(0, str(_nsga_parent))


def bootstrap():
    """Backward-compatible bootstrap entry used by run_project.py."""
    ensure_importable()
````

## 3. [cases/__init__.py](cases/__init__.py)

源文件 SHA256：`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`；0 行。

````python

````

## 4. [cases/direction_refinement/.case](cases/direction_refinement/.case)

源文件 SHA256：`4b56f01688c60c78bcb6e8c16b87472314481b8200e4ace64e9f432e8f1ac861`；3 行。

````text
name = direction_refinement
kind = solver
framework = nsgablack
````

## 5. [cases/direction_refinement/__init__.py](cases/direction_refinement/__init__.py)

源文件 SHA256：`01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b`；0 行。

````python

````

## 6. [cases/direction_refinement/adapter/__init__.py](cases/direction_refinement/adapter/__init__.py)

源文件 SHA256：`01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b`；0 行。

````python

````

## 7. [cases/direction_refinement/adapter/composition.py](cases/direction_refinement/adapter/composition.py)

源文件 SHA256：`aaddbfbd3b047667168ae824dee8d0a0b307934bf035b61e6065ceb4dbbffcfe`；56 行。

````python
"""MOEA/D 方向视图 → 粗 VNS 结果视图 → 细 VNS → MOEA/D 自身竞争。"""
from nsgablack.adapters import (
    MOEADAdapter, MultiStrategyConfig, PoolTaskSpec, RoleSpec,
    StrategyRouterAdapter, VNSAdapter, subpools,
)
from nsgablack.representation import ContextGaussianMutation, GaussianMutation, UniformInitializer


def build_adapter(settings):
    moead = MOEADAdapter(
        name="directions", population_size=settings.directions, batch_size=3,
        neighborhood_size=3, decomposition="weighted_sum", random_seed=settings.seed,
        initializer=UniformInitializer(low=-2.0, high=2.0),
        mutator=GaussianMutation(sigma=0.3),
    )
    coarse = VNSAdapter(
        name="coarse_vns", batch_size=settings.neighborhood_batch,
        base_sigma=0.35, restart_on_stagnation=False,
        mutator=ContextGaussianMutation(base_sigma=0.35),
    )
    fine = VNSAdapter(
        name="fine_vns", batch_size=settings.neighborhood_batch,
        base_sigma=0.08, restart_on_stagnation=False,
        mutator=ContextGaussianMutation(base_sigma=0.08),
    )

    def phase_policy(context):
        # all(...) 只选当前可读视图，完成屏障必须在调度策略明确表达。
        if context["step"] < settings.bootstrap_steps or not moead.pool_views_ready:
            return "bootstrap"
        tasks = context["pool_tasks"]
        if tasks["coarse:0"]["status"] != "done":
            return "coarse"
        if tasks["fine:0"]["status"] != "done":
            return "fine"
        return "return" if tasks["moead:0"]["status"] != "done" else "complete"

    return StrategyRouterAdapter(
        name="nested_directions",
        roles=[
            RoleSpec("moead", moead, pool_task=PoolTaskSpec(
                "fine_proposals", mode="compete", phases=("return",), shuffle=False)),
            RoleSpec("coarse", coarse, pool_task=PoolTaskSpec(
                subpools.all(moead), count=1, steps=settings.local_steps,
                output="coarse_proposals", shuffle=False)),
            RoleSpec("fine", fine, pool_task=PoolTaskSpec(
                subpools.all(coarse), count=1, steps=settings.local_steps,
                output="fine_proposals", shuffle=False)),
        ],
        config=MultiStrategyConfig(
            total_batch_size=settings.router_budget, adapt_weights=False,
            phase_policy=phase_policy,
            phase_roles={"bootstrap": ["moead"], "coarse": ["coarse"],
                         "fine": ["fine"], "return": ["moead"], "complete": []},
        ),
    )
````

## 8. [cases/direction_refinement/bias/__init__.py](cases/direction_refinement/bias/__init__.py)

源文件 SHA256：`01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b`；0 行。

````python

````

## 9. [cases/direction_refinement/build_solver.py](cases/direction_refinement/build_solver.py)

源文件 SHA256：`28cf9d7bd740ed6bf61ee81dd61f57d6e5fa25590a4a6751f099a9abfb565c4d`；27 行。

````python
"""唯一 Case 装配入口；生命周期和求解循环全部复用正式框架。"""
from pathlib import Path
from nsgablack.core import ComposableSolver
from nsgablack.plugins import ParetoArchivePlugin
from nsgablack.project import apply_solver_component_overrides
from .adapter.composition import build_adapter
from .config import DemoConfig
from .pipeline import build_pipeline
from .plugins.trace import NestedTrace
from .problem import build_problem


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    overrides = dict(component_overrides or {})
    settings = DemoConfig(**{**dict(config or {}), **dict(overrides.pop("config", {}))})
    solver = ComposableSolver(
        problem=build_problem(), representation_pipeline=build_pipeline(),
        adapter=build_adapter(settings), resource_context=resource_context,
        plugin_strict=True, snapshot_strict=True,
    )
    solver.set_random_seed(settings.seed)
    solver.set_max_steps(settings.max_steps)
    solver.add_plugin(ParetoArchivePlugin())
    solver.add_plugin(NestedTrace(output_dir=Path(__file__).resolve().parents[2] / "results",
                                 max_records=settings.max_steps))
    apply_solver_component_overrides(solver, overrides)
    return solver
````

## 10. [cases/direction_refinement/build_trainer.py](cases/direction_refinement/build_trainer.py)

源文件 SHA256：`99f765e75df055fdefa2b0a2bbdc035a77c5669466fcb9bbd15da6e21a2b468f`；1 行。

````python
from .build_solver import build_solver as build_trainer
````

## 11. [cases/direction_refinement/catalog/entries/plugin.toml](cases/direction_refinement/catalog/entries/plugin.toml)

源文件 SHA256：`161912a97576243b6ed5ffbbe918c69dfeb08c6caa70ce8b609e812a2925e7f5`；17 行。

````toml
[[entry]]
key = "project.plugin.nested_trace"
title = "NestedTrace"
kind = "plugin"
import_path = "plugins.trace:NestedTrace"
tags = ["project", "example", "plugin", "observe", "subpool", "lineage"]
summary = "只读已提交状态，导出各层精确引用、视图来源和原始反馈供教学对账。"
context_requires = []
context_provides = []
context_mutates = []
context_cache = []
context_notes = ["从不构建 Unit、不修改候选或共享 context；输出为观察报告而非权威 Artifact。"]
use_when = ["核对方向视图、递归精修、实际求值与最终返回时。"]
minimal_wiring = ["from cases.direction_refinement.plugins.trace import NestedTrace", "solver.add_plugin(NestedTrace(output_dir=results, max_records=settings.max_steps))"]
required_companions = ["nsgablack.core:ComposableSolver"]
config_keys = ["output_dir", "max_records"]
example_entry = "cases.direction_refinement.build_solver:build_solver"
````

## 12. [cases/direction_refinement/catalog/entries/problem.toml](cases/direction_refinement/catalog/entries/problem.toml)

源文件 SHA256：`062d712ea87a284d1a10b050406e678390aef4f9fdad9d486effac7ce965fc35`；17 行。

````toml
[[entry]]
key = "project.problem.two_targets"
title = "TwoTargets"
kind = "tool"
import_path = "problem.two_targets:TwoTargets"
tags = ["project", "example", "problem", "multi_objective", "analytic"]
summary = "一维双目标 f=[(x-1)^2,(x+1)^2]；方向比较不改写原始目标。"
context_requires = []
context_provides = []
context_mutates = []
context_cache = []
context_notes = ["只定义原始目标和边界约束，不读取 Unit 或写共享 context。"]
use_when = ["核对 MOEA/D 投影视图与两层局部精修的原始求值时。"]
minimal_wiring = ["from cases.direction_refinement.problem import TwoTargets", "problem = TwoTargets()"]
required_companions = []
config_keys = []
example_entry = "cases.direction_refinement.build_solver:build_solver"
````

## 13. [cases/direction_refinement/config.py](cases/direction_refinement/config.py)

源文件 SHA256：`629b2e09f6be86c309e5243d128aa4ce5df854db49532e212b2a167ed33b2c97`；33 行。

````python
"""本例只声明规模；不修改解池容量，也不建立另一套资源配置。"""
from dataclasses import dataclass


@dataclass(frozen=True)
class DemoConfig:
    seed: int = 23
    directions: int = 6
    bootstrap_steps: int = 2
    local_steps: int = 2
    neighborhood_batch: int = 2
    router_budget: int = 6

    def __post_init__(self):
        for name in ("directions", "bootstrap_steps", "local_steps", "neighborhood_batch", "router_budget"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ValueError(f"{name} must be a positive integer")
        if self.directions < 2 or self.local_steps < 2 or self.bootstrap_steps < 2:
            raise ValueError("this teaching example requires at least two directions, bootstrap and local steps")
        if self.router_budget < self.directions or self.router_budget < self.neighborhood_batch:
            raise ValueError("router_budget must fit bootstrap and a complete neighborhood")

    @property
    def local_evaluations(self):
        return self.directions * (1 + (self.local_steps - 1) * self.neighborhood_batch)

    @property
    def return_steps(self):
        return (self.local_evaluations + self.router_budget - 1) // self.router_budget

    @property
    def max_steps(self):
        return self.bootstrap_steps + 2 * self.directions * self.local_steps + self.return_steps
````

## 14. [cases/direction_refinement/evaluation/__init__.py](cases/direction_refinement/evaluation/__init__.py)

源文件 SHA256：`01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b`；0 行。

````python

````

## 15. [cases/direction_refinement/pipeline/__init__.py](cases/direction_refinement/pipeline/__init__.py)

源文件 SHA256：`b7fb51f3c2989875ac0734a66f59ed8ced326eb62d427fc0d2f96567fe95ae98`；1 行。

````python
from .main import build_pipeline
````

## 16. [cases/direction_refinement/pipeline/main.py](cases/direction_refinement/pipeline/main.py)

源文件 SHA256：`4aa6ae00ca843b9ff73b6fcd8be83402d56f6c872579899d808b918aac6f99e4`；6 行。

````python
"""各算法共享问题修复；搜索初始化和变化在实际叶 Adapter 上装配。"""
from nsgablack.representation import ClipRepair, RepresentationPipeline


def build_pipeline():
    return RepresentationPipeline(repair=ClipRepair(low=-2.0, high=2.0))
````

## 17. [cases/direction_refinement/plugins/__init__.py](cases/direction_refinement/plugins/__init__.py)

源文件 SHA256：`01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b`；0 行。

````python

````

## 18. [cases/direction_refinement/plugins/trace.py](cases/direction_refinement/plugins/trace.py)

源文件 SHA256：`37297855a8411ab9406a2431c6e99f57db74c0ece129ed5ee7d9fd3cb1760ccb`；104 行。

````python
"""只观察已提交状态，最终输出精确引用和原始反馈，供报告对账。"""
from collections.abc import Mapping
import json
from pathlib import Path
from blackbase.participation import ParticipationContract
from nsgablack.adapters.subpools import adapter_path
from nsgablack.plugins.base import Plugin
from nsgablack.utils.engineering.file_io import atomic_write_text


def data_copy(value):
    return json.loads(json.dumps(value, allow_nan=False))


class NestedTrace(Plugin):
    participation = ParticipationContract()
    state_recovery_level = "L1"
    state_recovery_notes = "Bounded JSON observations with an explicit data codec."
    context_notes = ("Read-only committed pool/task/Unit observations; never ensures a Unit.",)

    def __init__(self, *, output_dir, max_records):
        super().__init__(name="nested_trace")
        if type(max_records) is not int or max_records < 1:
            raise ValueError("max_records must be a positive integer")
        self.output_dir = Path(output_dir)
        self.max_records = max_records
        self.run_id, self.initial, self.records = None, None, []

    def _observe(self):
        solver, root = self.solver, self.solver.adapter
        pool = solver.solution_pool
        roles = []
        for instance in root.units:
            wrapper, inner = instance.adapter, instance.adapter.inner
            path = adapter_path(root, inner)
            roles.append({
                "role": instance.role, "owner_path": list(path),
                "adapter_type": type(inner).__name__, "task": wrapper.task_status,
                "unit_exists": getattr(inner, "algorithm_unit", None) is not None,
                "current_unit_exists": getattr(inner, "current_unit", None) is not None,
                "neighborhood_unit_exists": getattr(inner, "neighborhood_unit", None) is not None,
                "views": list(pool.subpools_created_by(path)),
            })
        return {"logical_steps": int(solver.run_progress_steps),
                "evaluations": int(solver.evaluation_count),
                "phase": root.get_runtime_context_projection(solver).get("phase"),
                "roles": roles}

    def on_solver_init(self, solver):
        if self.run_id != solver.run_session.run_id:
            self.run_id, self.records = solver.run_session.run_id, []
            self.initial = self._observe()

    def on_generation_committed(self, generation, outcome):
        del generation
        if not outcome.get("committed", False):
            raise ValueError("observer requires a committed generation")
        if len(self.records) >= self.max_records:
            raise RuntimeError("teaching trace capacity exhausted")
        self.records.append(self._observe())

    def on_solver_finalized(self, result):
        del result
        solver, pool = self.solver, self.solver.solution_pool
        final, views, aggregates = self._observe(), {}, {}
        for role in final["roles"]:
            entries = []
            for name in role["views"]:
                refs = pool.subpool_refs(name)
                raw_f, raw_v = pool.read_raw_feedback(refs)
                entries.append({"name": name, "metadata": pool.subpool_metadata(name),
                    "refs": [ref.as_dict() for ref in refs],
                    "candidates": pool.read(refs).numeric_matrix.tolist(),
                    "raw_objectives": raw_f.tolist(), "raw_violations": raw_v.tolist()})
            views[role["role"]] = entries
            output = role["task"]["output"]
            if output is not None:
                aggregates[role["role"]] = {"name": output,
                    "members": len(pool.subpool_refs(output))}
        moead = next(item.adapter.inner for item in solver.adapter.units if item.role == "moead")
        refs = moead.get_population_solution_refs(solver)
        raw_f, raw_v = pool.read_raw_feedback(refs)
        payload = {**self.get_state(), "final": final, "views": views, "aggregates": aggregates,
                   "final_population": {"refs": [ref.as_dict() for ref in refs],
                       "candidates": pool.read(refs).numeric_matrix.tolist(),
                       "raw_objectives": raw_f.tolist(), "raw_violations": raw_v.tolist(),
                       "adapter_objectives": moead.pop_F.tolist()}}
        atomic_write_text(self.output_dir / "trace.json",
                          json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False))

    def get_state(self):
        return data_copy({"schema": "assembled_moead_nested.trace/v1", "max_records": self.max_records,
                          "run_id": self.run_id,
                          "initial": self.initial, "records": self.records})

    def set_state(self, state):
        if not isinstance(state, Mapping) or state.get("schema") != "assembled_moead_nested.trace/v1":
            raise ValueError("invalid nested trace state")
        saved = data_copy(dict(state))
        if saved.get("max_records") != self.max_records:
            raise ValueError("trace capacity differs from checkpoint")
        if not isinstance(saved.get("records"), list) or len(saved["records"]) > self.max_records:
            raise ValueError("invalid nested trace records")
        self.run_id, self.initial, self.records = saved["run_id"], saved["initial"], saved["records"]
````

## 19. [cases/direction_refinement/problem/__init__.py](cases/direction_refinement/problem/__init__.py)

源文件 SHA256：`c7a722c3f180983ebda475512863bd85bf1b8237d336e6ce35a44203c5b23877`；1 行。

````python
from .two_targets import TwoTargets, build_problem
````

## 20. [cases/direction_refinement/problem/two_targets.py](cases/direction_refinement/problem/two_targets.py)

源文件 SHA256：`bf0270acaa3373c131d5af1e99ba4e5ea6417c082c6d57acbe912e6c21d52ec3`；21 行。

````python
"""一维双目标问题，便于逐方向核对；原目标永不被标量覆盖。"""
import numpy as np
from nsgablack.core import BlackBoxProblem


class TwoTargets(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="two_targets", dimension=1, objectives=["min", "min"],
                         bounds={"x": (-2.0, 2.0)})

    def evaluate(self, candidate):
        x = float(np.asarray(candidate).reshape(-1)[0])
        return [(x - 1.0) ** 2, (x + 1.0) ** 2]

    def evaluate_constraints(self, candidate):
        x = float(np.asarray(candidate).reshape(-1)[0])
        return [max(0.0, abs(x) - 2.0)]


def build_problem():
    return TwoTargets()
````

## 21. [cases/direction_refinement/run_solver.py](cases/direction_refinement/run_solver.py)

源文件 SHA256：`ab283d8f4ae5229c5ed6e690ffba71ddfd54587d9d880bbb49da3558ccc24db9`；17 行。

````python
"""
CLI entry point for running the solver.

Usage:
    python run_solver.py
    python run_solver.py --check
"""

from blackbase.project import run_standard_case_cli


def main(argv=None):
    return run_standard_case_cli(__file__, framework="nsgablack", argv=argv)


if __name__ == "__main__":
    raise SystemExit(main())
````

## 22. [cases/direction_refinement/run_trainer.py](cases/direction_refinement/run_trainer.py)

源文件 SHA256：`baa1ed97eb52ac800e55abd523a65bf3345d0f0792bcd088d1d04e35eab52fdb`；4 行。

````python
from .run_solver import main

if __name__ == "__main__":
    raise SystemExit(main())
````

## 23. [cases/direction_refinement/runtime/__init__.py](cases/direction_refinement/runtime/__init__.py)

源文件 SHA256：`01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b`；0 行。

````python

````

## 24. [cases/direction_refinement/solver/__init__.py](cases/direction_refinement/solver/__init__.py)

源文件 SHA256：`01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b`；0 行。

````python

````

## 25. [project_config.py](project_config.py)

源文件 SHA256：`2143e37ea330d760a2f64c58cef5503ac5bc93e8f4716777f336804adaebf51b`；11 行。

````python
"""Project 只负责 Case 编排和唯一 L0 授权；算法阶段由 Case 内 Router 管理。"""
L0 = {
    "namespace": "assembled_moead_nested",
    "offer": {"threads": 1, "gpus": 0, "backend": "local", "device_tokens": []},
    "policy": {"mode": "strict", "gpu_sharing": "exclusive", "cpu_oversubscribe": False},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto", "execution_backend": "local",
}
STAGES = [{"name": "search", "cases": ["direction_refinement"], "policy": "serial",
           "resource_requests": {"direction_refinement": {"threads": 1, "gpus": 0, "backend": "local"}}}]
GROUPS = {"default": {"stages": ["search"]}}
````

## 26. [run_and_report.py](run_and_report.py)

源文件 SHA256：`ec74976cf5daab8d5055f6bb779b351efae209ac2fd3b7e77a60a25113f2b6e7`；162 行。

````python
"""运行正式 Project 并核对嵌套视图；不另造求解循环。"""
import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path
from _bootstrap import bootstrap

bootstrap()
from nsgablack.project.project_runner import execute_project
from nsgablack.utils.engineering.file_io import atomic_write_text
from cases.direction_refinement.config import DemoConfig
from cases.direction_refinement.problem import build_problem

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"


def write_json(path, value):
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))


def close(a, b):
    return math.isclose(float(a), float(b), rel_tol=1e-11, abs_tol=1e-12)


def summarize(project, trace):
    settings = DemoConfig()
    if project["exit_code"] != 0 or len(project["cases"]) != 1 or not project["cases"][0]["ok"]:
        raise RuntimeError("Project did not complete one successful Case")
    case = project["cases"][0]
    if not trace["run_id"].startswith(case["identity"]["case_run_id"] + ":solver-run:"):
        raise RuntimeError("trace does not belong to the formal Case run")
    rows = trace["records"]
    expected = (["bootstrap"] * settings.bootstrap_steps
                + ["coarse"] * (settings.directions * settings.local_steps)
                + ["fine"] * (settings.directions * settings.local_steps)
                + ["return"] * settings.return_steps)
    if [row["phase"] for row in rows] != expected:
        raise RuntimeError("actual committed phase order differs from task barriers")
    if [row["logical_steps"] for row in rows] != list(range(1, settings.max_steps + 1)):
        raise RuntimeError("logical step counters are not consecutive")
    evaluation_deltas = [rows[0]["evaluations"]] + [b["evaluations"] - a["evaluations"] for a, b in zip(rows, rows[1:])]
    expected_deltas = ([settings.directions] + [min(3, settings.directions)] * (settings.bootstrap_steps - 1)
        + ([1] + [settings.neighborhood_batch] * (settings.local_steps - 1)) * (2 * settings.directions)
        + [min(settings.router_budget, settings.local_evaluations - i * settings.router_budget)
           for i in range(settings.return_steps)])
    if evaluation_deltas != expected_deltas:
        raise RuntimeError("baseline/neighborhood/return evaluation increments differ from the assembled plan")
    initial = trace["initial"]["roles"]
    if any(r["unit_exists"] or r["current_unit_exists"] or r["neighborhood_unit_exists"] for r in initial):
        raise RuntimeError("a Unit was constructed before algorithm activation")
    for role_name, forbidden in (("coarse", {"bootstrap"}), ("fine", {"bootstrap", "coarse"})):
        for row in rows:
            role = next(r for r in row["roles"] if r["role"] == role_name)
            if row["phase"] in forbidden and (role["unit_exists"] or role["current_unit_exists"] or role["neighborhood_unit_exists"]):
                raise RuntimeError("inactive refiner constructed a Unit")
    views = trace["views"]
    if any(len(views[name]) != settings.directions for name in ("moead", "coarse", "fine")):
        raise RuntimeError("each algorithm must publish exactly one view per direction/task")
    coarse_by_id = {v["metadata"]["view_id"]: v for v in views["coarse"]}
    problem = build_problem()
    scores = []
    for fine in views["fine"]:
        metadata = fine["metadata"]
        coarse = coarse_by_id[metadata["parent"]["view_id"]]
        projection = metadata["projection"]
        if projection != coarse["metadata"]["projection"] or len(metadata["parent"]["ancestors"]) != 1:
            raise RuntimeError("fine result lost its frozen projection or two-level ancestry")
        if metadata["parent"]["revision"] != coarse["metadata"]["revision"]:
            raise RuntimeError("fine result references the wrong coarse revision")
        for view in (coarse, fine):
            if len(view["refs"]) != 1 or view["raw_violations"] != [0.0]:
                raise RuntimeError("a selected result has invalid identity or feasibility")
            actual = problem.evaluate(view["candidates"][0])
            if not all(close(a, b) for a, b in zip(actual, view["raw_objectives"][0])):
                raise RuntimeError("stored raw two-objective evidence disagrees with the analytic problem")
        weights = projection["weights"]
        coarse_score = sum(w*f for w, f in zip(weights, coarse["raw_objectives"][0]))
        fine_score = sum(w*f for w, f in zip(weights, fine["raw_objectives"][0]))
        if fine_score > coarse_score + 1e-11:
            raise RuntimeError("fine VNS selected a worse result in the same frozen comparison frame")
        optimum = (weights[0] - weights[1]) / sum(weights)
        scores.append({"slot": metadata["slot"], "weights": weights,
            "coarse_x": coarse["candidates"][0][0], "fine_x": fine["candidates"][0][0],
            "coarse_projected_score": coarse_score, "fine_projected_score": fine_score,
            "analytic_direction_optimum_x": optimum,
            "fine_distance_to_direction_optimum": abs(fine["candidates"][0][0] - optimum),
            "coarse_view_id": coarse["metadata"]["view_id"], "fine_view_id": metadata["view_id"]})
    population = trace["final_population"]
    if len(population["refs"]) != settings.directions or population["adapter_objectives"] != population["raw_objectives"]:
        raise RuntimeError("MOEA/D population identity/raw objective alignment is invalid")
    if any(not all(close(a, b) for a, b in zip(problem.evaluate(x), f))
           for x, f in zip(population["candidates"], population["raw_objectives"])):
        raise RuntimeError("MOEA/D raw objectives were changed by a projection")
    final = trace["final"]
    if any(role["task"]["status"] != "done" for role in final["roles"]):
        raise RuntimeError("not all nested tasks and return competition completed")
    if case["output"]["report"]["evaluation_count"] != final["evaluations"]:
        raise RuntimeError("formal evaluation count disagrees with committed observations")
    if not case["resource_usage"]["binding"]["current"]:
        raise RuntimeError("effective Project L0 grant is not bound")
    phases, previous = [], 0
    for name in ("bootstrap", "coarse", "fine", "return"):
        stage = [row for row in rows if row["phase"] == name]
        phases.append({"phase": name, "steps": len(stage), "evaluations": stage[-1]["evaluations"] - previous})
        previous = stage[-1]["evaluations"]
    return {"project_run_id": project["run_id"], "solver_run_id": trace["run_id"],
        "case_run_id": case["identity"]["case_run_id"], "status": case["status"],
        "config": asdict(settings), "logical_steps": final["logical_steps"], "evaluations": final["evaluations"],
        "phases": phases, "per_step_evaluation_deltas": evaluation_deltas,
        "directions": sorted(scores, key=lambda row: row["slot"]),
        "aggregates": trace["aggregates"], "final_population": population,
        "resource_binding_current": True, "resource_grant": case["resource_usage"]["authorized_grant"],
        "case_elapsed_seconds": case["elapsed_seconds"],
        "checks": ["同一次 Project/Case/轨迹运行", "真实阶段屏障与连续提交计数",
            "各层每个任务都真实求值基准和邻域，返回每批也重新求值",
            "未激活的粗细 VNS 均未创建 Unit", "六方向各有粗搜和细搜最终选择视图",
            "冻结父视图身份、revision、祖先和投影保持一致", "细搜同方向分数不劣于粗搜起点",
            "存储 raw feedback 与解析双目标一致", "返回 MOEA/D 后仍是原始双目标而非标量",
            "粗搜、细搜和返回池任务均已完成", "正式求值计数与 Project L0 授权对账"]}


def write_report(summary):
    lines = ["# MOEA/D → 粗 VNS → 细 VNS → MOEA/D：真实运行结果", "",
        f"Project run：`{summary['project_run_id']}`。", "",
        f"完成 **{summary['logical_steps']} 次逻辑提交、{summary['evaluations']} 次实际求值**。", "",
        "本例是双目标问题，没有唯一的‘全局最优 x’。下列标量只在各自方向的固定权重下比较。", "", "## 分阶段对账", ""]
    lines += [f"- `{p['phase']}`：{p['steps']} 步、{p['evaluations']} 次求值。" for p in summary["phases"]]
    lines += ["", "## 每方向的两层结果", ""]
    for d in summary["directions"]:
        lines.append(f"- 方向 {d['slot']}，权重 `{d['weights']}`：粗搜 x=`{d['coarse_x']:.9g}`、投影分数 `{d['coarse_projected_score']:.9g}`；细搜 x=`{d['fine_x']:.9g}`、分数 `{d['fine_projected_score']:.9g}`；该方向解析最优 x=`{d['analytic_direction_optimum_x']:.9g}`。")
    lines += ["", "## 核对", ""] + [f"- {check}。" for check in summary["checks"]]
    lines += ["", "## 数据文件", "", "- [精简结果](results/summary.json)",
        "- [逐步观测、精确 SolutionRef、视图元数据和 raw 反馈](results/trace.json)",
        "- [正式 Project 返回值](results/project_result.json)", "",
        "解析重算和方向分数计算发生在报告阶段，不计入求解器求值预算，不冒充新发布的权威证据。轨迹文件是观察文件；正式 Artifact 收据和执行记录仍以 Project 返回与 `.blackbase/` 为准。",
        "该运行只验证装配和语义交接，不证明嵌套精修优于其他算法。", ""]
    atomic_write_text(ROOT / "RESULTS.md", "\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    if not args.report_only:
        result = execute_project(ROOT)
        write_json(RESULTS / "project_result.json", result.as_dict())
        if not result.ok:
            return result.exit_code or 1
    project = json.loads((RESULTS / "project_result.json").read_text(encoding="utf-8"))
    trace = json.loads((RESULTS / "trace.json").read_text(encoding="utf-8"))
    summary = summarize(project, trace)
    write_json(RESULTS / "summary.json", summary)
    write_report(summary)
    print(json.dumps({"status": summary["status"], "steps": summary["logical_steps"],
        "evaluations": summary["evaluations"], "report": str(ROOT / "RESULTS.md")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````

## 27. [run_project.py](run_project.py)

源文件 SHA256：`7bda03a21a381307647fdac0e4da4f1bd28ba84ac81b31d1f143dd2ef0004b68`；12 行。

````python
"""Run this project through the shared blackbase Project substrate."""

from pathlib import Path

from _bootstrap import bootstrap


if __name__ == "__main__":
    bootstrap()
    from nsgablack.project.project_runner import main

    raise SystemExit(main(Path(__file__).resolve().parent))
````
