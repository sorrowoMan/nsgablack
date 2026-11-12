# 本项目代码全文（阅读快照）

生成日期：2026-10-19。本文件按当前真实源文件生成，用于集中审阅；修改程序应编辑对应源文件，源码是权威。每段保留源文件链接和原始字节的 SHA256，可核对快照是否已经过期。

包含本项目的全部 Python 文件、本地 Catalog TOML、Case 标记和忽略配置；标准脚手架的空包与 trainer 薄别名也完整保留，不意味着本次运行调用了这些别名。排除运行记录、results、缓存和未参与示例的模板。框架库的完整实现直接链接于 [COMPONENTS.md](COMPONENTS.md)，没有复制进本项目制造另一份实现。

本次共 32 个源文件／配置文件。实际运行结果见 [RESULTS.md](RESULTS.md)，装配与边界说明见 [README.md](README.md)。

## 文件索引

- 1. [.gitignore](.gitignore)
- 2. [_bootstrap.py](_bootstrap.py)
- 3. [cases/__init__.py](cases/__init__.py)
- 4. [cases/hybrid_search/.case](cases/hybrid_search/.case)
- 5. [cases/hybrid_search/__init__.py](cases/hybrid_search/__init__.py)
- 6. [cases/hybrid_search/adapter/__init__.py](cases/hybrid_search/adapter/__init__.py)
- 7. [cases/hybrid_search/adapter/composition.py](cases/hybrid_search/adapter/composition.py)
- 8. [cases/hybrid_search/bias/__init__.py](cases/hybrid_search/bias/__init__.py)
- 9. [cases/hybrid_search/bias/preference.py](cases/hybrid_search/bias/preference.py)
- 10. [cases/hybrid_search/build_solver.py](cases/hybrid_search/build_solver.py)
- 11. [cases/hybrid_search/build_trainer.py](cases/hybrid_search/build_trainer.py)
- 12. [cases/hybrid_search/catalog/entries/bias.toml](cases/hybrid_search/catalog/entries/bias.toml)
- 13. [cases/hybrid_search/catalog/entries/pipeline.toml](cases/hybrid_search/catalog/entries/pipeline.toml)
- 14. [cases/hybrid_search/catalog/entries/plugin.toml](cases/hybrid_search/catalog/entries/plugin.toml)
- 15. [cases/hybrid_search/catalog/entries/problem.toml](cases/hybrid_search/catalog/entries/problem.toml)
- 16. [cases/hybrid_search/config.py](cases/hybrid_search/config.py)
- 17. [cases/hybrid_search/evaluation/__init__.py](cases/hybrid_search/evaluation/__init__.py)
- 18. [cases/hybrid_search/pipeline/__init__.py](cases/hybrid_search/pipeline/__init__.py)
- 19. [cases/hybrid_search/pipeline/main.py](cases/hybrid_search/pipeline/main.py)
- 20. [cases/hybrid_search/pipeline/operators.py](cases/hybrid_search/pipeline/operators.py)
- 21. [cases/hybrid_search/pipeline/population.py](cases/hybrid_search/pipeline/population.py)
- 22. [cases/hybrid_search/plugins/__init__.py](cases/hybrid_search/plugins/__init__.py)
- 23. [cases/hybrid_search/plugins/trace.py](cases/hybrid_search/plugins/trace.py)
- 24. [cases/hybrid_search/problem/__init__.py](cases/hybrid_search/problem/__init__.py)
- 25. [cases/hybrid_search/problem/quadratic.py](cases/hybrid_search/problem/quadratic.py)
- 26. [cases/hybrid_search/run_solver.py](cases/hybrid_search/run_solver.py)
- 27. [cases/hybrid_search/run_trainer.py](cases/hybrid_search/run_trainer.py)
- 28. [cases/hybrid_search/runtime/__init__.py](cases/hybrid_search/runtime/__init__.py)
- 29. [cases/hybrid_search/solver/__init__.py](cases/hybrid_search/solver/__init__.py)
- 30. [project_config.py](project_config.py)
- 31. [run_and_report.py](run_and_report.py)
- 32. [run_project.py](run_project.py)

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

## 4. [cases/hybrid_search/.case](cases/hybrid_search/.case)

源文件 SHA256：`9f70b8a089f4a912b3db68708855604cbc02cb4bdb45b8e3880e4018c601cfa8`；3 行。

````text
name = hybrid_search
kind = solver
framework = nsgablack
````

## 5. [cases/hybrid_search/__init__.py](cases/hybrid_search/__init__.py)

源文件 SHA256：`01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b`；1 行。

````python

````

## 6. [cases/hybrid_search/adapter/__init__.py](cases/hybrid_search/adapter/__init__.py)

源文件 SHA256：`a765db0f006cc3ff2f3838e0dd6c55353973ec2c79d1b546a23633f5ae332095`；3 行。

````python
from .composition import build_adapter

__all__ = ["build_adapter"]
````

## 7. [cases/hybrid_search/adapter/composition.py](cases/hybrid_search/adapter/composition.py)

源文件 SHA256：`53e0d89bd4cf4c7c5bfac0e4a86c750ec7105df06d5a58fc5f3244b2483239a2`；39 行。

````python
"""用公开角色、池任务和操作绑定装配 GA → VNS → GA 返回竞争。"""
from nsgablack.adapters import (
    MultiStrategyConfig, NSGA2Adapter, PoolTaskSpec, RoleSpec,
    StrategyRouterAdapter, VNSAdapter, subpools,
)
from nsgablack.representation import ContextGaussianMutation, GaussianMutation, UniformInitializer
from nsgablack.units import UnitBinding
from ..pipeline.population import AgePopulationBuilder


def build_adapter(settings):
    ga = NSGA2Adapter(
        name="ga", population_size=settings.population_size, offspring_size=settings.population_size,
        initializer=UniformInitializer(-4.0, 4.0),
        mutator=GaussianMutation(sigma=settings.ga_sigma),
        unit_binding=UnitBinding(AgePopulationBuilder()),
    )
    vns = VNSAdapter(
        name="vns", batch_size=settings.local_batch, k_max=3,
        base_sigma=settings.vns_sigma, scale=1.5, max_sigma=0.8,
        restart_on_stagnation=False,
        mutator=ContextGaussianMutation(base_sigma=settings.vns_sigma),
    )
    local_steps = settings.population_size * settings.local_steps
    return StrategyRouterAdapter(
        name="ga_vns", roles=[
            RoleSpec("global", ga, pool_task=PoolTaskSpec(
                "refined", mode="compete", phases=("return",), count="all", shuffle=False)),
            # 每个成员单独精修；每项任务包含起点重新求值的一步。
            RoleSpec("refinement", vns, pool_task=PoolTaskSpec(
                subpools.all(ga), mode="refine", count="all",
                steps=settings.local_steps, output="refined", shuffle=False)),
        ], config=MultiStrategyConfig(
            # 提案上限，允许最后一次竞争读完整聚合池；不是种群或池容量。
            total_batch_size=settings.proposal_budget, adapt_weights=False,
            phase_schedule=(("ga", settings.ga_steps), ("vns", local_steps), ("return", 1)),
            phase_roles={"ga": ["global"], "vns": ["refinement"], "return": ["global"]},
        ),
    )
````

## 8. [cases/hybrid_search/bias/__init__.py](cases/hybrid_search/bias/__init__.py)

源文件 SHA256：`1a52059931d83bb979337f16fb8729c013b71d1b3e7238bfaf80f3037de0abad`；5 行。

````python

"""候选级软偏好。"""
from .preference import NegativeHalfPlaneBias, build_bias

__all__ = ["NegativeHalfPlaneBias", "build_bias"]
````

## 9. [cases/hybrid_search/bias/preference.py](cases/hybrid_search/bias/preference.py)

源文件 SHA256：`54a975c4e33d9c658455f7e9d82ab24e41980b240781ef5c1f7e59094a86056e`；26 行。

````python
"""软偏好单独定义；不修改原始目标、约束或候选。"""
import numpy as np

from nsgablack.bias import BiasModule, DomainBias


class NegativeHalfPlaneBias(DomainBias):
    objective_independent = True
    context_notes = "Penalizes negative x0 in the selection view; no context I/O."

    def __init__(self, weight=0.1):
        super().__init__(
            name="prefer_nonnegative_x0",
            weight=weight,
            mandatory=False,
            description="x0 < 0 时增加软惩罚；x0 >= 0 不加分、不扣分。",
        )

    def compute(self, x, context):
        return max(0.0, -float(np.asarray(x)[0]))


def build_bias():
    module = BiasModule()
    module.add(NegativeHalfPlaneBias(weight=0.1))
    return module
````

## 10. [cases/hybrid_search/build_solver.py](cases/hybrid_search/build_solver.py)

源文件 SHA256：`f42b4c24cbc9cc5abb0dced943c82dad702f29767663211bc6f2be5d02eeaab5`；27 行。

````python
"""唯一装配入口；Project 的 L0 授权通过 resource_context 传入。"""
from pathlib import Path
from nsgablack.core import ComposableSolver
from nsgablack.project import apply_solver_component_overrides
from .adapter import build_adapter
from .bias import build_bias
from .config import DemoConfig
from .pipeline import build_pipeline
from .plugins import build_plugin
from .problem import build_problem


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    overrides = dict(component_overrides or {})
    options = {**dict(config or {}), **dict(overrides.pop("config", {}))}
    settings = DemoConfig(**options)
    results = Path(__file__).resolve().parents[2] / "results"
    solver = ComposableSolver(
        problem=build_problem(), representation_pipeline=build_pipeline(),
        adapter=build_adapter(settings), bias_module=build_bias(),
        resource_context=resource_context, plugin_strict=True, snapshot_strict=True,
    )
    solver.set_random_seed(settings.seed)
    solver.set_max_steps(settings.max_steps)
    solver.add_plugin(build_plugin(output_dir=results, max_records=settings.max_steps))
    apply_solver_component_overrides(solver, overrides)
    return solver
````

## 11. [cases/hybrid_search/build_trainer.py](cases/hybrid_search/build_trainer.py)

源文件 SHA256：`99f765e75df055fdefa2b0a2bbdc035a77c5669466fcb9bbd15da6e21a2b468f`；1 行。

````python
from .build_solver import build_solver as build_trainer
````

## 12. [cases/hybrid_search/catalog/entries/bias.toml](cases/hybrid_search/catalog/entries/bias.toml)

源文件 SHA256：`e6b8865e2ebc4d79935c116f92f213c667d0315af1e8767065acbb1a6f78610d`；17 行。

````toml
[[entry]]
key = "project.bias.nonnegative_x0"
title = "NegativeHalfPlaneBias"
kind = "bias"
import_path = "bias.preference:NegativeHalfPlaneBias"
tags = ["project", "example", "bias", "candidate", "soft_preference"]
summary = "x0 < 0 时为选择目标增加 weight * (-x0)；保留原始目标与约束。"
context_requires = []
context_provides = []
context_mutates = []
context_cache = []
context_notes = ["只读当前候选并返回软评分，不改写候选、Unit 或共享 context。"]
use_when = ["观察原始求值与选择偏好如何分开记录时。"]
minimal_wiring = ["from cases.hybrid_search.bias import NegativeHalfPlaneBias", "module = BiasModule()", "module.add(NegativeHalfPlaneBias(weight=0.1))"]
required_companions = ["nsgablack.bias:BiasModule"]
config_keys = ["weight"]
example_entry = "cases.hybrid_search.build_solver:build_solver"
````

## 13. [cases/hybrid_search/catalog/entries/pipeline.toml](cases/hybrid_search/catalog/entries/pipeline.toml)

源文件 SHA256：`af103656b914826985327dcf967b0b6b344cab4c527b4d9ead18c8187ff22bd7`；53 行。

````toml
[[entry]]
key = "project.pipeline.box_repair"
title = "BoxRepair"
kind = "representation"
import_path = "pipeline.operators:BoxRepair"
tags = ["project", "example", "pipeline", "repair", "box"]
summary = "将候选投影到问题盒约束；只读 validate 不求值、不构建 Unit。"
context_requires = []
context_provides = []
context_mutates = []
context_cache = []
context_notes = ["仅处理候选值，不直接写共享 context；修复由正式控制路径调用。"]
use_when = ["为本例两个 Adapter 共享同一问题可行性修复时。"]
minimal_wiring = ["from cases.hybrid_search.pipeline import BoxRepair", "pipeline = RepresentationPipeline(repair=BoxRepair())"]
required_companions = ["nsgablack.representation:RepresentationPipeline"]
config_keys = ["low", "high"]
example_entry = "cases.hybrid_search.build_solver:build_solver"

[[entry]]
key = "project.unit.age_population_builder"
title = "AgePopulationBuilder"
kind = "representation"
import_path = "pipeline.population:AgePopulationBuilder"
tags = ["project", "example", "unit", "population", "builder", "codec"]
summary = "构建带成员年龄的兼容种群 Unit；复用标准数据 codec，构建按 Adapter 需要发生。"
context_requires = []
context_provides = []
context_mutates = []
context_cache = []
context_notes = ["无状态构建规则；不持有运行 Unit，不从 context 猜测算法所有者。"]
use_when = ["在不修改 NSGA-II 选择代码的情况下扩展成员字段时。"]
minimal_wiring = ["from cases.hybrid_search.pipeline import AgePopulationBuilder", "ga = NSGA2Adapter(unit_binding=UnitBinding(AgePopulationBuilder()))"]
required_companions = ["nsgablack.units:UnitBinding", "nsgablack.adapters:NSGA2Adapter"]
config_keys = []
example_entry = "cases.hybrid_search.build_solver:build_solver"

[[entry]]
key = "project.unit.age_population"
title = "AgePopulationUnit"
kind = "tool"
import_path = "pipeline.population:AgePopulationUnit"
tags = ["project", "example", "unit", "population", "members"]
summary = "member_age 表示成员连续存活的环境选择次数，按显式来源索引维护。"
context_requires = []
context_provides = []
context_mutates = []
context_cache = []
context_notes = ["维护所属 Adapter 的结构与行字段，不拥有 Solver 生命周期或共享 context。"]
use_when = ["阅读成员扩展字段如何随初始化、选择、替换和恢复对齐时。"]
minimal_wiring = ["from cases.hybrid_search.pipeline import AgePopulationBuilder", "binding = UnitBinding(AgePopulationBuilder())", "# Adapter calls the binding when its Unit is first needed."]
required_companions = ["project.unit.age_population_builder"]
config_keys = ["unit_id", "member_age"]
example_entry = "cases.hybrid_search.build_solver:build_solver"
````

## 14. [cases/hybrid_search/catalog/entries/plugin.toml](cases/hybrid_search/catalog/entries/plugin.toml)

源文件 SHA256：`d6bfbc9f556fcda63cbbfe7a95c983cbe614400d74ef8e24305a252344183b98`；17 行。

````toml
[[entry]]
key = "project.plugin.committed_trace"
title = "CommittedTracePlugin"
kind = "plugin"
import_path = "plugins.trace:CommittedTracePlugin"
tags = ["project", "example", "plugin", "observe", "committed", "lazy_unit"]
summary = "只观察已提交步骤与现存 Unit，使用显式 JSON 状态 codec 导出本例轨迹。"
context_requires = []
context_provides = []
context_mutates = []
context_cache = []
context_notes = ["读取正式 Solver/Adapter/Pool 表面，不调用 ensure_unit，不直接写 context。导出文件仅为观察报告。"]
use_when = ["核对 GA/VNS 按需建 Unit、阶段与计数的实际运行行为时。"]
minimal_wiring = ["from cases.hybrid_search.plugins import CommittedTracePlugin", "solver.add_plugin(CommittedTracePlugin(max_records=settings.max_steps))"]
required_companions = ["nsgablack.core:ComposableSolver"]
config_keys = ["max_records", "output_dir"]
example_entry = "cases.hybrid_search.build_solver:build_solver"
````

## 15. [cases/hybrid_search/catalog/entries/problem.toml](cases/hybrid_search/catalog/entries/problem.toml)

源文件 SHA256：`68b9751f85760d31e6a9b7872e445a76f1c178f711a71fd88453ff821681c256`；18 行。

````toml
# Case-local entries: portable paths are normalized to cases.hybrid_search.*.
[[entry]]
key = "project.problem.quadratic"
title = "QuadraticProblem"
kind = "tool"
import_path = "problem.quadratic:QuadraticProblem"
tags = ["project", "example", "problem", "quadratic", "box"]
summary = "二维盒约束二次目标；已知最优点为 [2, -1]，原始目标为 0。"
context_requires = []
context_provides = []
context_mutates = []
context_cache = []
context_notes = ["只定义目标和原始约束，不读取算法结构或改写共享 context。"]
use_when = ["逐项核对装配、候选交接与原始反馈时。"]
minimal_wiring = ["from cases.hybrid_search.problem import QuadraticProblem", "problem = QuadraticProblem()"]
required_companions = []
config_keys = []
example_entry = "cases.hybrid_search.build_solver:build_solver"
````

## 16. [cases/hybrid_search/config.py](cases/hybrid_search/config.py)

源文件 SHA256：`5243d606f2bd986f813de3381cf8a23f2769951ebe1f50a342d1d2162e33384c`；31 行。

````python
"""本 Case 的算法配置；池历史容量与这些参数无关。"""
from dataclasses import dataclass


@dataclass(frozen=True)
class DemoConfig:
    seed: int = 7
    population_size: int = 12
    ga_steps: int = 8
    local_steps: int = 6
    local_batch: int = 4
    ga_sigma: float = 0.45
    vns_sigma: float = 0.12

    def __post_init__(self):
        for name in ("population_size", "ga_steps", "local_steps", "local_batch"):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if self.population_size < 2 or self.ga_sigma <= 0 or self.vns_sigma <= 0:
            raise ValueError("population_size >= 2 and positive mutation scales are required")

    @property
    def max_steps(self):
        return self.ga_steps + self.population_size * self.local_steps + 1

    @property
    def proposal_budget(self):
        # 返回池最多含全部局部接纳提案，最后一次竞争不悄悄裁掉输入。
        return max(self.population_size,
                   self.population_size * (1 + (self.local_steps - 1) * self.local_batch))
````

## 17. [cases/hybrid_search/evaluation/__init__.py](cases/hybrid_search/evaluation/__init__.py)

源文件 SHA256：`01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b`；1 行。

````python

````

## 18. [cases/hybrid_search/pipeline/__init__.py](cases/hybrid_search/pipeline/__init__.py)

源文件 SHA256：`e58f567d9adcf13992d27f6e47489492f550ae5599079f1999740ef87a5644ad`；6 行。

````python
"""候选处理与 Unit 构建规则；装配这些规则不会创建运行中的 Unit。"""
from .main import build_pipeline
from .operators import BoxRepair
from .population import AgePopulationBuilder, AgePopulationUnit

__all__ = ["build_pipeline", "BoxRepair", "AgePopulationBuilder", "AgePopulationUnit"]
````

## 19. [cases/hybrid_search/pipeline/main.py](cases/hybrid_search/pipeline/main.py)

源文件 SHA256：`2d9418c58108f6f1286839e226e475bc8938edbe56a9d25023564fbd4704a0be`；8 行。

````python
"""所有 Adapter 共用的问题候选管线；行为组件另行绑定给实际所有者。"""
from nsgablack.representation import RepresentationPipeline

from .operators import BoxRepair


def build_pipeline():
    return RepresentationPipeline(repair=BoxRepair())
````

## 20. [cases/hybrid_search/pipeline/operators.py](cases/hybrid_search/pipeline/operators.py)

源文件 SHA256：`de356dc98a53aa011f434838c30989eaf919b2c1d7e0aa6653c1f77c2b99638c`；28 行。

````python
"""只处理问题可行性；不创建 Unit、不求值、不决定成员去留。"""
from dataclasses import dataclass
from typing import ClassVar

import numpy as np

from blackbase.representation import RepresentationCapabilities
from nsgablack.representation.base import RepresentationComponentContract
from nsgablack.units.contracts import candidate_array


@dataclass(frozen=True)
class BoxRepair(RepresentationComponentContract):
    low: float = -4.0
    high: float = 4.0
    representation_capabilities: ClassVar = RepresentationCapabilities(
        frozenset({"repair"}), repair_idempotent=True,
    )
    context_notes = "Clips each coordinate to the problem bounds; no context writes."

    def repair(self, candidate, context=None):
        return np.clip(candidate_array(candidate), self.low, self.high)

    def validate(self, candidate, context=None):
        # 只读检查；共同修复需要时可复用，不偷偷调用 Problem.evaluate。
        x = candidate_array(candidate)
        return bool(x.shape == (2,) and np.all(np.isfinite(x))
                    and np.all(x >= self.low) and np.all(x <= self.high))
````

## 21. [cases/hybrid_search/pipeline/population.py](cases/hybrid_search/pipeline/population.py)

源文件 SHA256：`81e51d84645681e9a5d72060ed5b155fee2ee7e5e1addfb4fe29b2a8600f1161`；38 行。

````python
"""扩展算法结构；NSGA-II 无需知道 member_age 如何维护。"""
from dataclasses import dataclass, field

import numpy as np

from nsgablack.representation import PopulationUnitBuilder
from nsgablack.units import PopulationUnit, UnitSchema


@dataclass
class AgePopulationUnit(PopulationUnit):
    member_age: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=int))
    member_fields = ("member_age",)
    schema = UnitSchema(
        "assembled_ga_vns.age_population",
        required_fields=(*PopulationUnit.schema.required_fields, "member_age"),
        candidate_projection=False,
    )

    def on_members_changed(self, change):
        # 年龄 = 此成员连续存活的环境选择次数。新成员为 0；局部替换
        # 不算整轮环境选择。按来源索引维护，数值相同也不猜身份。
        increment = int(change.operation == "selection")
        return {"member_age": np.asarray([
            0 if previous is None else self.member_age[previous] + increment
            for previous in change.previous_member_indices
        ], dtype=int)}

    def validate(self):
        super().validate()
        if self.member_age.dtype.kind not in "iu" or np.any(self.member_age < 0):
            raise ValueError("member_age must contain nonnegative integers")


class AgePopulationBuilder(PopulationUnitBuilder):
    # 继承标准纯数据 codec；恢复只恢复字段，不重跑构建。
    unit_type = AgePopulationUnit
    compatible_schemas = (PopulationUnit.schema,)
````

## 22. [cases/hybrid_search/plugins/__init__.py](cases/hybrid_search/plugins/__init__.py)

源文件 SHA256：`03f23dae42726c63cfda40d96a2214867eefb39a7685a3f60aa395e66841d734`；4 行。

````python

from .trace import CommittedTracePlugin, build_plugin

__all__ = ["CommittedTracePlugin", "build_plugin"]
````

## 23. [cases/hybrid_search/plugins/trace.py](cases/hybrid_search/plugins/trace.py)

源文件 SHA256：`7bbc4907522daa551f1c1a702bb237afa2d5c0443d69da8c78da8a77327a390b`；195 行。

````python
"""只观察已提交步骤；最终发布后导出观测 JSON/CSV，不修改搜索或 context。"""
from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping
from pathlib import Path

from blackbase.participation import ParticipationContract
from nsgablack.plugins.base import Plugin
from nsgablack.utils.engineering.file_io import atomic_write_text


def _data_copy(value):
    """本组件的状态仅含有限 JSON 数据，不复制 Solver/Adapter 对象图。"""
    return json.loads(json.dumps(value, allow_nan=False))


class CommittedTracePlugin(Plugin):
    """小示例的轻量标量轨迹；不持有另一份 Adapter 或候选状态。"""

    participation = ParticipationContract()
    state_recovery_level = "L1"
    state_recovery_notes = "Explicit JSON codec for bounded committed observations."
    context_notes = ("Observes committed state without constructing a Unit.",)

    def __init__(self, *, max_records=128, output_dir=None):
        super().__init__(name="committed_trace")
        if type(max_records) is not int or max_records < 1:
            raise ValueError("max_records must be a positive integer")
        self.max_records = max_records
        self.output_dir = None if output_dir is None else Path(output_dir)
        self.run_id = None
        self.initial = None
        self.records = []
        self.final_summary = None
        self._started = None

    def _observe(self, *, include_operations=False):
        solver = self.solver
        root = solver.adapter
        pool = solver.solution_pool
        units = []
        operations = []

        def visit(adapter, path):
            # 只读取已有 Unit，绝不调用 ensure_unit 或 UnitBuilder。
            structure = getattr(adapter, "algorithm_unit", None)
            current = getattr(adapter, "current_unit", None)
            neighborhood = getattr(adapter, "neighborhood_unit", None)
            members = getattr(structure, "population", None)
            ages = getattr(structure, "member_age", None)
            member_age = [] if ages is None else [int(age) for age in ages]
            views = pool.subpools_created_by(path)
            units.append({
                "path": "/".join(path),
                "type": type(adapter).__name__,
                "structure_exists": structure is not None,
                "current_exists": current is not None,
                "neighborhood_exists": neighborhood is not None,
                "population_members": 0 if members is None else len(members),
                "member_age": member_age,
                "member_age_min": min(member_age, default=None),
                "member_age_max": max(member_age, default=None),
                "published_views": len(views),
                "published_view_members": sum(len(pool.subpool_refs(name)) for name in views),
            })
            if include_operations:
                operations.append({
                    "path": "/".join(path), "type": type(adapter).__name__,
                    "operations": _data_copy(adapter.get_operation_contract()),
                })
            # 正式所有权树；路径规则与 subpools 的实例来源寻址一致。
            for index, child in enumerate(adapter.step_transaction_children()):
                visit(child, (*path, f"{index}:{child.name}"))

        visit(root, (root.name,))
        projection = root.get_runtime_context_projection(solver)
        incumbent = solver.get_incumbent()
        authority = solver.population_authority
        handle = authority.snapshot_handle
        observation = {
            "logical_steps": int(solver.run_progress_steps),
            "evaluations": int(solver.evaluation_count),
            "phase": str(projection.get("phase", "unassigned")),
            "pool_records": int(pool.record_count),
            "pool_sequence": int(pool.timestamp.sequence),
            "authority_generation": authority.snapshot_generation,
            "authority_key": None if handle is None else str(handle.key),
            "best_score": None if incumbent is None else float(incumbent.score),
            "units": units,
        }
        if include_operations:
            observation["operation_contracts"] = operations
        return observation

    def on_solver_init(self, solver):
        run_id = solver.run_session.run_id
        if self.run_id != run_id:
            self.records = []
            self.final_summary = None
            self.initial = None
        self.run_id = run_id
        if self.initial is None:
            self.initial = self._observe(include_operations=True)
        self._started = None

    def on_generation_start(self, generation):
        # 该 hook 在提交之后调用，不能当作算法执行前的状态。
        self._started = (int(generation), self._observe())

    def on_generation_committed(self, generation, outcome):
        if not bool(outcome.get("committed", False)):
            raise ValueError("committed hook requires a committed outcome")
        row = self._observe()
        if self._started != (int(generation), row):
            raise RuntimeError("committed lifecycle observations disagree")
        if len(self.records) >= self.max_records:
            raise RuntimeError("example trace capacity exhausted")
        self.records.append({"generation": int(generation), **row})
        self._started = None

    def on_solver_finalized(self, result):
        # 此时结果已发布；不在 finishing 阶段提前宣称成功。
        self.final_summary = self._observe()
        if self.output_dir is None:
            return
        incumbent = self.solver.get_incumbent()
        best = None if incumbent is None else {
            "candidate": incumbent.candidate.tolist(),
            "selection_objectives": incumbent.objectives.tolist(),
            "selection_constraint_violation": float(incumbent.constraint_violation),
            "selection_score": float(incumbent.score),
            "candidate_token": incumbent.candidate_token,
        }
        # 观测文件，不声明为带权威发布收据的 Artifact。
        payload = {**self.get_state(), "final_incumbent": best}
        atomic_write_text(self.output_dir / "trace.json",
                          json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False))
        columns = ("generation", "logical_steps", "evaluations", "phase", "best_score",
                   "pool_records", "pool_sequence", "authority_generation", "authority_key",
                   "ga_structure_exists", "ga_member_age_min", "ga_member_age_max",
                   "vns_current_exists", "vns_neighborhood_exists")
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for record in self.records:
            row = {key: record[key] for key in columns if key in record}
            units = record["units"]
            row["ga_structure_exists"] = any(unit["type"] == "NSGA2Adapter" and
                                               unit["structure_exists"] for unit in units)
            ga = next((unit for unit in units if unit["type"] == "NSGA2Adapter"), None)
            row["ga_member_age_min"] = None if ga is None else ga["member_age_min"]
            row["ga_member_age_max"] = None if ga is None else ga["member_age_max"]
            row["vns_current_exists"] = any(unit["type"] == "VNSAdapter" and
                                              unit["current_exists"] for unit in units)
            row["vns_neighborhood_exists"] = any(unit["type"] == "VNSAdapter" and
                                                   unit["neighborhood_exists"] for unit in units)
            writer.writerow(row)
        atomic_write_text(self.output_dir / "trace.csv", stream.getvalue())

    def get_state(self):
        return _data_copy({
            "schema": "assembled_ga_vns.committed_trace/v1",
            "max_records": self.max_records,
            "run_id": self.run_id,
            "initial": self.initial,
            "records": self.records,
            "final_summary": self.final_summary,
        })

    def set_state(self, state):
        if not isinstance(state, Mapping):
            raise TypeError("trace state must be a Mapping")
        saved = _data_copy(dict(state))
        if saved.get("schema") != "assembled_ga_vns.committed_trace/v1":
            raise ValueError("unsupported trace state schema")
        if saved.get("max_records") != self.max_records:
            raise ValueError("trace capacity differs from checkpoint")
        records = saved.get("records")
        if not isinstance(records, list) or len(records) > self.max_records:
            raise ValueError("invalid trace records")
        if any(not isinstance(row, dict) or type(row.get("generation")) is not int
               or row["generation"] < 0 for row in records):
            raise ValueError("invalid committed generation record")
        self.run_id = saved["run_id"]
        self.initial = saved["initial"]
        self.records = records
        self.final_summary = saved["final_summary"]
        self._started = None


def build_plugin(*, output_dir=None, max_records=128):
    return CommittedTracePlugin(output_dir=output_dir, max_records=max_records)
````

## 24. [cases/hybrid_search/problem/__init__.py](cases/hybrid_search/problem/__init__.py)

源文件 SHA256：`cc23a71194d3b96f65eeada6fe6f2b7b69086f31567daaebce6bd929d65162e3`；9 行。

````python
"""本 Case 的问题定义与工厂。"""
from .quadratic import QuadraticProblem


def build_problem():
    return QuadraticProblem()


__all__ = ["QuadraticProblem", "build_problem"]
````

## 25. [cases/hybrid_search/problem/quadratic.py](cases/hybrid_search/problem/quadratic.py)

源文件 SHA256：`71fb5ac9b6508eab7a7d3074005eb319cd4ddb50909f17874d2ee2aa43dca9d9`；30 行。

````python
"""二维盒约束问题；原始目标与算法、偏好无关。"""
from __future__ import annotations

import numpy as np

from nsgablack.core import BlackBoxProblem
from nsgablack.units.contracts import candidate_array


class QuadraticProblem(BlackBoxProblem):
    """已知最优点 (2, -1)，原始最优目标为 0。"""

    optimum = (2.0, -1.0)

    def __init__(self):
        super().__init__(
            name="带盒约束的二维二次函数",
            dimension=2,
            objectives=["minimize"],
            bounds={"x0": (-4.0, 4.0), "x1": (-4.0, 4.0)},
        )

    def evaluate(self, candidate):
        x = candidate_array(candidate)
        return float((x[0] - 2.0) ** 2 + (x[1] + 1.0) ** 2)

    def evaluate_constraints(self, candidate):
        # 显式记录原始违反量；ProblemRepair 不替代可行性含义。
        x = np.asarray(candidate, dtype=float)
        return np.maximum(-4.0 - x, 0.0) + np.maximum(x - 4.0, 0.0)
````

## 26. [cases/hybrid_search/run_solver.py](cases/hybrid_search/run_solver.py)

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

## 27. [cases/hybrid_search/run_trainer.py](cases/hybrid_search/run_trainer.py)

源文件 SHA256：`baa1ed97eb52ac800e55abd523a65bf3345d0f0792bcd088d1d04e35eab52fdb`；4 行。

````python
from .run_solver import main

if __name__ == "__main__":
    raise SystemExit(main())
````

## 28. [cases/hybrid_search/runtime/__init__.py](cases/hybrid_search/runtime/__init__.py)

源文件 SHA256：`01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b`；1 行。

````python

````

## 29. [cases/hybrid_search/solver/__init__.py](cases/hybrid_search/solver/__init__.py)

源文件 SHA256：`01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b`；1 行。

````python

````

## 30. [project_config.py](project_config.py)

源文件 SHA256：`0d36a26a51480ab1e291929b1fc66d0593c5d52080ade9b223c228ea019ff2ec`；11 行。

````python
"""Project 管跨 Case 执行及唯一 L0 授权；算法阶段位于 Case 的 Adapter。"""
L0 = {
    "namespace": "assembled_ga_vns",
    "offer": {"threads": 1, "gpus": 0, "backend": "local", "device_tokens": []},
    "policy": {"mode": "strict", "gpu_sharing": "exclusive", "cpu_oversubscribe": False},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto", "execution_backend": "local",
}
STAGES = [{"name": "search", "cases": ["hybrid_search"], "policy": "serial",
           "resource_requests": {"hybrid_search": {"threads": 1, "gpus": 0, "backend": "local"}}}]
GROUPS = {"default": {"stages": ["search"]}}
````

## 31. [run_and_report.py](run_and_report.py)

源文件 SHA256：`d9a4ec7e733057ffd35fba38254b91fd3c0bb4e0dedd33219aedac8750272dc8`；162 行。

````python
"""调用正式 Project runner；只对返回值与提交轨迹整理教学报告。"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict
from pathlib import Path

from _bootstrap import bootstrap

bootstrap()
from nsgablack.project.project_runner import execute_project
from nsgablack.utils.engineering.file_io import atomic_write_text
from cases.hybrid_search.config import DemoConfig
from cases.hybrid_search.problem import build_problem

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"


def write_json(path, value):
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))


def unit(record, class_name):
    return next(item for item in record["units"] if item["type"] == class_name)


def summarize(project, trace):
    """交叉核对正式结果与本例观测；不据观察值改写框架状态。"""
    settings = DemoConfig()
    if project["exit_code"] != 0 or len(project["cases"]) != 1:
        raise RuntimeError("Project did not produce one successful Case")
    case = project["cases"][0]
    if not case["ok"]:
        raise RuntimeError(f"Case failed: {case['failure']}")
    case_id = case["identity"]["case_run_id"]
    if not trace["run_id"].startswith(case_id + ":solver-run:"):
        raise RuntimeError("trace belongs to another run; refusing a stale report")
    initial, records, final = trace["initial"], trace["records"], trace["final_summary"]
    expected = (["ga"] * settings.ga_steps
                + ["vns"] * (settings.population_size * settings.local_steps) + ["return"])
    if [item["phase"] for item in records] != expected:
        raise RuntimeError("committed phase order differs from the assembled schedule")
    if [item["logical_steps"] for item in records] != list(range(1, settings.max_steps + 1)):
        raise RuntimeError("committed progress contains a gap or duplicate")
    if any(item["structure_exists"] or item["current_exists"] or item["neighborhood_exists"]
           for item in initial["units"]):
        raise RuntimeError("a Unit was created before the first search operation")
    if any(unit(item, "VNSAdapter")["current_exists"]
           or unit(item, "VNSAdapter")["neighborhood_exists"]
           for item in records[:settings.ga_steps]):
        raise RuntimeError("inactive VNS created a Unit during the GA phase")
    first_vns = unit(records[settings.ga_steps], "VNSAdapter")
    if not first_vns["current_exists"] or not first_vns["neighborhood_exists"]:
        raise RuntimeError("VNS did not create its required Units on first activation")
    ga, vns = unit(final, "NSGA2Adapter"), unit(final, "VNSAdapter")
    if ga["population_members"] != settings.population_size or len(ga["member_age"]) != settings.population_size:
        raise RuntimeError("final GA member fields are misaligned")
    if vns["published_views"] != settings.population_size or vns["published_view_members"] != settings.population_size:
        raise RuntimeError("not every VNS member task published its selected result")
    formal, best = case["output"], trace["final_incumbent"]
    if formal["best_candidate_token"] != best["candidate_token"]:
        raise RuntimeError("formal result and observed incumbent have different identities")
    if formal["best_objectives"] != best["selection_objectives"]:
        raise RuntimeError("formal result and observed selection feedback disagree")
    if formal["report"]["evaluation_count"] != final["evaluations"]:
        raise RuntimeError("formal result and committed evaluation counter disagree")
    # 仅独立核对解析函数；不是从记录里恢复 raw evidence，也不计入求解求值次数。
    raw_recomputed = float(build_problem().evaluate(best["candidate"]))
    penalty = 0.1 * max(0.0, -best["candidate"][0])
    if not math.isclose(raw_recomputed + penalty, best["selection_score"], rel_tol=1e-12, abs_tol=1e-14):
        raise RuntimeError("analytical objective plus declared preference disagrees with selection score")
    if not all(-4.0 <= value <= 4.0 for value in best["candidate"]):
        raise RuntimeError("final candidate violates the declared problem bounds")
    binding = case["resource_usage"]["binding"]
    if not binding["current"]:
        raise RuntimeError("Case did not acknowledge the effective Project resource grant")
    phases, previous_evaluations = [], 0
    for name in ("ga", "vns", "return"):
        rows = [item for item in records if item["phase"] == name]
        last = rows[-1]
        phases.append({"phase": name, "committed_steps": len(rows),
                       "evaluations": last["evaluations"] - previous_evaluations,
                       "best_selection_score": last["best_score"]})
        previous_evaluations = last["evaluations"]
    return {
        "project_run_id": project["run_id"], "case_run_id": case_id,
        "solver_run_id": trace["run_id"], "status": case["status"],
        "config": asdict(settings), "logical_steps": final["logical_steps"],
        "evaluations": final["evaluations"], "phases": phases, "best": best,
        "raw_objective_recomputed": raw_recomputed,
        "raw_recomputation_note": "Independent analytical check, not persisted raw evidence or another solver evaluation.",
        "known_optimum": [2.0, -1.0], "known_optimal_objective": 0.0,
        "distance_to_known_optimum": math.dist(best["candidate"], [2.0, -1.0]),
        "final_ga_members": ga["population_members"], "final_member_age": ga["member_age"],
        "ga_phase_end_member_age": unit(records[settings.ga_steps - 1], "NSGA2Adapter")["member_age"],
        "vns_result_views": vns["published_views"],
        "pool_batch_records": final["pool_records"],
        "resource_binding_current": binding["current"],
        "resource_grant": case["resource_usage"]["authorized_grant"],
        "case_elapsed_seconds": case["elapsed_seconds"],
        "checks": ["正式结果与轨迹属于同一次运行", "81 步阶段顺序与提交计数一致",
                   "VNS 未启用时无 Unit，首次启用时创建所需 Unit", "12 个成员年龄字段仍与种群对齐",
                   "12 个 VNS 任务发布最终选择视图", "正式结果与轨迹的候选 token 和选择目标一致",
                   "解析目标加软偏好与选择分数一致", "最终候选符合问题边界", "Project L0 授权绑定已生效"],
    }


def write_report(summary):
    lines = ["# GA → VNS → GA 实际运行结果", "",
             f"Project run：`{summary['project_run_id']}`。固定随机种子为 7。", "",
             f"- 最终候选：`{summary['best']['candidate']}`。",
             f"- 选择目标：`{summary['best']['selection_score']:.12g}`。",
             f"- 独立重算原始目标：`{summary['raw_objective_recomputed']:.12g}`。",
             f"- 已知最优点：`[2, -1]`，最优目标：`0`；距离最优点 `{summary['distance_to_known_optimum']:.8g}`。",
             f"- 共 `{summary['logical_steps']}` 次逻辑提交、`{summary['evaluations']}` 次实际求值。", "",
             "原始目标重算是报告阶段的解析核对，不冒充持久证据，也不计入求解求值预算。", "",
             "## 分阶段对账", ""]
    for phase in summary["phases"]:
        lines.append(f"- `{phase['phase']}`：{phase['committed_steps']} 步，{phase['evaluations']} 次求值，阶段末最好选择分数 `{phase['best_selection_score']:.12g}`。")
    lines += ["", "VNS 的 252 次求值包含 12 个起点和 240 个邻域提案；返回 GA 时再评估 252 个接纳提案。",
              "`refined` 保存途中接纳提案，不等同于 12 个任务最终选择；最终选择另发布为 12 个 VNS 结果视图。", "",
              "## Unit 与交接核对", ""]
    lines += [f"- {check}。" for check in summary["checks"]]
    lines += [f"- GA 阶段结束的成员年龄：`{summary['ga_phase_end_member_age']}`。",
              f"- 最终 GA 成员年龄：`{summary['final_member_age']}`。", "",
              "GA 阶段已有成员连续存活 5 次环境选择；最终成员年龄全部为 0 是本次返回竞争的结果，不代表字段未被维护。", "",
              "## 原始文件", "",
              "- [精简结果与核对项](results/summary.json)",
              "- [每个提交步骤的 CSV](results/trace.csv)",
              "- [Unit、来源路径与实际算子绑定](results/trace.json)",
              "- [正式 Project 返回值与 Artifact 收据](results/project_result.json)", "",
              "轨迹是观察报告，不替代权威快照或 Artifact 发布收据。`.blackbase/` 保存本次 Project 执行记录与归档；报告没有内联完整求值证据，跨机器复制还需搬运各引用对应的数据。",
              "单次简单问题运行用于核对装配与数据交接，不构成算法性能比较。", ""]
    atomic_write_text(ROOT / "RESULTS.md", "\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-only", action="store_true", help="仅核对并整理上次正式运行的文件")
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
                      "evaluations": summary["evaluations"], "best": summary["best"]["candidate"],
                      "selection_score": summary["best"]["selection_score"],
                      "report": str(ROOT / "RESULTS.md")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````

## 32. [run_project.py](run_project.py)

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
