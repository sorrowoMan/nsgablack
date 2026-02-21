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
    return dedent(
        f"""\
        # {name}

        **中文说明**
        - 目录职责：{desc}
        - 边界要求：只放本层职责，不要在本目录隐藏跨层逻辑。
        - 输入输出契约：
          - 输入：数据来源、参数、读取的 context 字段
          - 输出：返回对象、写入的 context 字段、副作用
          - 若使用 context，建议显式声明
            `context_requires/context_provides/context_mutates/context_cache`。
        - 最小示例：至少保留一个可运行文件，或在此写清入口路径。

        **English**
        - Responsibility: {desc}
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
        f"""\
        # {project_name}

        **中文说明**
        NSGABlack 本地项目骨架。

        ## 目录结构 / Structure
        - `problem/`: 问题定义 / problem definition
        - `pipeline/`: 表示与硬约束 / representation + hard constraints
        - `bias/`: 软偏好 / soft preference
        - `adapter/`: 策略编排（可选）/ strategy orchestration (optional)
        - `plugins/`: 工程能力（可选）/ engineering capabilities (optional)
        - `data/`: 输入数据 / input data
        - `assets/`: 输出产物 / outputs

        ## 推荐流程 / Recommended Flow
        1. 阅读 `START_HERE.md`.
        2. 阅读 `COMPONENT_REGISTRATION.md`.
        3. 运行 `python -m nsgablack project doctor --path . --build`.
        4. 用 `build_solver.py` 作为唯一装配入口。

        ## 入口文件 / Entry Files
        - `build_solver.py`: 装配 problem/pipeline/bias/strategy
        - `project_registry.py`: 项目本地 Catalog 注册
        - `COMPONENT_REGISTRATION.md`: 注册组件的 why/what/how
        """
    )


def _start_here() -> str:
    return dedent(
        """\
        # START_HERE

        新项目 6 步上手（中文 + English）。

        ## Step 1 - 先做体检 / Health check first
        ```powershell
        python -m nsgablack project doctor --path . --build
        ```
        - 若要新增可复用组件，先读 `COMPONENT_REGISTRATION.md`。
        - If you will add reusable components, read `COMPONENT_REGISTRATION.md` first.

        ## Step 2 - 实现问题层 / Implement problem
        - File: `problem/example_problem.py`
        - 必需 / Required:
          - `evaluate(x)` returns objective vector (`numpy.ndarray`)
          - `evaluate_constraints(x)` returns violation vector (empty if no constraints)

        ## Step 3 - 实现管线层 / Implement pipeline
        - File: `pipeline/example_pipeline.py`
        - 硬可行性优先放在此层 / Keep hard feasibility in this layer.

        ## Step 4 - 按需加偏置 / Add bias if needed
        - File: `bias/example_bias.py`
        - 偏置表达偏好，不替代硬约束 / Bias encodes preference, not hard constraints.

        ## Step 5 - 只做装配 / Assemble only
        - File: `build_solver.py`
        - 保持 wiring，不重写框架内核 / Keep it as wiring; avoid re-implementing internals.

        ## Step 6 - 运行与检查 / Run and inspect
        ```powershell
        python build_solver.py
        python -m nsgablack project catalog list --path .
        ```

        ## 可选 / Optional
        - Run Inspector: `python -m nsgablack run_inspector --entry build_solver.py:build_solver`
        - 搜索时合并全局目录 / Include global catalog in search:
          `python -m nsgablack project catalog search vns --path . --global`
        """
    )


def _component_registration_guide() -> str:
    return dedent(
        """\
        # COMPONENT_REGISTRATION

        本文件定义项目本地组件注册契约。  
        This file defines the local project registration contract.

        ## 为什么要注册 / Why register components
        - 让组件可被 Catalog 和 Run Inspector 检索。
        - 保持装配可复现（`build_solver.py` + 稳定 key）。
        - 让 context 读写可审计（`context_*` 字段）。
        - Make components discoverable, reproducible, and auditable.

        ## 注册什么 / What should be registered
        注册可复用、可搜索、可开关的组件：  
        Register reusable components that may be searched, toggled, or reused:
        - problem builders
        - pipelines / biases / adapters / plugins
        - solver assembly entries

        不要注册一次性脚本或私有调试代码。  
        Do not register one-off helpers or private debug code.

        ## 在哪里注册 / Where to register
        - Local project entries: `project_registry.py`
        - 本地 key 建议简短；加载器会自动加前缀 `project.`
        - Local keys should be short; loader auto-prefixes with `project.`
          (example: `pipeline.example` -> `project.pipeline.example`)

        ## 最小契约 / Minimal entry contract
        Each `CatalogEntry` should include:
        - `key`, `kind`, `title`, `import_path`
        - `tags`, `summary`
        - `context_requires`, `context_provides`, `context_mutates`, `context_cache`
        - `use_when`, `minimal_wiring`, `required_companions`, `config_keys`, `example_entry`

        - 使用说明字段是可发现性的基础。
        - context 字段是契约审计的基础。
        - 若省略，框架可能推断默认值，但 CI/doctor 应视为不合规。
        - Usage fields are mandatory for discoverability UX.
        - Context fields are mandatory for contract auditability.
        - If omitted, framework may infer defaults, but CI/doctor should treat this as non-compliant.

        context 字段即使为空也显式写 `()`，并始终提供 `context_notes`。  
        Keep context fields explicit as `()`, and always provide `context_notes`.

        ## Example
        ```python
        CatalogEntry(
            key="plugin.eval_cache",
            title="Evaluation Cache Plugin",
            kind="plugin",
            import_path="plugins.eval_cache:EvaluationCachePlugin",
            tags=("project", "plugin", "cache"),
            summary="Cache repeated evaluations by deterministic key.",
            context_requires=("context.population",),
            context_provides=("context.cache.eval_hits",),
            context_mutates=("context.cache.eval_store",),
            context_cache=("context.cache.eval_store",),
        )
        ```

        ## 校验 / Validation
        修改注册后建议执行：  
        Run after changing registry entries:
        ```powershell
        python -m nsgablack project doctor --path . --build --strict
        python -m nsgablack project catalog list --path .
        python tools/catalog_integrity_checker.py --check-usage --strict-usage --check-context --context-kinds plugin --require-context-notes --strict-context
        ```

        ## UI 中的 Scope / Scope in UI
        In Run Inspector Catalog tab:
        - `Scope=project`: local project components
        - `Scope=framework`: framework built-in components
        - `Scope=all`: merged view
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

        from nsgablack.core.adapters.algorithm_adapter import AlgorithmAdapter


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
                if candidates:
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
        from nsgablack.utils.context.context_keys import KEY_GENERATION

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
        from nsgablack.utils.context.context_keys import KEY_GENERATION

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
        """\
        # -*- coding: utf-8 -*-
        \"\"\"Project entrypoint: assembly only.\"\"\"

        from __future__ import annotations

        import argparse

        from nsgablack.core.solver import BlackBoxSolverNSGAII

        from bias.example_bias import build_bias_module
        from pipeline.example_pipeline import build_pipeline
        from plugins.example_plugin import ExampleProjectPlugin
        from problem.example_problem import ExampleProblem


        def build_solver(argv: list[str] | None = None) -> BlackBoxSolverNSGAII:
            parser = argparse.ArgumentParser(add_help=False)
            parser.add_argument("--dimension", type=int, default=8)
            parser.add_argument("--pop-size", type=int, default=80)
            parser.add_argument("--generations", type=int, default=60)
            parser.add_argument("--enable-bias", action="store_true")
            parser.add_argument("--enable-example-plugin", action="store_true")
            args, _ = parser.parse_known_args(argv if argv is not None else [])

            problem = ExampleProblem(dimension=int(args.dimension))
            pipeline = build_pipeline()
            bias_module = build_bias_module(enable_bias=bool(args.enable_bias))

            solver = BlackBoxSolverNSGAII(problem, bias_module=bias_module)
            solver.pop_size = int(args.pop_size)
            solver.max_generations = int(args.generations)
            solver.mutation_rate = 0.2
            solver.crossover_rate = 0.8
            solver.enable_progress_log = True
            solver.report_interval = max(1, solver.max_generations // 10)
            solver.set_representation_pipeline(pipeline)
            if bool(args.enable_example_plugin):
                solver.add_plugin(ExampleProjectPlugin(interval=5, verbose=True))
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
    _write_file(root / "START_HERE.md", _start_here(), overwrite=force)
    _write_file(root / "COMPONENT_REGISTRATION.md", _component_registration_guide(), overwrite=force)
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

    return root
