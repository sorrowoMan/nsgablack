# -*- coding: utf-8 -*-
"""Project scaffolding."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from typing import Dict


_FOLDERS = [
    "catalog",
    "problem",
    "pipeline",
    "bias",
    "adapter",
    "plugins",
    "data",
    "assets",
]


_FOLDER_DESCRIPTIONS: Dict[str, str] = {
    "catalog": "Project-local catalog index: register discoverable local components.",
    "problem": "Problem layer: objective, constraints, variable dimension and bounds.",
    "pipeline": "Representation layer: initializer, mutation, repair, encode/decode.",
    "bias": "Bias layer: soft preference and search tendency.",
    "adapter": "Strategy layer: propose/update orchestration.",
    "plugins": "Engineering layer: logging, parallelism, replay, visualization.",
    "data": "Input data layer: raw and processed project data.",
    "assets": "Output artifacts: charts, reports, exported files.",
}


def _write_file(path: Path, content: str, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        return
    path.write_text(content, encoding="utf-8")


def _readme_for_folder(name: str) -> str:
    desc = _FOLDER_DESCRIPTIONS.get(name, "Module directory.")
    desc_cn = {
        "catalog": "项目本地 catalog 索引：注册可发现的本地组件。",
        "problem": "问题层：目标、约束、变量维度与边界。",
        "pipeline": "表示层：初始化、变异、修复、编码/解码。",
        "bias": "偏置层：软偏好与搜索倾向。",
        "adapter": "策略层：propose/update 协调。",
        "plugins": "工程层：日志、并行、回放、可视化等运行能力。",
        "data": "数据层：项目原始与处理后的数据。",
        "assets": "产出物：图表、报告、导出文件。",
    }.get(name, "模块目录。")
    return dedent(
        f"""\
        # {name}

        **中文**
        - 职责：{{desc_cn}}
        - 边界：只保留本层关切，不在此处隐藏跨层逻辑。
        - I/O 约定：
          - 输入：数据源、参数、读取的 context 字段
          - 输出：返回对象、写入的 context 字段、副作用
          - 如使用 context，请声明
            `context_requires/context_provides/context_mutates/context_cache`。
        - 最小示例：保留一个可运行文件，或说明入口路径。

        **English**
        - Responsibility: {{desc}}
        - Boundary: keep only this layer's concern; do not hide cross-layer logic here.
        - I/O contract:
          - Input: data source, parameters, context fields read
          - Output: returned objects, context fields written, side effects
          - If context is used, declare
            `context_requires/context_provides/context_mutates/context_cache`.
        - Minimal example: keep one runnable file, or document the entry path.
        """
    )


def _root_readme(project_name: str) -> str:
    return dedent(
        f"""        # {project_name}

        NSGABlack scaffold project.

        ## Start Here (2 files only)
        - Read `START_HERE.md` first (stage-gate workflow).
        - Keep `BUILD_SOLVER_REGISTRATION.md` open while wiring `build_solver.py`.

        ## Structure
        - `problem/`: problem semantics
        - `pipeline/`: representation + hard-constraint repair
        - `bias/`: soft preferences
        - `adapter/`: strategy orchestration (optional)
        - `plugins/`: engineering/runtime capabilities (optional)
        - `data/`: input data
        - `assets/`: output artifacts

        ## Recommended Flow
        1. Run `python -m nsgablack project doctor --path . --build`
        2. Complete stage gates in `START_HERE.md`
        3. Wire `build_solver.py` by registration zones
        4. Register metadata in `project_registry.py` / `catalog/entries.toml`

        ## Entry Files
        - `build_solver.py`: standard assembly entry with explicit registration zones
        - `BUILD_SOLVER_REGISTRATION.md`: zone mapping + what belongs where
        - `project_registry.py`: local catalog registry
        - `COMPONENT_REGISTRATION.md`: registration metadata contract
        """
    )

def _start_here() -> str:
    return dedent(
        """        # START_HERE

        If you only read one file, read this one.
        如果只读一个文件，就读这个。

        ## Stage Gate 0 - Health Baseline
        Run first:
        ```powershell
        python -m nsgablack project doctor --path . --build
        ```
        Pass criteria:
        - Scaffold exists and doctor output is understandable.
        - No unresolved structure errors before wiring.

        ## Stage Gate 1 - Problem Semantics
        File: `problem/example_problem.py`
        Deliverable:
        - `evaluate(x)` returns objective vector (`numpy.ndarray`).
        - `evaluate_constraints(x)` returns violation vector.
        Pass criteria:
        - Problem file contains only business semantics.
        - No repair logic, no plugin logic, no strategy logic.

        ## Stage Gate 2 - Layer Placement (Most Important)
        Split requirements into layers:
        - Problem: semantics only
        - Pipeline: init/mutate/repair/encode/decode
        - Bias: soft preference only
        - Solver/Adapter: search strategy and orchestration
        - Plugin: observability/engineering/runtime capability
        Pass criteria:
        - Each requirement is placed in one layer only.
        - Any cross-layer decision has an explicit reason.

        ## Stage Gate 3 - Catalog Candidate Review
        Search components:
        ```powershell
        python -m nsgablack project catalog search <keyword> --path . --global
        ```
        For each candidate, record:
        - Why choose
        - Why not choose alternatives
        - Expected input/output shape
        - Dependency and state behavior

        ## Stage Gate 4 - Assembly Wiring
        File: `build_solver.py`
        Wire by zone order:
        1) problem
        2) pipeline
        3) bias
        4) solver core
        5) acceleration backends (L0)
        6) evaluation runtime (L4)
        7) observability plugins
        8) project plugins
        9) optional checkpoint
        Pass criteria:
        - Assembly is explicit and traceable.
        - No hidden side effects.

        ## Stage Gate 5 - Registration & Discoverability
        Register metadata:
        - `project_registry.py`
        - `catalog/entries.toml`
        Pass criteria:
        - Teammates can understand what each component does from metadata only.

        ## Stage Gate 6 - Contract Verification
        Run:
        ```powershell
        python -m nsgablack project doctor --path . --build --strict
        python -m nsgablack project catalog list --path .
        ```
        Pass criteria:
        - Context/snapshot/shape checks pass.
        - Errors can be explained and fixed by file + line.

        ## Stage Gate 7 - Evidence Loop
        Run minimal experiment:
        ```powershell
        python build_solver.py
        ```
        Optional inspection:
        ```powershell
        python -m nsgablack run_inspector --entry build_solver.py:build_solver
        ```
        Pass criteria:
        - New user can reproduce run and explain why this composition works.
        """
    )


def _component_registration_guide() -> str:
    return dedent(
        """        # COMPONENT_REGISTRATION

        组件注册说明
        This file defines the local project registration contract.

        ## 为什么要注册组件 / Why register components
        - 供 Catalog 与 Run Inspector 发现与审计
        - 统一 `build_solver.py` 与 `project_registry.py` 的入口
        - 让 context I/O 更可追踪

        ## 需要注册什么 / What should be registered
        - problem builders
        - pipelines / biases / adapters / plugins
        - solver assembly entries

        原则：仅登记可复用或可发现的组件；实验草稿不必登记。

        ## 在哪里注册 / Where to register
        - Local project entries: `project_registry.py`
        - Catalog key 统一使用 `project.` 前缀

        ## 最小条目契约 / Minimal entry contract
        Each `CatalogEntry` should include:
        - `key`, `kind`, `title`, `import_path`
        - `tags`, `summary`
        - `context_requires`, `context_provides`, `context_mutates`, `context_cache`
        - `use_when`, `minimal_wiring`, `required_companions`, `config_keys`, `example_entry`

        context 若无任何使用，允许为空 `()` 并在 `context_notes` 说明。

        ## 校验 / Validation
        ```powershell
        python -m nsgablack project doctor --path . --build --strict
        python -m nsgablack project catalog list --path .
        python tools/catalog_integrity_checker.py --check-usage --strict-usage --check-context --context-kinds plugin --require-context-notes --strict-context
        ```

        ## UI Scope
        - `Scope=project`: local components
        - `Scope=framework`: framework built-in components
        - `Scope=all`: merged view
        """
    )


def _component_contract_template() -> str:
    return dedent(
        """\
        # Component Contract Card Template

        Use this card for every project component (adapter/pipeline/bias/plugin).

        ## 1. Identity
        - Component key:
        - Kind:
        - Source path:
        - Owner:

        ## 2. Responsibility
        - What this component must do:
        - What this component must NOT do:

        ## 3. I/O Contract
        - Input shape/types:
        - Output shape/types:
        - Side effects:

        ## 4. Context Contract
        - context_requires:
        - context_provides:
        - context_mutates:
        - context_cache:
        - context_notes:

        ## 5. Recovery Contract
        - Implements get_state/set_state: yes/no
        - state_recovery_level: L0/L1/L2
        - Recovery boundary notes:

        ## 6. Mode Boundary
        - Prove mode boundary (if any):
        - Heuristic mode boundary (if any):

        ## 7. Stop Condition
        - Explicit stop/short-circuit behavior:
        """
    )


def _component_test_matrix_readme() -> str:
    return dedent(
        """\
        # Component Test Matrix Templates

        Copy one template per new component and rename to `tests/test_<component>_<kind>.py`.

        Required matrix (minimum):
        1. smoke
        2. contract
        3. checkpoint_roundtrip
        4. strict_fault
        """
    )


def _smoke_test_template() -> str:
    return dedent(
        """\
        \"\"\"Template: smoke test for a new component.\"\"\"

        import pytest


        def test_component_smoke_template():
            pytest.skip("Copy this template, rename to tests/test_<component>_smoke.py, then implement.")
        """
    )


def _contract_test_template() -> str:
    return dedent(
        """\
        \"\"\"Template: contract behavior test for a new component.\"\"\"

        import pytest


        def test_component_contract_template():
            pytest.skip("Validate propose/update or hook I/O contract and context flow.")
        """
    )


def _checkpoint_roundtrip_test_template() -> str:
    return dedent(
        """\
        \"\"\"Template: checkpoint roundtrip test for a new component.\"\"\"

        import pytest


        def test_component_checkpoint_roundtrip_template():
            pytest.skip("Validate get_state -> set_state roundtrip at declared recovery level.")
        """
    )


def _strict_fault_test_template() -> str:
    return dedent(
        """\
        \"\"\"Template: strict/fault test for a new component.\"\"\"

        import pytest


        def test_component_strict_fault_template():
            pytest.skip("Validate strict mode + fault path behavior.")
        """
    )


def _problem_template() -> str:
    return dedent(
        """\
        # -*- coding: utf-8 -*-
        \"\"\"Example problem: simple two-objective continuous optimization.\"\"\"

        from __future__ import annotations

        import numpy as np

        from nsgablack.core.base import BlackBoxProblem


        class ExampleProblem(BlackBoxProblem):
            def __init__(self, dimension: int = 8) -> None:
                bounds = {f"x{i}": [-5.0, 5.0] for i in range(dimension)}
                super().__init__(
                    name="ExampleProblem",
                    dimension=dimension,
                    bounds=bounds,
                    objectives=["sphere", "l1"],
                )

            def evaluate(self, x: np.ndarray) -> np.ndarray:
                arr = np.asarray(x, dtype=float).reshape(-1)
                f1 = float(np.sum(arr ** 2))
                f2 = float(np.sum(np.abs(arr)))
                return np.array([f1, f2], dtype=float)

            def evaluate_constraints(self, x: np.ndarray) -> np.ndarray:
                # No hard constraints in this minimal example.
                return np.zeros(0, dtype=float)
        """
    )


def _problem_class_template() -> str:
    return dedent(
        """\
        # -*- coding: utf-8 -*-
        \"\"\"问题模板：复制后改文件名和类名即可开始建模。\"\"\"

        from __future__ import annotations

        import numpy as np

        from nsgablack.core.base import BlackBoxProblem


        class ProblemTemplate(BlackBoxProblem):
            \"\"\"最小可运行的问题模板。\"\"\"

            def __init__(self, dimension: int = 8) -> None:
                # 变量边界：这里默认每个维度都在 [-5, 5]
                bounds = {f"x{i}": [-5.0, 5.0] for i in range(dimension)}
                super().__init__(
                    name="ProblemTemplate",
                    dimension=dimension,
                    bounds=bounds,
                    objectives=["obj_0", "obj_1"],
                )

            def evaluate(self, x: np.ndarray) -> np.ndarray:
                # 目标函数示例：f1=平方和，f2=绝对值和
                arr = np.asarray(x, dtype=float).reshape(-1)
                obj_0 = float(np.sum(arr ** 2))
                obj_1 = float(np.sum(np.abs(arr)))
                return np.array([obj_0, obj_1], dtype=float)

            def evaluate_constraints(self, x: np.ndarray) -> np.ndarray:
                # 约束示例：默认无硬约束，返回空向量
                _ = x
                return np.zeros(0, dtype=float)
        """
    )


def _pipeline_template() -> str:
    return dedent(
        """\
        # -*- coding: utf-8 -*-
        \"\"\"Example pipeline: init + mutate + repair for continuous vectors.\"\"\"

        from __future__ import annotations

        from nsgablack.representation import (
            ClipRepair,
            GaussianMutation,
            RepresentationPipeline,
            UniformInitializer,
        )


        def build_pipeline() -> RepresentationPipeline:
            pipeline = RepresentationPipeline(
                initializer=UniformInitializer(low=-5.0, high=5.0),
                mutator=GaussianMutation(sigma=0.25, low=-5.0, high=5.0),
                repair=ClipRepair(low=-5.0, high=5.0),
                encoder=None,
            )
            pipeline.context_requires = ()
            pipeline.context_provides = ()
            pipeline.context_mutates = ()
            pipeline.context_cache = ()
            pipeline.context_notes = "No context read/write in this minimal pipeline."
            return pipeline
        """
    )


def _pipeline_class_template() -> str:
    return dedent(
        """\
        # -*- coding: utf-8 -*-
        \"\"\"管线模板：复制后改类名即可组合 initializer/mutator/repair。\"\"\"

        from __future__ import annotations

        from typing import Optional

        import numpy as np

        from nsgablack.representation.base import RepresentationComponentContract


        class PipelineInitializerTemplate(RepresentationComponentContract):
            \"\"\"初始化器模板。\"\"\"

            context_requires = ()
            context_provides = ()
            context_mutates = ()
            context_cache = ()
            context_notes = ("初始化器模板：负责生成可行初始解。",)

            def initialize(self, problem, context: Optional[dict] = None) -> np.ndarray:
                # 这里默认全零初始化；按你的问题改成随机或启发式都可以
                _ = context
                return np.zeros(problem.dimension, dtype=float)


        class PipelineMutationTemplate(RepresentationComponentContract):
            \"\"\"变异器模板。\"\"\"

            context_requires = ()
            context_provides = ()
            context_mutates = ()
            context_cache = ()
            context_notes = ("变异器模板：输入 x 输出 x'。",)

            def mutate(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
                # 这里是无操作变异；先保证流程通，再换成真实变异
                _ = context
                return np.array(x, copy=True)


        class PipelineRepairTemplate(RepresentationComponentContract):
            \"\"\"修复器模板。\"\"\"

            context_requires = ()
            context_provides = ()
            context_mutates = ()
            context_cache = ()
            context_notes = ("修复器模板：把候选解拉回可行域。",)

            def repair(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
                # 这里默认不改动；后续按硬约束补修复逻辑
                _ = context
                return np.array(x, copy=True)
        """
    )


def _bias_template() -> str:
    return dedent(
        """\
        # -*- coding: utf-8 -*-
        \"\"\"Example bias assembly.\"\"\"

        from __future__ import annotations

        from nsgablack.bias import BiasModule


        def build_bias_module(enable_bias: bool = False) -> BiasModule:
            module = BiasModule()
            if enable_bias:
                # Add domain/algorithmic bias here when needed.
                # Keep default empty so project is runnable from day one.
                pass
            module.context_requires = ()
            module.context_provides = ()
            module.context_mutates = ()
            module.context_cache = ()
            module.context_notes = "No default bias I/O in starter template."
            return module
        """
    )


def _bias_class_template() -> str:
    return dedent(
        """\
        # -*- coding: utf-8 -*-
        \"\"\"偏置模板：复制后改文件名和类名即可接入。\"\"\"

        from __future__ import annotations

        import numpy as np

        from nsgablack.bias.core.base import BiasBase, OptimizationContext


        class BiasTemplate(BiasBase):
            \"\"\"最小可运行偏置模板。\"\"\"

            context_requires = ()
            context_provides = ()
            context_mutates = ()
            context_cache = ()
            context_notes = ("偏置模板：基于 x/context 计算一个标量偏好值。",)
            requires_metrics = ()
            metrics_fallback = "none"
            missing_metrics_policy = "warn"

            def __init__(self, weight: float = 1.0) -> None:
                # weight 控制偏置强度；建议先用 1.0 再微调
                super().__init__(name="bias_template", weight=float(weight), description="偏置模板")

            def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
                # 返回值越大表示越偏好；这里默认返回 0（不施加偏好）
                _ = context
                _ = x
                return 0.0
        """
    )


def _adapter_class_template() -> str:
    return dedent(
        """\
        # -*- coding: utf-8 -*-
        \"\"\"适配器模板：复制后改文件名和类名即可接入 propose/update 流程。\"\"\"

        from __future__ import annotations

        from typing import Any, Dict, Sequence

        import numpy as np

        from nsgablack.adapters.algorithm_adapter import AlgorithmAdapter


        class AdapterTemplate(AlgorithmAdapter):
            \"\"\"最小可运行适配器模板。\"\"\"

            context_requires = ()
            context_provides = ()
            context_mutates = ()
            context_cache = ()
            context_notes = ("适配器模板：在 propose/update 生命周期中维护算法状态。",)

            def __init__(self, max_candidates: int = 8) -> None:
                super().__init__(name="adapter_template")
                # 每轮最多提出多少个候选解
                self.max_candidates = max(1, int(max_candidates))
                self._last_population: np.ndarray | None = None

            def propose(self, solver: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
                # 提案阶段：生成候选解列表
                _ = context
                rng = self.create_local_rng(solver)
                dim = int(getattr(getattr(solver, "problem", None), "dimension", 1))
                out = []
                for _ in range(self.max_candidates):
                    out.append(rng.uniform(-1.0, 1.0, size=(dim,)))
                return out

            def update(
                self,
                solver: Any,
                candidates: Sequence[np.ndarray],
                objectives: np.ndarray,
                violations: np.ndarray,
                context: Dict[str, Any],
            ) -> None:
                # 更新阶段：消费评估反馈，维护内部状态
                _ = solver
                _ = objectives
                _ = violations
                _ = context
                if candidates is not None and len(candidates) > 0:
                    self._last_population = np.asarray(candidates, dtype=float)
        """
    )


def _plugin_template() -> str:
    return dedent(
        """\
        # -*- coding: utf-8 -*-
        \"\"\"Example plugin template with explicit context contract.\"\"\"

        from __future__ import annotations

        from typing import Any, Dict

        from nsgablack.plugins.base import Plugin
        from nsgablack.core.state.context_keys import KEY_GENERATION

        KEY_PROJECT_EXAMPLE_HIT = "project.example_plugin.hit_count"


        class ExampleProjectPlugin(Plugin):
            \"\"\"Minimal project plugin: count generation hits and expose a context key.\"\"\"

            context_requires = (KEY_GENERATION,)
            context_provides = (KEY_PROJECT_EXAMPLE_HIT,)
            context_mutates = (KEY_PROJECT_EXAMPLE_HIT,)
            context_cache = ()
            context_notes = ("Demo plugin for scaffold: updates a project-level counter.",)

            def __init__(self, interval: int = 5, verbose: bool = True) -> None:
                super().__init__(name="project_example_plugin")
                self.interval = max(1, int(interval))
                self.verbose = bool(verbose)
                self._hit_count = 0

            def on_solver_init(self, solver) -> None:
                self._hit_count = 0

            def on_generation_end(self, generation: int) -> None:
                generation = int(generation)
                if generation % self.interval != 0:
                    return None
                self._hit_count += 1
                if self.verbose:
                    print(f"[example_plugin] gen={generation} hit_count={self._hit_count}")
                return None

            def on_context_build(self, context: Dict[str, Any]) -> Dict[str, Any]:
                context[KEY_PROJECT_EXAMPLE_HIT] = int(self._hit_count)
                return context

            def on_solver_finish(self, result: Dict[str, Any]) -> None:
                result["example_project_plugin"] = {
                    "hit_count": int(self._hit_count),
                    "interval": int(self.interval),
                }
        """
    )


def _adapter_readme() -> str:
    return dedent(
        """\
        # adapter

        策略层（propose/update 搜索逻辑）。  
        Strategy layer for propose/update search logic.

        ## 说明 / Notes
        - 多数项目可先不写自定义 adapter。
        - 当默认 solver 循环不足时再新增 adapter。
        - Typical projects can start without custom adapters.
        - Add adapter only when default solver loop is not enough.

        ## 推荐 context 声明 / Recommended context declaration
        - `context_requires`: required fields
        - `context_provides`: produced fields
        - `context_mutates`: overwritten fields
        - `context_cache`: non-replayable cache fields
        """
    )


def _plugin_readme() -> str:
    return dedent(
        """\
        # plugins

        工程插件层：日志、并行、监控、回放、存储。  
        Engineering plugin layer: logging, parallelism, monitor, replay, storage.

        ## 说明 / Notes
        - 插件聚焦工程能力，不承载核心问题建模。
        - 每个插件尽量显式声明 context 契约。
        - Keep plugins focused on capabilities, not core problem modeling.
        - Prefer explicit context contracts for each plugin.

        ## 常用起步项 / Typical starters
        - `BenchmarkHarnessPlugin`
        - `ModuleReportPlugin`
        - `BoundaryGuardPlugin`
        """
    )


def _plugin_class_template() -> str:
    return dedent(
        """\
        # -*- coding: utf-8 -*-
        \"\"\"插件模板：复制后改文件名和类名即可开始开发。\"\"\"

        from __future__ import annotations

        from typing import Any, Dict

        from nsgablack.plugins.base import Plugin
        from nsgablack.core.state.context_keys import KEY_GENERATION

        KEY_PROJECT_PLUGIN_TEMPLATE = "project.plugin_template.hit_count"


        class PluginTemplate(Plugin):
            \"\"\"最小可运行插件模板。\"\"\"

            context_requires = (KEY_GENERATION,)
            context_provides = (KEY_PROJECT_PLUGIN_TEMPLATE,)
            context_mutates = (KEY_PROJECT_PLUGIN_TEMPLATE,)
            context_cache = ()
            context_notes = ("插件模板：按固定代间隔记录命中次数，并写入 context。",)

            def __init__(self, interval: int = 5, verbose: bool = True) -> None:
                super().__init__(name="plugin_template")
                # interval：每隔多少代触发一次；verbose：是否打印日志
                self.interval = max(1, int(interval))
                self.verbose = bool(verbose)
                self._hit_count = 0

            def on_solver_init(self, solver) -> None:
                # 每次新 run 开始时重置内部状态
                self._hit_count = 0

            def on_generation_end(self, generation: int) -> None:
                # 代末触发：按 interval 统计命中次数
                generation = int(generation)
                if generation % self.interval != 0:
                    return None
                self._hit_count += 1
                if self.verbose:
                    print(f"[plugin_template] gen={generation} hit_count={self._hit_count}")
                return None

            def on_context_build(self, context: Dict[str, Any]) -> Dict[str, Any]:
                # 将插件状态暴露到 context，便于 Inspector / 其他组件读取
                context[KEY_PROJECT_PLUGIN_TEMPLATE] = int(self._hit_count)
                return context
        """
    )


def _project_registry_template() -> str:
    return dedent(
        """\
        # -*- coding: utf-8 -*-
        \"\"\"Project-local Catalog registration.

        NOTE:
        - Preferred local registration source is `catalog/entries.toml` (created by scaffold).
        - Keep this file for optional dynamic registration only.
        \"\"\"

        from __future__ import annotations

        def get_project_entries():
            # Optional dynamic entries. Keep empty by default.
            return []
        """
    )


def _project_catalog_entries_template() -> str:
    return dedent(
        """\
        [[entry]]
        key = "project.problem.example"
        title = "ExampleProblem"
        kind = "tool"
        import_path = "problem.example_problem:ExampleProblem"
        tags = ["project", "example", "problem"]
        summary = "Example two-objective problem."
        companions = ["project.pipeline.example"]
        context_requires = []
        context_provides = []
        context_mutates = []
        context_cache = []
        context_notes = ["Defines objective/constraint semantics only; no runtime context writes."]
        use_when = ["Define project objective/constraint semantics."]
        minimal_wiring = ["from problem.example_problem import ExampleProblem"]
        required_companions = ["project.pipeline.example"]
        config_keys = ["dimension"]
        example_entry = "build_solver:build_solver"

        [[entry]]
        key = "project.pipeline.example"
        title = "build_pipeline"
        kind = "representation"
        import_path = "pipeline.example_pipeline:build_pipeline"
        tags = ["project", "example", "pipeline"]
        summary = "Example representation pipeline."
        companions = ["project.problem.example"]
        context_requires = []
        context_provides = []
        context_mutates = []
        context_cache = []
        context_notes = ["Pipeline handles init/mutate/repair; no additional runtime context keys."]
        use_when = ["Need init/mutate/repair wiring for vector representation."]
        minimal_wiring = [
          "from pipeline.example_pipeline import build_pipeline",
          "solver.set_representation_pipeline(build_pipeline())",
        ]
        required_companions = ["project.problem.example"]
        config_keys = []
        example_entry = "build_solver:build_solver"

        [[entry]]
        key = "project.solver.example"
        title = "build_solver"
        kind = "example"
        import_path = "build_solver:build_solver"
        tags = ["project", "example", "solver"]
        summary = "Example solver assembly entry."
        companions = ["project.problem.example", "project.pipeline.example"]
        context_requires = []
        context_provides = []
        context_mutates = []
        context_cache = []
        context_notes = ["Assembly entrypoint; context contract is delegated to registered components."]
        use_when = ["Need runnable assembly entry for CLI and Run Inspector."]
        minimal_wiring = ["python build_solver.py"]
        required_companions = ["project.problem.example", "project.pipeline.example"]
        config_keys = ["dimension", "pop_size", "generations", "enable_bias"]
        example_entry = "build_solver:build_solver"

        [[entry]]
        key = "project.plugin.example"
        title = "ExampleProjectPlugin"
        kind = "plugin"
        import_path = "plugins.example_plugin:ExampleProjectPlugin"
        tags = ["project", "example", "plugin"]
        summary = "Example plugin template with explicit context contracts."
        companions = ["project.solver.example"]
        context_requires = ["generation"]
        context_provides = ["project.example_plugin.hit_count"]
        context_mutates = ["project.example_plugin.hit_count"]
        context_cache = []
        context_notes = ["Scaffold plugin example for lifecycle/context wiring."]
        use_when = ["Need a minimal custom plugin starting point."]
        minimal_wiring = [
          "from plugins.example_plugin import ExampleProjectPlugin",
          "solver.add_plugin(ExampleProjectPlugin(interval=5))",
        ]
        required_companions = ["project.solver.example"]
        config_keys = ["interval", "verbose"]
        example_entry = "build_solver:build_solver"
        """
    )


def _build_solver_template() -> str:
    return dedent(
        """
        # -*- coding: utf-8 -*-
        \"\"\"Project entrypoint with explicit registration zones.

        项目入口：显式注册各层组件。
        Keep all assembly in this file. For each zone, define:
        1) `_extend_<zone>_args(parser)` for CLI flags
        2) `_register_<zone>(...)` for component wiring

        建议顺序 / Recommended order:
        1) problem / 问题
        2) pipeline / 表示
        3) bias / 偏置
        4) solver core / 求解器
        5) controllers (L3) / 控制器
        6) evaluation providers (L4) / 评估提供方
        7) observability plugins / 观测插件
        8) project/domain plugins / 项目插件
        9) optional checkpoint / 断点续跑
        10) L0 acceleration backend / 加速后端

        Stage-gate reminder:
        - Gate 1: problem semantics only
        - Gate 2: layer placement
        - Gate 3: catalog candidate review
        - Gate 4: zone wiring (this file)
        \"\"\"

        from __future__ import annotations

        import argparse
        from datetime import datetime

        from nsgablack.core.control_plane import BaseController, ControlDecision
        from nsgablack.core.evaluation_runtime import EvaluationProvider
        from nsgablack.core.evolution_solver import EvolutionSolver
        from nsgablack.utils.wiring import attach_checkpoint_resume
        from nsgablack.utils.wiring import attach_observability_profile

        from bias.example_bias import build_bias_module
        from pipeline.example_pipeline import build_pipeline
        from plugins.example_plugin import ExampleProjectPlugin
        from problem.example_problem import ExampleProblem


        # --- Zone 1: problem / 问题 -----------------------------------------
        def _extend_problem_args(parser: argparse.ArgumentParser) -> None:
            parser.add_argument("--dimension", type=int, default=8)


        def _register_problem(args) -> ExampleProblem:
            # DO: only create problem semantics.
            # DO NOT: attach plugins / strategy / repair rules here.
            return ExampleProblem(dimension=int(args.dimension))


        # --- Zone 2: pipeline / 表示 --------------------------------------
        def _extend_pipeline_args(parser: argparse.ArgumentParser) -> None:
            _ = parser
            # Add pipeline-specific flags here when needed.


        def _register_pipeline(args):
            _ = args
            # DO: keep init/mutate/repair/encode-decode here.
            # DO NOT: put business objective semantics here.
            return build_pipeline()


        # --- Zone 3: bias / 偏置 --------------------------------------------
        def _extend_bias_args(parser: argparse.ArgumentParser) -> None:
            parser.add_argument("--enable-bias", action="store_true")


        def _register_bias(problem: ExampleProblem, args):
            _ = problem
            # DO: soft guidance only.
            # DO NOT: hard-feasibility enforcement (belongs to pipeline repair).
            return build_bias_module(enable_bias=bool(args.enable_bias))


        # --- Zone 4: solver core / 求解器 ----------------------------------
        def _extend_solver_args(parser: argparse.ArgumentParser) -> None:
            parser.add_argument("--pop-size", type=int, default=80)
            parser.add_argument("--generations", type=int, default=60)
            parser.add_argument("--plugin-strict", action="store_true")
            parser.add_argument(
                "--thread-bias-isolation",
                choices=["deepcopy", "disable_cache", "off"],
                default="deepcopy",
                help="Thread backend bias isolation policy when parallel evaluation is enabled.",
            )


        def _register_solver(problem: ExampleProblem, pipeline, bias_module, args) -> EvolutionSolver:
            # DO: wire solver + adapter/strategy parameters.
            # DO NOT: spread plugin registration into this zone.
            solver = EvolutionSolver(problem, bias_module=bias_module)
            solver.pop_size = int(args.pop_size)
            solver.max_generations = int(args.generations)
            solver.mutation_rate = 0.2
            solver.crossover_rate = 0.8
            solver.enable_progress_log = True
            solver.report_interval = max(1, solver.max_generations // 10)
            solver.set_representation_pipeline(pipeline)
            solver.parallel_thread_bias_isolation = str(args.thread_bias_isolation)
            if hasattr(solver, "plugin_manager") and getattr(solver, "plugin_manager", None) is not None:
                try:
                    solver.plugin_manager.strict = bool(args.plugin_strict)
                except Exception:
                    pass
            return solver


        # --- Zone 5: controllers (L3) / 控制器 -----------------------------
        def _extend_controller_args(parser: argparse.ArgumentParser) -> None:
            parser.add_argument("--enable-stop-controller", action="store_true")


        class _MaxGenerationStopController(BaseController):
            domain = "stopping"
            slots = ("gen_end",)

            def __init__(self, *, limit: int) -> None:
                super().__init__(name="max_generation_stop", priority=10)
                self.limit = int(limit)

            def propose(self, solver, slot: str, context):
                _ = context
                if str(slot) != "gen_end":
                    return None
                should_stop = int(getattr(solver, "generation", 0)) + 1 >= self.limit
                return ControlDecision(
                    domain="stopping",
                    slot=str(slot),
                    controller=self.name,
                    priority=self.priority,
                    payload={"stop": bool(should_stop)},
                    reason="max_generation_reached",
                )


        def _register_controllers(solver: EvolutionSolver, args) -> None:
            if bool(args.enable_stop_controller):
                solver.register_controller(_MaxGenerationStopController(limit=int(args.generations)))


        # --- Zone 6: evaluation providers (L4) / 评估提供方 ----------------------
        def _extend_eval_provider_args(parser: argparse.ArgumentParser) -> None:
            parser.add_argument("--enable-l4-placeholder-provider", action="store_true")


        class _NoopProvider:
            name = "noop_provider"
            semantic_mode = "equivalent"

            def can_handle_individual(self, solver, x, context):
                _ = solver
                _ = x
                _ = context
                return False

            def evaluate_individual(self, solver, x, context, individual_id=None):
                _ = solver
                _ = x
                _ = context
                _ = individual_id
                return None

            def can_handle_population(self, solver, population, context):
                _ = solver
                _ = population
                _ = context
                return False

            def evaluate_population(self, solver, population, context):
                _ = solver
                _ = population
                _ = context
                return None


        def _register_evaluation_providers(solver: EvolutionSolver, args) -> None:
            if bool(args.enable_l4_placeholder_provider):
                solver.register_evaluation_provider(_NoopProvider())


        # --- Zone 7: observability plugins / 观测插件 ---------------------------
        def _extend_observability_args(parser: argparse.ArgumentParser) -> None:
            parser.add_argument(
                "--observability-profile",
                choices=["quickstart", "default", "strict"],
                default="default",
                help="Plug-and-play profile for observability wiring.",
            )
            parser.add_argument("--no-profiler", action="store_true")
            parser.add_argument("--no-decision-trace", action="store_true")
            parser.add_argument("--run-dir", default="runs")
            parser.add_argument("--run-id", default=None)


        def _register_observability_plugins(solver: EvolutionSolver, args, run_id: str) -> None:
            # Framework observability/runtime plugins only.
            attach_observability_profile(
                solver,
                profile=str(args.observability_profile),
                output_dir=str(args.run_dir),
                run_id=run_id,
                enable_profiler=False if bool(args.no_profiler) else None,
                enable_decision_trace=False if bool(args.no_decision_trace) else None,
            )


        # --- Zone 8: project plugins / 项目插件 --------------------------------
        def _extend_project_plugin_args(parser: argparse.ArgumentParser) -> None:
            parser.add_argument("--enable-example-plugin", action="store_true")


        def _register_project_plugins(solver: EvolutionSolver, args) -> None:
            # Register domain/business plugins in this zone only.
            if bool(args.enable_example_plugin):
                solver.add_plugin(ExampleProjectPlugin(interval=5, verbose=True))


        # --- Zone 9: optional checkpoint / 断点续跑 -------------------------
        def _extend_checkpoint_args(parser: argparse.ArgumentParser) -> None:
            parser.add_argument("--enable-checkpoint", action="store_true")
            parser.add_argument("--checkpoint-dir", default="runs/checkpoints")
            parser.add_argument(
                "--trust-checkpoint",
                action="store_true",
                help="Explicitly trust unsigned checkpoints for resume (not allowed with strict mode).",
            )


        def _register_optional_checkpoint(solver: EvolutionSolver, args) -> None:
            # Optional engineering capability; keep isolated from core zones.
            if not bool(args.enable_checkpoint):
                return
            attach_checkpoint_resume(
                solver,
                checkpoint_dir=str(args.checkpoint_dir),
                auto_resume=True,
                strict=not bool(args.trust_checkpoint),
                trust_checkpoint=bool(args.trust_checkpoint),
            )


        # --- Zone 10: L0 acceleration backend / 加速后端 -----------------------
        def _extend_l0_args(parser: argparse.ArgumentParser) -> None:
            parser.add_argument(
                "--accel-backend",
                choices=["default", "vectorized"],
                default="default",
            )


        def _register_l0_backend(solver: EvolutionSolver, args) -> None:
            _ = solver
            _ = args
            # Register real acceleration backend factories here when needed.


        def _build_parser() -> argparse.ArgumentParser:
            parser = argparse.ArgumentParser(add_help=False)
            _extend_problem_args(parser)
            _extend_pipeline_args(parser)
            _extend_bias_args(parser)
            _extend_solver_args(parser)
            _extend_controller_args(parser)
            _extend_eval_provider_args(parser)
            _extend_observability_args(parser)
            _extend_project_plugin_args(parser)
            _extend_checkpoint_args(parser)
            _extend_l0_args(parser)
            return parser


        def _parse_args(argv: list[str] | None = None):
            parser = _build_parser()
            args, _ = parser.parse_known_args(argv if argv is not None else [])
            return args


        def build_solver(argv: list[str] | None = None) -> EvolutionSolver:
            args = _parse_args(argv)
            run_id = str(args.run_id) if args.run_id else datetime.now().strftime("%Y%m%d_%H%M%S")

            problem = _register_problem(args)
            pipeline = _register_pipeline(args)
            bias_module = _register_bias(problem, args)
            solver = _register_solver(problem, pipeline, bias_module, args)
            _register_controllers(solver, args)
            _register_evaluation_providers(solver, args)
            _register_observability_plugins(solver, args, run_id)
            _register_project_plugins(solver, args)
            _register_optional_checkpoint(solver, args)
            _register_l0_backend(solver, args)
            return solver


        def main() -> None:
            solver = build_solver()
            result = solver.run(return_dict=True)
            pareto = result.get("pareto_solutions") or {}
            objs = pareto.get("objectives")
            if objs is not None and len(objs) > 0:
                best_f1 = min(float(row[0]) for row in objs)
                print(f"[example] best_objective_0={best_f1:.6f}")
            else:
                print("[example] run finished but no pareto objectives were returned")


        if __name__ == "__main__":
            main()
        """
    )


def _build_solver_registration_guide_template() -> str:
    return dedent(
        """        # BUILD_SOLVER_REGISTRATION

        Goal: after searching from catalog, you should know exactly where to place each component.
        补充：从 catalog 检索后，把组件放到正确的注册区。

        ## Zone Pair Rule (must follow)
        Each zone keeps two functions together:
        - `_extend_<zone>_args(parser)`: CLI flags for this zone.
        - `_register_<zone>(...)`: component wiring for this zone.

        ## Zone Order
        1. Problem
           - `_extend_problem_args(parser)`
           - `_register_problem(args)`

        2. Pipeline
           - `_extend_pipeline_args(parser)`
           - `_register_pipeline(args)`

        3. Bias
           - `_extend_bias_args(parser)`
           - `_register_bias(problem, args)`

        4. Solver Core
           - `_extend_solver_args(parser)`
           - `_register_solver(problem, pipeline, bias_module, args)`

        5. Controllers (L3)
           - `_extend_controller_args(parser)`
           - `_register_controllers(solver, args)`
           - Rule: one controller owns one control domain.

        6. Evaluation Providers (L4)
           - `_extend_eval_provider_args(parser)`
           - `_register_evaluation_providers(solver, args)`
           - Rule: semantic replacement must enter through `register_evaluation_provider`.

        7. Observability Plugins
           - `_extend_observability_args(parser)`
           - `_register_observability_plugins(solver, args, run_id)`
           - Recommended: use `--observability-profile` first, then override with `--no-profiler` / `--no-decision-trace` only when needed.

        8. Project Plugins
           - `_extend_project_plugin_args(parser)`
           - `_register_project_plugins(solver, args)`

        9. Checkpoint (Optional)
           - `_extend_checkpoint_args(parser)`
           - `_register_optional_checkpoint(solver, args)`

        10. L0 Acceleration Backend
           - `_extend_l0_args(parser)`
           - `_register_l0_backend(solver, args)`

        ## Catalog Kind -> Zone Mapping
        - `problem` -> Problem zone
        - `pipeline` / `representation` -> Pipeline zone
        - `bias` -> Bias zone
        - `adapter` / `solver` -> Solver Core zone
        - `controller` -> Controllers zone
        - `evaluation-provider` -> Evaluation Providers zone
        - `plugin`:
          - observability/runtime plugin -> Observability zone
          - domain/business plugin -> Project Plugins zone

        ## Selection Checklist (before wiring)
        For each chosen component, answer in one line:
        - Why this component fits this problem
        - Which alternatives were rejected and why
        - Expected input/output shape
        - Required context keys and side effects

        ## Validation Checklist (after wiring)
        - Run `python -m nsgablack project doctor --path . --build --strict`
        - Ensure no layer misuse (wrong-zone logic)
        - Ensure shape/context contract is explainable by file and line

        ## Guardrails
        - Keep `build_solver(argv=None)` as the only assembly entrypoint.
        - Prefer `solver.add_plugin(...)` only in project plugin zone.
        - Do not put repair logic into problem/bias.
        - Do not put business semantics into plugins.
        """
    )

def _vscode_snippets_template() -> str:
    return dedent(
        """\
        {
          "NSGABlack Bias Template": {
            "scope": "python",
            "prefix": ["nbias", "@component(kind=\\"bias\\")"],
            "body": [
              "from nsgablack.catalog.markers import component",
              "from nsgablack.bias.core.base import BiasBase, OptimizationContext",
              "",
              "@component(kind=\\"bias\\")",
              "class ${1:Bias1}(BiasBase):",
              "    # TODO(中/EN): 仅声明真实读写字段 / declare only real read-write fields.",
              "    context_requires = ()",
              "    context_provides = ()",
              "    context_mutates = ()",
              "    context_cache = ()",
              "    context_notes = (\\"${2:TODO(中/EN): 一句话说明 context 契约 / one-line context contract.}\\",)",
              "    requires_metrics = ()",
              "    metrics_fallback = \\"none\\"",
              "    missing_metrics_policy = \\"warn\\"",
              "",
              "    def __init__(self, weight: float = 1.0) -> None:",
              "        # TODO(中/EN): 设置稳定组件名与说明 / set stable name and description.",
              "        super().__init__(name=\\"${3:bias_name}\\", weight=float(weight), description=\\"${4:TODO}\\")",
              "",
              "    def compute(self, x, context: OptimizationContext) -> float:",
              "        # TODO(中/EN): 返回标量偏好分 / return a scalar preference score.",
              "        _ = x",
              "        _ = context",
              "        raise NotImplementedError"
            ],
            "description": "Expand NSGABlack bias component template."
          },
          "NSGABlack Plugin Template": {
            "scope": "python",
            "prefix": ["nplugin", "@component(kind=\\"plugin\\")"],
            "body": [
              "from nsgablack.catalog.markers import component",
              "from nsgablack.plugins.base import Plugin",
              "",
              "@component(kind=\\"plugin\\")",
              "class ${1:Plugin1}(Plugin):",
              "    # TODO(中/EN): 仅声明真实读写字段 / declare only real read-write fields.",
              "    context_requires = ()",
              "    context_provides = ()",
              "    context_mutates = ()",
              "    context_cache = ()",
              "    context_notes = (\\"${2:TODO(中/EN): 一句话说明 context 契约 / one-line context contract.}\\",)",
              "",
              "    def __init__(self) -> None:",
              "        # TODO(中/EN): 设置稳定插件名 / set a stable plugin name.",
              "        super().__init__(name=\\"${3:plugin_name}\\")"
            ],
            "description": "Expand NSGABlack plugin component template."
          },
          "NSGABlack Adapter Template": {
            "scope": "python",
            "prefix": ["nadapter", "@component(kind=\\"adapter\\")"],
            "body": [
              "from nsgablack.catalog.markers import component",
              "from nsgablack.adapters.algorithm_adapter import AlgorithmAdapter",
              "",
              "@component(kind=\\"adapter\\")",
              "class ${1:Adapter1}(AlgorithmAdapter):",
              "    # TODO(中/EN): 仅声明真实读写字段 / declare only real read-write fields.",
              "    context_requires = ()",
              "    context_provides = ()",
              "    context_mutates = ()",
              "    context_cache = ()",
              "    context_notes = (\\"${2:TODO(中/EN): 一句话说明 context 契约 / one-line context contract.}\\",)",
              "",
              "    def __init__(self) -> None:",
              "        # TODO(中/EN): 设置稳定适配器名 / set a stable adapter name.",
              "        super().__init__(name=\\"${3:adapter_name}\\")",
              "",
              "    def propose(self, solver, context):",
              "        # TODO(中/EN): 生成候选解 / generate candidate solutions.",
              "        _ = solver",
              "        _ = context",
              "        raise NotImplementedError",
              "",
              "    def update(self, solver, candidates, objectives, violations, context):",
              "        # TODO(中/EN): 用评估反馈更新状态 / update state with evaluation feedback.",
              "        _ = solver",
              "        _ = candidates",
              "        _ = objectives",
              "        _ = violations",
              "        _ = context",
              "        raise NotImplementedError"
            ],
            "description": "Expand NSGABlack adapter component template."
          }
        }
        """
    )


def init_project(target_dir: Path | str, *, force: bool = False) -> Path:
    """Initialize a project scaffold under target_dir."""
    root = Path(target_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)

    if any(root.iterdir()) and not force:
        raise FileExistsError(f"Target directory not empty: {root}")

    for name in _FOLDERS:
        folder = root / name
        folder.mkdir(parents=True, exist_ok=True)
        if name != "catalog":
            _write_file(folder / "__init__.py", "", overwrite=force)
        if name == "adapter":
            _write_file(folder / "README.md", _adapter_readme(), overwrite=force)
        elif name == "plugins":
            _write_file(folder / "README.md", _plugin_readme(), overwrite=force)
        else:
            _write_file(folder / "README.md", _readme_for_folder(name), overwrite=force)

    _write_file(root / "README.md", _root_readme(root.name), overwrite=force)
    _write_file(
        root / ".nsgablack-project",
        "marker = nsgablack-scaffold-project\n",
        overwrite=force,
    )
    (root / "docs" / "contracts").mkdir(parents=True, exist_ok=True)
    (root / "tests" / "templates").mkdir(parents=True, exist_ok=True)
    _write_file(root / "START_HERE.md", _start_here(), overwrite=force)
    _write_file(
        root / "BUILD_SOLVER_REGISTRATION.md",
        _build_solver_registration_guide_template(),
        overwrite=force,
    )
    _write_file(root / "COMPONENT_REGISTRATION.md", _component_registration_guide(), overwrite=force)
    _write_file(
        root / "docs" / "contracts" / "COMPONENT_CONTRACT_TEMPLATE.md",
        _component_contract_template(),
        overwrite=force,
    )
    _write_file(
        root / "tests" / "templates" / "README.md",
        _component_test_matrix_readme(),
        overwrite=force,
    )
    _write_file(
        root / "tests" / "templates" / "smoke_template.py",
        _smoke_test_template(),
        overwrite=force,
    )
    _write_file(
        root / "tests" / "templates" / "contract_template.py",
        _contract_test_template(),
        overwrite=force,
    )
    _write_file(
        root / "tests" / "templates" / "checkpoint_roundtrip_template.py",
        _checkpoint_roundtrip_test_template(),
        overwrite=force,
    )
    _write_file(
        root / "tests" / "templates" / "strict_fault_template.py",
        _strict_fault_test_template(),
        overwrite=force,
    )
    _write_file(root / "project_registry.py", _project_registry_template(), overwrite=force)
    _write_file(root / "catalog" / "entries.toml", _project_catalog_entries_template(), overwrite=force)
    _write_file(root / "build_solver.py", _build_solver_template(), overwrite=force)
    _write_file(root / "problem" / "example_problem.py", _problem_template(), overwrite=force)
    _write_file(root / "problem" / "template_problem.py", _problem_class_template(), overwrite=force)
    _write_file(root / "pipeline" / "example_pipeline.py", _pipeline_template(), overwrite=force)
    _write_file(root / "pipeline" / "template_pipeline.py", _pipeline_class_template(), overwrite=force)
    _write_file(root / "bias" / "example_bias.py", _bias_template(), overwrite=force)
    _write_file(root / "bias" / "template_bias.py", _bias_class_template(), overwrite=force)
    _write_file(root / "adapter" / "template_adapter.py", _adapter_class_template(), overwrite=force)
    _write_file(root / "plugins" / "example_plugin.py", _plugin_template(), overwrite=force)
    _write_file(root / "plugins" / "template_plugin.py", _plugin_class_template(), overwrite=force)
    (root / ".vscode").mkdir(parents=True, exist_ok=True)
    _write_file(root / ".vscode" / "nsgablack.code-snippets", _vscode_snippets_template(), overwrite=force)

    return root
