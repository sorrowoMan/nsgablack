# 本 Project 全部代码与配置

生成日期：2026-10-19。以下是实际文件的阅读快照。程序源码是权威；修改代码请编辑原文件。
包含全部项目 Python、本地 Catalog TOML、Case 标记和忽略配置；排除运行结果、缓存和本地 `.blackbase/`。
框架已有组件的完整实现见 [COMPONENTS.md](COMPONENTS.md)，没有复制为第二份 Case 实现。

共 26 个源码／配置文件。说明见 [README.md](README.md)，真实结果见 [RESULTS.md](RESULTS.md)。

## 文件索引

- [.gitignore](.gitignore)
- [_bootstrap.py](_bootstrap.py)
- [cases/__init__.py](cases/__init__.py)
- [cases/pool_recovery/.case](cases/pool_recovery/.case)
- [cases/pool_recovery/__init__.py](cases/pool_recovery/__init__.py)
- [cases/pool_recovery/adapter/__init__.py](cases/pool_recovery/adapter/__init__.py)
- [cases/pool_recovery/adapter/composition.py](cases/pool_recovery/adapter/composition.py)
- [cases/pool_recovery/bias/__init__.py](cases/pool_recovery/bias/__init__.py)
- [cases/pool_recovery/build_solver.py](cases/pool_recovery/build_solver.py)
- [cases/pool_recovery/build_trainer.py](cases/pool_recovery/build_trainer.py)
- [cases/pool_recovery/catalog/entries/components.toml](cases/pool_recovery/catalog/entries/components.toml)
- [cases/pool_recovery/config.py](cases/pool_recovery/config.py)
- [cases/pool_recovery/evaluation/__init__.py](cases/pool_recovery/evaluation/__init__.py)
- [cases/pool_recovery/pipeline/__init__.py](cases/pool_recovery/pipeline/__init__.py)
- [cases/pool_recovery/pipeline/main.py](cases/pool_recovery/pipeline/main.py)
- [cases/pool_recovery/plugins/__init__.py](cases/pool_recovery/plugins/__init__.py)
- [cases/pool_recovery/plugins/trace.py](cases/pool_recovery/plugins/trace.py)
- [cases/pool_recovery/problem/__init__.py](cases/pool_recovery/problem/__init__.py)
- [cases/pool_recovery/problem/plateau.py](cases/pool_recovery/problem/plateau.py)
- [cases/pool_recovery/run_solver.py](cases/pool_recovery/run_solver.py)
- [cases/pool_recovery/run_trainer.py](cases/pool_recovery/run_trainer.py)
- [cases/pool_recovery/runtime/__init__.py](cases/pool_recovery/runtime/__init__.py)
- [cases/pool_recovery/solver/__init__.py](cases/pool_recovery/solver/__init__.py)
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

## 4. [cases/pool_recovery/.case](cases/pool_recovery/.case)

源文件 SHA256：`585c42b8113da538e0f8926735dc935162a7e44ac9516e3fb2f823d87e350651`；3 行。

````text
name = pool_recovery
kind = solver
framework = nsgablack
````

## 5. [cases/pool_recovery/__init__.py](cases/pool_recovery/__init__.py)

源文件 SHA256：`01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b`；0 行。

````python

````

## 6. [cases/pool_recovery/adapter/__init__.py](cases/pool_recovery/adapter/__init__.py)

源文件 SHA256：`7f79bc298f4b4d6ae8592c60a1338667fb3a23aa60c880e5e52c7bcad1697ffa`；5 行。

````python

"""Case-level adapter assembly."""
from .composition import build_adapter

__all__ = ["build_adapter"]
````

## 7. [cases/pool_recovery/adapter/composition.py](cases/pool_recovery/adapter/composition.py)

源文件 SHA256：`8fa575080b977da6393cc32d70c861b51c8dc313fbc659c56a2ad535c675a540`；31 行。

````python
"""Compose the public pool preparation/search/recovery/return state machine."""
from nsgablack.adapters import (
    NSGA2Adapter, SPEA2Adapter, PoolSearchAdapter, PoolSearchSpec,
    SimulatedAnnealingAdapter,
)
from nsgablack.representation import UniformInitializer, GaussianMutation, ContextGaussianMutation


def build_adapter(settings):
    # Separate mutable operator instances: no shared RNG or hidden aliasing.
    sa = SimulatedAnnealingAdapter(
        name="seed_and_recovery_sa", batch_size=settings.producer_batch_size,
        base_sigma=settings.sigma, initial_temperature=0.4, cooling_rate=0.9,
        initializer=UniformInitializer(low=-0.15, high=0.15),
        mutator=ContextGaussianMutation(base_sigma=settings.sigma),
    )
    searchers = [
        NSGA2Adapter(name="population_a", population_size=settings.population_size,
                     offspring_size=settings.offspring_size,
                     mutator=GaussianMutation(sigma=settings.sigma)),
        SPEA2Adapter(name="population_b", population_size=settings.population_size,
                     offspring_size=settings.offspring_size,
                     mutator=GaussianMutation(sigma=settings.sigma)),
    ]
    return PoolSearchAdapter(
        producer=sa,
        searches=[PoolSearchSpec(adapter, initial_count=settings.initial_count_per_population)
                  for adapter in searchers],
        stagnation_steps=settings.stagnation_steps, recovery_steps=settings.recovery_steps,
        restart_recovery=True, name="pooled_search",
    )
````

## 8. [cases/pool_recovery/bias/__init__.py](cases/pool_recovery/bias/__init__.py)

源文件 SHA256：`01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b`；0 行。

````python

````

## 9. [cases/pool_recovery/build_solver.py](cases/pool_recovery/build_solver.py)

源文件 SHA256：`a2f72aeea1d22f735cc57add6f1a903e125751979a2c8a4ae405d59bdc332e56`；23 行。

````python
"""One canonical Case assembly; resource authorization comes from Project L0."""
from pathlib import Path
from nsgablack.core import ComposableSolver
from nsgablack.project import apply_solver_component_overrides
from .config import DemoConfig
from .problem import build_problem
from .pipeline import build_pipeline
from .adapter import build_adapter
from .plugins import PoolTracePlugin


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    overrides = dict(component_overrides or {})
    settings = DemoConfig(**{**dict(config or {}), **dict(overrides.pop("config", {}))})
    solver = ComposableSolver(problem=build_problem(), representation_pipeline=build_pipeline(),
                              adapter=build_adapter(settings), resource_context=resource_context,
                              plugin_strict=True, snapshot_strict=True)
    solver.set_random_seed(settings.seed)
    solver.set_max_steps(settings.max_steps)
    solver.add_plugin(PoolTracePlugin(output_dir=Path(__file__).resolve().parents[2] / "results",
                                      max_records=settings.max_steps))
    apply_solver_component_overrides(solver, overrides)
    return solver
````

## 10. [cases/pool_recovery/build_trainer.py](cases/pool_recovery/build_trainer.py)

源文件 SHA256：`99f765e75df055fdefa2b0a2bbdc035a77c5669466fcb9bbd15da6e21a2b468f`；1 行。

````python
from .build_solver import build_solver as build_trainer
````

## 11. [cases/pool_recovery/catalog/entries/components.toml](cases/pool_recovery/catalog/entries/components.toml)

源文件 SHA256：`0e06e3f48cfe9b5b886bb3beb6d138c9aa40fde485a5738f5579dd1d63063d3c`；71 行。

````toml
[[entry]]
key = "project.problem.plateau"
title = "PlateauProblem"
kind = "tool"
import_path = "problem.plateau:PlateauProblem"
tags = ["example", "problem", "plateau"]
summary = "二维真实平坦最优区域，演示按原始求值度量停滞触发。"
context_requires = []
context_provides = []
context_mutates = []
context_cache = []
context_notes = ["只定义原始目标与盒约束。"]
use_when = ["以很小预算检查停滞恢复调度。"]
minimal_wiring = ["from cases.pool_recovery.problem import build_problem", "problem = build_problem()"]
required_companions = []
config_keys = []
example_entry = "cases.pool_recovery.build_solver:build_solver"

[[entry]]
key = "project.adapter.pool_recovery"
title = "Pool recovery composition"
kind = "tool"
import_path = "adapter.composition:build_adapter"
tags = ["example", "assembly", "sa", "nsga2", "spea2", "pool"]
summary = "使用正式 PoolSearchAdapter 装配准备、双种群、停滞恢复与返回竞争。"
context_requires = []
context_provides = []
context_mutates = []
context_cache = []
context_notes = ["这是装配工厂，运行契约由实际 Adapter 声明。"]
use_when = ["检查初始配额、种群容量和恢复批量的独立配置。"]
minimal_wiring = ["from cases.pool_recovery.config import DemoConfig", "from cases.pool_recovery.adapter import build_adapter", "adapter = build_adapter(DemoConfig())"]
required_companions = ["nsgablack.adapters:PoolSearchAdapter"]
config_keys = ["initial_count_per_population", "population_size", "offspring_size", "stagnation_steps", "recovery_steps"]
example_entry = "cases.pool_recovery.build_solver:build_solver"

[[entry]]
key = "project.pipeline.pool_recovery"
title = "Shared problem repair pipeline"
kind = "tool"
import_path = "pipeline.main:build_pipeline"
tags = ["example", "pipeline", "repair"]
summary = "共享问题修复管线，叶 Adapter 自己绑定初始化与变化组件。"
context_requires = []
context_provides = []
context_mutates = []
context_cache = []
context_notes = ["只装配 ClipRepair，不构建 Unit 或决定算法成员。"]
use_when = ["多个算法共享问题可行性处理。"]
minimal_wiring = ["from cases.pool_recovery.pipeline import build_pipeline", "pipeline = build_pipeline()"]
required_companions = ["nsgablack.representation:RepresentationPipeline"]
config_keys = []
example_entry = "cases.pool_recovery.build_solver:build_solver"

[[entry]]
key = "project.plugin.pool_trace"
title = "PoolTracePlugin"
kind = "plugin"
import_path = "plugins.trace:PoolTracePlugin"
tags = ["example", "observe", "plugin", "pool", "lazy_unit"]
summary = "观察真实执行阶段、已提交阶段、精确成员引用与来源。"
context_requires = []
context_provides = []
context_mutates = []
context_cache = []
context_notes = ["不创建 Unit，不切换阶段，输出只是观察报告。"]
use_when = ["核对 preparing/search/recovery/return 是否真实执行。"]
minimal_wiring = ["from cases.pool_recovery.plugins import PoolTracePlugin", "solver.add_plugin(PoolTracePlugin(output_dir=results, max_records=settings.max_steps))"]
required_companions = ["nsgablack.core:ComposableSolver"]
config_keys = ["max_records", "output_dir"]
example_entry = "cases.pool_recovery.build_solver:build_solver"
````

## 12. [cases/pool_recovery/config.py](cases/pool_recovery/config.py)

源文件 SHA256：`6ae0b2c3a20ec19aac3ae1d35e56f457409677f723a66261e08772b444b9ff1c`；23 行。

````python
"""Small deterministic settings that expose one full recovery cycle."""
from dataclasses import dataclass


@dataclass(frozen=True)
class DemoConfig:
    seed: int = 23
    max_steps: int = 8
    initial_count_per_population: int = 3
    population_size: int = 3
    offspring_size: int = 2
    producer_batch_size: int = 3
    stagnation_steps: int = 1
    recovery_steps: int = 2
    sigma: float = 0.04

    def __post_init__(self):
        for name in ("max_steps", "initial_count_per_population", "population_size",
                     "offspring_size", "producer_batch_size", "stagnation_steps", "recovery_steps"):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if self.population_size < 2 or self.sigma <= 0:
            raise ValueError("population_size >= 2 and sigma > 0 are required")
````

## 13. [cases/pool_recovery/evaluation/__init__.py](cases/pool_recovery/evaluation/__init__.py)

源文件 SHA256：`01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b`；0 行。

````python

````

## 14. [cases/pool_recovery/pipeline/__init__.py](cases/pool_recovery/pipeline/__init__.py)

源文件 SHA256：`2b7e90eec58336e81c6e3b8eddd64aacb65d8f17ac25bb88c72ff9ee82914efb`；3 行。

````python
from .main import build_pipeline

__all__ = ["build_pipeline"]
````

## 15. [cases/pool_recovery/pipeline/main.py](cases/pool_recovery/pipeline/main.py)

源文件 SHA256：`9720b9ef863a85a6ada1536fd6f3986f4ae452d60407fb0089d3554a052d4f0a`；6 行。

````python
"""Only problem repair lives in the shared candidate pipeline."""
from nsgablack.representation import ClipRepair, RepresentationPipeline


def build_pipeline():
    return RepresentationPipeline(repair=ClipRepair(low=-2.0, high=2.0))
````

## 16. [cases/pool_recovery/plugins/__init__.py](cases/pool_recovery/plugins/__init__.py)

源文件 SHA256：`ae7adb316d24d854166e885aea6328fb903ac17f0c872659c9e21a387f0b5277`；4 行。

````python

from .trace import PoolTracePlugin

__all__ = ["PoolTracePlugin"]
````

## 17. [cases/pool_recovery/plugins/trace.py](cases/pool_recovery/plugins/trace.py)

源文件 SHA256：`760360324b8a2181d82e069002539345fc44518e514ce9d2ab116fc91541eace`；110 行。

````python
"""Observe committed pool phases without creating Units or controlling search."""
import csv
import io
import json
from collections.abc import Mapping
from pathlib import Path
from blackbase.participation import ParticipationContract
from nsgablack.plugins.base import Plugin
from nsgablack.utils.engineering.file_io import atomic_write_text


def data_copy(value):
    return json.loads(json.dumps(value, allow_nan=False))


class PoolTracePlugin(Plugin):
    participation = ParticipationContract()
    state_recovery_level = "L1"
    state_recovery_notes = "Bounded JSON observations of committed phases."
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Reads owned algorithm state and exact pool references; never constructs Units."

    def __init__(self, *, output_dir, max_records):
        super().__init__(name="pool_recovery_trace")
        self.output_dir = Path(output_dir)
        if type(max_records) is not int or max_records < 1:
            raise ValueError("max_records must be a positive integer")
        self.max_records = max_records
        self.run_id, self.initial, self.records = None, None, []
        self._attempt_phase = None

    def observe(self):
        solver, root = self.solver, self.solver.adapter
        pool = solver.solution_pool
        populations = {}
        for spec in root.searches:
            adapter = spec.adapter
            structure = adapter.algorithm_unit
            members = None if structure is None else structure.population
            refs = () if members is None else adapter.get_population_solution_refs(solver)
            populations[adapter.name] = {
                "type": type(adapter).__name__, "unit_exists": structure is not None,
                "members": 0 if members is None else len(members),
                "refs": [ref.as_dict() for ref in refs],
                "provenance": list(pool.read_provenance(refs)) if refs else [],
            }
        incumbent = solver.get_incumbent()
        return {
            "steps": int(solver.run_progress_steps), "evaluations": int(solver.evaluation_count),
            "phase_after": root.phase, "prepared_count": root.prepared_count,
            "stagnation": root.stagnation, "best_metric": root.best_metric,
            "recovery_count": root.recovery_count,
            "input_remaining": {name: pool.input_remaining(key) for name, key in root.input_ids.items()},
            "pool_records": pool.record_count, "pool_sequence": pool.timestamp.sequence,
            "sa_unit_exists": root.producer.algorithm_unit is not None,
            "sa_temperature": float(root.producer.temperature),
            "sa_current_score": root.producer.current_score,
            "populations": populations,
            "best_selection_score": None if incumbent is None else float(incumbent.score),
        }

    def on_solver_init(self, solver):
        run_id = solver.run_session.run_id
        if self.run_id != run_id:
            self.records, self.initial = [], None
        self.run_id = run_id
        if self.initial is None:
            self.initial = self.observe()

    def on_step_attempt_start(self, attempt, logical_step):
        self._attempt_phase = self.solver.adapter.phase

    def on_generation_committed(self, generation, outcome):
        if not outcome.get("committed"):
            raise ValueError("trace requires a committed step")
        if len(self.records) >= self.max_records:
            raise ValueError("the teaching trace exhausted its configured committed-step capacity")
        self.records.append({"generation": int(generation), "executed_phase": self._attempt_phase,
                             **self.observe()})

    def on_solver_finalized(self, result):
        payload = {**self.get_state(), "final": self.observe()}
        atomic_write_text(self.output_dir / "trace.json",
                          json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False))
        fields = ("steps", "executed_phase", "phase_after", "evaluations", "prepared_count",
                  "stagnation", "recovery_count", "sa_temperature", "best_selection_score")
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({name: row[name] for name in fields} for row in self.records)
        atomic_write_text(self.output_dir / "trace.csv", stream.getvalue())

    def get_state(self):
        return data_copy({"schema": "assembled_pool_recovery.trace/v1", "run_id": self.run_id,
                          "max_records": self.max_records,
                          "initial": self.initial, "records": self.records})

    def set_state(self, state):
        if not isinstance(state, Mapping) or state.get("schema") != "assembled_pool_recovery.trace/v1":
            raise ValueError("unsupported trace state")
        saved = data_copy(dict(state))
        if saved.get("max_records") != self.max_records:
            raise ValueError("trace capacity changed since checkpoint")
        if not isinstance(saved.get("records"), list) or len(saved["records"]) > self.max_records:
            raise ValueError("invalid trace records")
        self.run_id, self.initial, self.records = saved["run_id"], saved["initial"], saved["records"]
        self._attempt_phase = None
````

## 18. [cases/pool_recovery/problem/__init__.py](cases/pool_recovery/problem/__init__.py)

源文件 SHA256：`9ad1e9d00ebe7c4fcf11d40b0b5a4a19842f8ebdeb3ad2f0e816fed38e835bc9`；4 行。

````python
"""Problem definition and factory."""
from .plateau import PlateauProblem, build_problem

__all__ = ["PlateauProblem", "build_problem"]
````

## 19. [cases/pool_recovery/problem/plateau.py](cases/pool_recovery/problem/plateau.py)

源文件 SHA256：`9aeb9f136980eb6b19d8e850165d4523f1770b3948aec814575018450830e76c`；22 行。

````python
"""A real flat objective region makes a short, reproducible stagnation demo."""
import numpy as np
from nsgablack.core import BlackBoxProblem
from nsgablack.units.contracts import candidate_array


class PlateauProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="二维平坦区域恢复演示", dimension=2, objectives=["minimize"],
                         bounds={"x0": (-2.0, 2.0), "x1": (-2.0, 2.0)})

    def evaluate(self, candidate):
        x = candidate_array(candidate)
        return max(0.0, float(np.dot(x, x)) - 1.0)

    def evaluate_constraints(self, candidate):
        x = candidate_array(candidate)
        return np.maximum(-2.0 - x, 0.0) + np.maximum(x - 2.0, 0.0)


def build_problem():
    return PlateauProblem()
````

## 20. [cases/pool_recovery/run_solver.py](cases/pool_recovery/run_solver.py)

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

## 21. [cases/pool_recovery/run_trainer.py](cases/pool_recovery/run_trainer.py)

源文件 SHA256：`baa1ed97eb52ac800e55abd523a65bf3345d0f0792bcd088d1d04e35eab52fdb`；4 行。

````python
from .run_solver import main

if __name__ == "__main__":
    raise SystemExit(main())
````

## 22. [cases/pool_recovery/runtime/__init__.py](cases/pool_recovery/runtime/__init__.py)

源文件 SHA256：`01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b`；0 行。

````python

````

## 23. [cases/pool_recovery/solver/__init__.py](cases/pool_recovery/solver/__init__.py)

源文件 SHA256：`01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b`；0 行。

````python

````

## 24. [project_config.py](project_config.py)

源文件 SHA256：`035f75a26d22c2b73cb38950a0c4315a935ba14fbcfb9771e62db86ff11546e3`；11 行。

````python
"""Project L0 owns the grant; algorithm phases belong to the Case Adapter."""
L0 = {
    "namespace": "assembled_pool_recovery",
    "offer": {"threads": 1, "gpus": 0, "backend": "local", "device_tokens": []},
    "policy": {"mode": "strict", "gpu_sharing": "exclusive", "cpu_oversubscribe": False},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto", "execution_backend": "local",
}
STAGES = [{"name": "recovery_demo", "cases": ["pool_recovery"], "policy": "serial",
           "resource_requests": {"pool_recovery": {"threads": 1, "gpus": 0, "backend": "local"}}}]
GROUPS = {"default": {"stages": ["recovery_demo"]}}
````

## 25. [run_and_report.py](run_and_report.py)

源文件 SHA256：`1f94ca04ac2fa0fd1d396668c61dd309aa7b78987b4d1370b0522a171f343844`；119 行。

````python
"""Run the official Project runner, then validate and export teaching results."""
import argparse
import json
from collections import Counter
from pathlib import Path
from _bootstrap import bootstrap

bootstrap()
from nsgablack.project.project_runner import execute_project
from nsgablack.utils.engineering.file_io import atomic_write_text

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"


def write_json(path, value):
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))


def summarize(project, trace):
    if project["exit_code"] or len(project["cases"]) != 1 or not project["cases"][0]["ok"]:
        raise RuntimeError("Project did not return one successful Case")
    case = project["cases"][0]
    if not trace["run_id"].startswith(case["identity"]["case_run_id"] + ":solver-run:"):
        raise RuntimeError("trace and formal result belong to different runs")
    rows, initial, final = trace["records"], trace["initial"], trace["final"]
    expected = ["preparing"] * 3 + ["search"] * 2 + ["recovery"] * 2 + ["return"]
    if [row["executed_phase"] for row in rows] != expected:
        raise RuntimeError("the default example did not execute its complete intended phase cycle")
    if [row["steps"] for row in rows] != list(range(1, 9)):
        raise RuntimeError("committed progress is missing or duplicated")
    if initial["sa_unit_exists"] or any(pop["unit_exists"] for pop in initial["populations"].values()):
        raise RuntimeError("algorithm Units were created before their first actual use")
    if any(pop["unit_exists"] for row in rows[:3] for pop in row["populations"].values()):
        raise RuntimeError("a waiting population created its Unit prematurely")
    if rows[4]["stagnation"] != 1 or rows[4]["phase_after"] != "recovery":
        raise RuntimeError("recovery was not triggered by the declared stagnation metric")
    if rows[5]["sa_temperature"] != 0.4 or rows[5]["sa_current_score"] is None:
        raise RuntimeError("SA did not restart with an independently evaluated recovery baseline")
    if any(pop["members"] != 3 for pop in final["populations"].values()):
        raise RuntimeError("the two private populations did not retain their declared capacities")
    output = case["output"]
    if output["report"]["evaluation_count"] != final["evaluations"] or final["evaluations"] != 29:
        raise RuntimeError("formal and committed evaluation counts do not agree with the default plan")
    if not case["resource_usage"]["binding"]["current"]:
        raise RuntimeError("the effective Project L0 grant is not acknowledged")
    populations_at_intake = rows[3]["populations"]
    a_refs, b_refs = (populations_at_intake[name]["refs"] for name in ("population_a", "population_b"))
    # The installed proposals derive new identities; original allocations are
    # evidenced separately by each exact version's provenance in trace.json.
    if {ref["candidate_token"] for ref in a_refs} & {ref["candidate_token"] for ref in b_refs}:
        raise RuntimeError("the separately allocated population intakes share a proposal identity")
    allocations = {name: [item["metadata"]["solution_source_ref"] for item in population["provenance"]]
                   for name, population in populations_at_intake.items()}
    source_keys = [json.dumps(ref, sort_keys=True) for refs in allocations.values() for ref in refs]
    if len(source_keys) != 6 or len(set(source_keys)) != 6:
        raise RuntimeError("the two populations did not receive six disjoint exact source versions")
    increments, previous = [], 0
    for row in rows:
        increments.append(row["evaluations"] - previous)
        previous = row["evaluations"]
    return {
        "project_run_id": project["run_id"], "solver_run_id": trace["run_id"],
        "case_run_id": case["identity"]["case_run_id"], "status": case["status"],
        "logical_steps": final["steps"], "evaluations": final["evaluations"],
        "executed_phases": [row["executed_phase"] for row in rows],
        "phase_counts": dict(Counter(row["executed_phase"] for row in rows)),
        "evaluations_per_step": increments, "best_selection_objectives": output["best_objectives"],
        "best_candidate": output["best_solution"]["values"],
        "best_candidate_token": output["best_candidate_token"], "final_phase": final["phase_after"],
        "initial_source_allocations": allocations,
        "population_sizes": {name: pop["members"] for name, pop in final["populations"].items()},
        "prepared_candidate_count": rows[2]["prepared_count"], "initial_intake_quotas": [3, 3],
        "resource_binding_current": True, "resource_grant": case["resource_usage"]["authorized_grant"],
        "checks": ["正式结果与轨迹运行身份一致", "完整执行 preparing/search/recovery/return",
                   "等待阶段不创建种群 Unit", "按 raw metric 停滞后唤醒 SA",
                   "SA 重新加热并先评估起点", "两个私有种群保持各自容量",
                   "两群初始化提案身份不重叠", "正式求值数与提交轨迹一致", "L0 授权生效"],
    }


def write_report(summary):
    lines = ["# SA → 双种群 → SA 恢复 → 返回竞争：实际结果", "",
             f"Project run：`{summary['project_run_id']}`。", "",
             f"- 状态：`{summary['status']}`；逻辑提交 `{summary['logical_steps']}` 步，实际求值 `{summary['evaluations']}` 次。",
             f"- 执行阶段：`{summary['executed_phases']}`。",
             f"- 每步求值：`{summary['evaluations_per_step']}`。",
             f"- 最终选择目标：`{summary['best_selection_objectives']}`。",
             f"- 最终候选：`{summary['best_candidate']}`。",
             f"- 两个独立种群：`{summary['population_sizes']}`。", "",
             "本例故意从真实目标的平坦最优区域附近开始，以很小预算复现停滞触发。目标等于零不表示 SA 跳出了局部最优，也不构成算法效果比较。", "",
             "## 已执行的核对", "", *[f"- {check}。" for check in summary["checks"]], "",
             "## 原始文件", "", "- [汇总](results/summary.json)",
             "- [每次提交及精确成员引用/来源](results/trace.json)",
             "- [紧凑 CSV 轨迹](results/trace.csv)", "- [正式 Project 返回值](results/project_result.json)", "",
             "轨迹文件是观察报告，不冒充权威 Snapshot 或 Artifact 收据；完整运行存储位于本地 `.blackbase/`。", ""]
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
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````

## 26. [run_project.py](run_project.py)

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
