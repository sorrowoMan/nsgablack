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
    "solver",
    "acceleration",
    "evaluation",
    "plugins",
    "assets",
    "docs",
]

_NON_PACKAGE_FOLDERS = {"catalog", "assets", "docs"}


_FOLDER_DESCRIPTIONS: Dict[str, str] = {
    "catalog": "Project-local catalog index: register discoverable local components.",
    "problem": "Problem layer: objectives, constraints, variables, and bounds.",
    "pipeline": "Representation layer: init/mutate/repair/encode/decode.",
    "bias": "Bias layer: soft preference and search tendency.",
    "adapter": "Strategy layer: propose/update orchestration.",
    "solver": "Solver core profiles and runtime governance.",
    "acceleration": "L0 acceleration backends (thread/process/GPU).",
    "evaluation": "L4 evaluation runtime providers (optional).",
    "plugins": "Engineering layer: logging, replay, diagnostics, storage.",
    "assets": "Output artifacts: charts, reports, exported files.",
    "docs": "Project documentation and design notes.",
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

        - Responsibility: {desc}
        - Boundary: keep only this layer's concern; avoid cross-layer logic here.
        - Context contract (if any):
          - `context_requires` / `context_provides` / `context_mutates` / `context_cache`
        - Minimal example: keep one runnable file, or document the entry path.
        """
    )


def _root_readme(project_name: str) -> str:
    return dedent(
        f"""\
        # {project_name}

        NSGABlack scaffold (my_project-style layout).

        ## Quickstart
        1. `python -m nsgablack project doctor --path . --build`
        2. `python run_solver.py --check`
        3. `python run_solver.py`

        ## Structure
        - `build_solver.py`: main assembly entry
        - `assembly.py`: attach/build helpers
        - `config.py`: project registries
        - `problem/`, `pipeline/`, `bias/`, `adapter/`, `solver/`
        - `acceleration/` (L0), `evaluation/` (L4)
        - `plugins/` (governance/ops/observability)
        - `catalog/entries.toml`: local catalog entries

        ## Notes
        - Parameters live in registries; selection happens in `build_solver.py`.
        - Use `project doctor` to validate contracts early.
        """
    )

def _start_here() -> str:
    return dedent(
        """\
        # START_HERE

        ## 1) Health Baseline
        ```powershell
        python -m nsgablack project doctor --path . --build
        ```

        ## 2) Define the Core Layers
        - `problem/`: objective + constraints
        - `pipeline/`: init/mutate/repair
        - `bias/`: soft preferences (optional)

        ## 3) Wire the Assembly
        - `build_solver.py` is the only assembly entry
        - parameters in registries; selection in build_solver

        ## 4) Run
        ```powershell
        python run_solver.py --check
        python run_solver.py
        ```

        ## 5) Optional
        ```powershell
        python -m nsgablack run_inspector --entry build_solver.py:build_solver
        ```
        """
    )


def _component_registration_guide() -> str:
    return dedent(
        """\
        # COMPONENT_REGISTRATION

        This file defines the local project registration contract.

        ## Why register components
        - Enable Catalog and Run Inspector discovery
        - Keep `build_solver.py` and `project_registry.py` aligned
        - Make context I/O traceable

        ## What should be registered
        - problems, pipelines, biases, adapters, plugins
        - solver assembly entries

        ## Where to register
        - `project_registry.py` for dynamic entries
        - `catalog/entries.toml` for static entries

        ## Minimal entry fields
        - `key`, `kind`, `title`, `import_path`
        - `tags`, `summary`
        - `context_requires`, `context_provides`, `context_mutates`, `context_cache`, `context_notes`
        - `use_when`, `minimal_wiring`, `required_companions`, `config_keys`, `example_entry`

        ## Validation
        ```powershell
        python -m nsgablack project doctor --path . --build --strict
        python -m nsgablack project catalog list --path .
        ```
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
        # Problem template: copy and rename for new problems.

        from __future__ import annotations

        import numpy as np

        from nsgablack.core.base import BlackBoxProblem


        class ProblemTemplate(BlackBoxProblem):
            # Minimal runnable problem template.

            def __init__(self, dimension: int = 8) -> None:
                bounds = {f"x{i}": [-5.0, 5.0] for i in range(dimension)}
                super().__init__(
                    name="ProblemTemplate",
                    dimension=dimension,
                    bounds=bounds,
                    objectives=["obj_0", "obj_1"],
                )

            def evaluate(self, x: np.ndarray) -> np.ndarray:
                arr = np.asarray(x, dtype=float).reshape(-1)
                obj_0 = float(np.sum(arr ** 2))
                obj_1 = float(np.sum(np.abs(arr)))
                return np.array([obj_0, obj_1], dtype=float)

            def evaluate_constraints(self, x: np.ndarray) -> np.ndarray:
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
        # Pipeline component templates: init/mutate/repair.

        from __future__ import annotations

        from typing import Optional

        import numpy as np

        from nsgablack.representation.base import RepresentationComponentContract


        class PipelineInitializerTemplate(RepresentationComponentContract):
            # Initializer template.

            context_requires = ()
            context_provides = ()
            context_mutates = ()
            context_cache = ()
            context_notes = ("Initializer template: produce a feasible initial candidate.",)

            def initialize(self, problem, context: Optional[dict] = None) -> np.ndarray:
                _ = context
                return np.zeros(problem.dimension, dtype=float)


        class PipelineMutationTemplate(RepresentationComponentContract):
            # Mutation template.

            context_requires = ()
            context_provides = ()
            context_mutates = ()
            context_cache = ()
            context_notes = ("Mutation template: input x -> output x'.",)

            def mutate(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
                _ = context
                return np.array(x, copy=True)


        class PipelineRepairTemplate(RepresentationComponentContract):
            # Repair template.

            context_requires = ()
            context_provides = ()
            context_mutates = ()
            context_cache = ()
            context_notes = ("Repair template: project candidates back to feasibility.",)

            def repair(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
                _ = context
                return np.array(x, copy=True)
        """
    )


def _bias_template() -> str:
    return dedent(
        """\
        # -*- coding: utf-8 -*-
        # Example bias assembly.

        from __future__ import annotations

        from nsgablack.bias import BiasModule

        from .config import BiasConfig


        def build_bias_module(enable_bias: bool | None = None, *, cfg: BiasConfig | None = None) -> BiasModule:
            if cfg is None:
                cfg = BiasConfig()
            if enable_bias is None:
                enable_bias = bool(cfg.enable_bias)
            module = BiasModule()
            if bool(enable_bias):
                # Add domain/algorithmic bias here when needed.
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
        # Bias template: copy and customize for new bias components.

        from __future__ import annotations

        import numpy as np

        from nsgablack.bias.core.base import BiasBase, OptimizationContext


        class BiasTemplate(BiasBase):
            # Minimal runnable bias template.

            context_requires = ()
            context_provides = ()
            context_mutates = ()
            context_cache = ()
            context_notes = ("Bias template: compute a scalar bias from x/context.",)
            requires_metrics = ()
            metrics_fallback = "none"
            missing_metrics_policy = "warn"

            def __init__(self, weight: float = 1.0) -> None:
                super().__init__(name="bias_template", weight=float(weight), description="bias template")

            def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
                _ = (x, context)
                return 0.0
        """
    )


def _adapter_class_template() -> str:
    return dedent(
        """\
        # -*- coding: utf-8 -*-
        # Adapter template: copy and customize propose/update.

        from __future__ import annotations

        from typing import Any, Dict, Sequence

        import numpy as np

        from nsgablack.adapters.algorithm_adapter import AlgorithmAdapter


        class AdapterTemplate(AlgorithmAdapter):
            # Minimal runnable adapter template.

            context_requires = ()
            context_provides = ()
            context_mutates = ()
            context_cache = ()
            context_notes = ("Adapter template: manage algorithm state in propose/update.",)

            def __init__(self, max_candidates: int = 8) -> None:
                super().__init__(name="adapter_template")
                self.max_candidates = max(1, int(max_candidates))
                self._last_population: np.ndarray | None = None

            def propose(self, solver: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
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
                _ = (solver, objectives, violations, context)
                if candidates is not None and len(candidates) > 0:
                    self._last_population = np.asarray(candidates, dtype=float)
        """
    )


def _plugin_template() -> str:
    return dedent(
        """\
        # -*- coding: utf-8 -*-
        # Example plugin template with explicit context contract.

        from __future__ import annotations

        from typing import Any, Dict

        from nsgablack.plugins.base import Plugin
        from nsgablack.core.state.context_keys import KEY_GENERATION

        KEY_PROJECT_EXAMPLE_HIT = "project.example_plugin.hit_count"


        class ExampleProjectPlugin(Plugin):
            # Minimal project plugin: count generation hits and expose a context key.

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

        Strategy layer for propose/update orchestration.

        ## Notes
        - Most projects can start without a custom adapter.
        - Add an adapter only when the default solver loop is not enough.

        ## Context Contract (recommended)
        - `context_requires`
        - `context_provides`
        - `context_mutates`
        - `context_cache`
        """
    )


def _plugin_readme() -> str:
    return dedent(
        """\
        # plugins

        Engineering plugin layer: logging, replay, diagnostics, storage.

        ## Notes
        - Plugins add capabilities, not algorithm semantics.
        - Prefer explicit context contracts for each plugin.
        """
    )


def _plugin_class_template() -> str:
    return dedent(
        """\
        # -*- coding: utf-8 -*-
        # Plugin template: copy and customize lifecycle hooks.

        from __future__ import annotations

        from typing import Any, Dict

        from nsgablack.plugins.base import Plugin
        from nsgablack.core.state.context_keys import KEY_GENERATION

        KEY_PROJECT_PLUGIN_TEMPLATE = "project.plugin_template.hit_count"


        class PluginTemplate(Plugin):
            # Minimal runnable plugin template.

            context_requires = (KEY_GENERATION,)
            context_provides = (KEY_PROJECT_PLUGIN_TEMPLATE,)
            context_mutates = (KEY_PROJECT_PLUGIN_TEMPLATE,)
            context_cache = ()
            context_notes = ("Template plugin that exposes a small runtime counter.",)

            def __init__(self, interval: int = 5, verbose: bool = True) -> None:
                super().__init__(name="plugin_template")
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
                    print(f"[plugin_template] gen={generation} hit_count={self._hit_count}")
                return None

            def on_context_build(self, context: Dict[str, Any]) -> Dict[str, Any]:
                context[KEY_PROJECT_PLUGIN_TEMPLATE] = int(self._hit_count)
                return context
        """
    )


def _assembly_template() -> str:
    return dedent(
        """\
        # -*- coding: utf-8 -*-
        # Assembly helpers for build_solver (build/apply/attach).

        from __future__ import annotations

        from nsgablack.core.evolution_solver import EvolutionSolver
        from nsgablack.utils.wiring import attach_checkpoint_resume, attach_observability_profile

        from acceleration.config import apply_acceleration_backends
        from bias.domain.config import build_bias
        from evaluation.config import register_evaluation_runtime
        from pipeline.config import build_pipeline
        from plugins.config import (
            build_governance_plugins,
            build_ops_plugins,
            get_checkpoint_spec,
            get_observability_spec,
        )
        from problem.config import build_problem
        from solver.config import apply_solver_profile as apply_solver_profile_cfg


        def build_modeling(cfg, *, problem_key: str, pipeline_key: str, bias_key: str):
            problem = build_problem(cfg.problems, problem_key)
            pipeline = build_pipeline(cfg.pipelines, pipeline_key)
            bias_module = build_bias(cfg.biases, bias_key)
            return problem, pipeline, bias_module


        def apply_solver_profile(solver: EvolutionSolver, cfg, key: str) -> None:
            apply_solver_profile_cfg(solver, cfg.solver_profiles, key)


        def attach_search(solver: EvolutionSolver, adapter: object | None = None) -> None:
            if adapter is not None:
                solver.set_adapter(adapter)


        def attach_acceleration(solver: EvolutionSolver, cfg, keys) -> None:
            apply_acceleration_backends(solver, cfg.acceleration, keys)


        def attach_evaluation(solver: EvolutionSolver, cfg, keys) -> None:
            register_evaluation_runtime(solver, cfg.evaluation, keys)


        def attach_observability(solver: EvolutionSolver, cfg, run_id: str, key: str) -> None:
            obs_spec = get_observability_spec(cfg.observability, key)
            obs_cfg = obs_spec.params
            attach_observability_profile(
                solver,
                profile=str(obs_cfg.get("profile", "default")),
                output_dir=str(obs_cfg.get("run_dir", "runs")),
                run_id=run_id,
                enable_profiler=obs_cfg.get("enable_profiler", None),
                enable_decision_trace=obs_cfg.get("enable_decision_trace", None),
            )


        def attach_governance(solver: EvolutionSolver, cfg, keys) -> None:
            for plugin in build_governance_plugins(cfg.governance_plugins, keys):
                solver.add_plugin(plugin)


        def attach_ops(solver: EvolutionSolver, cfg, keys) -> None:
            for plugin in build_ops_plugins(cfg.ops_plugins, keys):
                solver.add_plugin(plugin)


        def attach_checkpoint(solver: EvolutionSolver, cfg, key: str) -> None:
            ckpt_spec = get_checkpoint_spec(cfg.checkpoint, key)
            ckpt_cfg = ckpt_spec.params
            attach_checkpoint_resume(
                solver,
                checkpoint_dir=str(ckpt_cfg.get("checkpoint_dir", "runs/checkpoints")),
                auto_resume=bool(ckpt_cfg.get("auto_resume", True)),
                strict=bool(ckpt_cfg.get("strict", True)),
                trust_checkpoint=bool(ckpt_cfg.get("trust_checkpoint", False)),
            )
        """
    )


def _project_config_template() -> str:
    return dedent(
        """\
        # -*- coding: utf-8 -*-
        # Project-level configuration aggregator (registries only).

        from __future__ import annotations

        from dataclasses import dataclass

        from problem.config import ProblemRegistry
        from pipeline.config import PipelineRegistry
        from bias.domain.config import BiasRegistry
        from adapter.config import AdapterRegistry
        from solver.config import RuntimeGovernanceRegistry, SolverProfileRegistry, StoreProfileRegistry
        from acceleration.config import AccelerationRegistry
        from evaluation.config import EvaluationRegistry
        from plugins.config import GovernancePluginRegistry, OpsPluginRegistry, ObservabilityRegistry, CheckpointRegistry

        __all__ = ["ProjectConfig", "get_project_config"]


        @dataclass(frozen=True)
        class ProjectConfig:
            problems: ProblemRegistry
            pipelines: PipelineRegistry
            biases: BiasRegistry
            adapters: AdapterRegistry
            solver_profiles: SolverProfileRegistry
            store_profiles: StoreProfileRegistry
            runtime_governance: RuntimeGovernanceRegistry
            acceleration: AccelerationRegistry
            evaluation: EvaluationRegistry
            governance_plugins: GovernancePluginRegistry
            ops_plugins: OpsPluginRegistry
            observability: ObservabilityRegistry
            checkpoint: CheckpointRegistry


        def get_project_config() -> ProjectConfig:
            from acceleration.config import get_acceleration_registry
            from adapter.config import get_adapter_registry
            from bias.domain.config import get_bias_registry
            from evaluation.config import get_evaluation_registry
            from pipeline.config import get_pipeline_registry
            from plugins.config import (
                get_checkpoint_registry,
                get_governance_plugin_registry,
                get_observability_registry,
                get_ops_plugin_registry,
            )
            from problem.config import get_problem_registry
            from solver.config import get_solver_profile_registry
            from solver.config import get_store_profile_registry
            from solver.config import get_runtime_governance_registry

            return ProjectConfig(
                problems=get_problem_registry(),
                pipelines=get_pipeline_registry(),
                biases=get_bias_registry(),
                adapters=get_adapter_registry(),
                solver_profiles=get_solver_profile_registry(),
                store_profiles=get_store_profile_registry(),
                runtime_governance=get_runtime_governance_registry(),
                acceleration=get_acceleration_registry(),
                evaluation=get_evaluation_registry(),
                governance_plugins=get_governance_plugin_registry(),
                ops_plugins=get_ops_plugin_registry(),
                observability=get_observability_registry(),
                checkpoint=get_checkpoint_registry(),
            )
        """
    )


def _run_solver_template() -> str:
    return dedent(
        """\
        # -*- coding: utf-8 -*-
        # CLI entrypoint for running the project scaffold.

        from __future__ import annotations

        import argparse

        from build_solver import build_solver


        def _build_parser() -> argparse.ArgumentParser:
            parser = argparse.ArgumentParser(
                description="Build and run the project scaffold.",
                formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            )
            parser.add_argument(
                "--check",
                action="store_true",
                help="Build and validate assembly only; do not execute solver.run().",
            )
            parser.add_argument("--run-id", default=None, help="Optional run id. Auto-generated when omitted.")
            parser.add_argument("--strategy", default="default", help="Search strategy key (default).")
            parser.add_argument(
                "--quickstart",
                action="store_true",
                help="Use quickstart observability profile.",
            )
            return parser


        def main(argv: list[str] | None = None) -> None:
            parser = _build_parser()
            args = parser.parse_args(argv)
            solver = build_solver(run_id=args.run_id, strategy=args.strategy, quickstart=bool(args.quickstart))
            if bool(args.check):
                plugin_count = len(getattr(getattr(solver, "plugin_manager", None), "plugins", []) or [])
                providers = getattr(getattr(solver, "evaluation_mediator", None), "list_providers", None)
                provider_count = len(tuple(providers())) if callable(providers) else 0
                pipeline = getattr(solver, "representation_pipeline", None)
                mutator_name = type(getattr(pipeline, "mutator", None)).__name__
                print(
                    "[check] assembly ok | "
                    f"problem={type(getattr(solver, 'problem', None)).__name__} | "
                    f"pipeline={type(getattr(solver, 'representation_pipeline', None)).__name__} | "
                    f"mutator={mutator_name} | "
                    f"adapter={type(getattr(solver, 'adapter', None)).__name__} | "
                    f"providers={provider_count} | "
                    f"plugins={plugin_count}"
                )
                return
            result = solver.run(return_dict=True)
            pareto_payload = result.get("pareto_solutions", None)
            if isinstance(pareto_payload, dict):
                objs = pareto_payload.get("objectives")
            else:
                objs = result.get("pareto_objectives", None)
            if objs is not None and len(objs) > 0:
                best_f1 = min(float(row[0]) for row in objs)
                print(f"[example] best_objective_0={best_f1:.6f}")
            else:
                print("[example] run finished but no pareto objectives were returned")


        if __name__ == "__main__":
            main()
        """
    )


def _problem_config_template() -> str:
    return dedent(
        """\
        # -*- coding: utf-8 -*-
        # Problem-layer configuration for this project (registry only).

        from __future__ import annotations

        from dataclasses import dataclass
        from dataclasses import field
        from dataclasses import fields
        from typing import Any, Callable, Dict, Optional

        from .example_problem import ExampleProblem


        @dataclass(frozen=True)
        class ProblemConfig:
            dimension: int = 8


        @dataclass(frozen=True)
        class ProblemSpec:
            key: str
            params: Dict[str, Any] = field(default_factory=dict)


        @dataclass(frozen=True)
        class ProblemRegistry:
            registry: tuple[ProblemSpec, ...] = ()


        def get_problem_registry() -> ProblemRegistry:
            return ProblemRegistry(
                registry=(
                    ProblemSpec(key="example", params={"dimension": 8}),
                )
            )


        ProblemBuilder = Callable[[Dict[str, Any]], object]

        _PROBLEM_BUILDERS: Dict[str, ProblemBuilder] = {}


        def register_problem_builder(key: str, builder: ProblemBuilder) -> None:
            _PROBLEM_BUILDERS[str(key).strip().lower()] = builder


        def _split_config_kwargs(config_cls, params: Dict[str, Any]) -> tuple[object, Dict[str, Any]]:
            if not params:
                return config_cls(), {}
            cfg_fields = {f.name for f in fields(config_cls)}
            cfg_kwargs = {k: v for k, v in params.items() if k in cfg_fields}
            other = {k: v for k, v in params.items() if k not in cfg_fields}
            return config_cls(**cfg_kwargs), other


        def _build_example_problem(cfg: Optional[ProblemConfig] = None) -> ExampleProblem:
            cfg = cfg or ProblemConfig()
            return ExampleProblem(dimension=int(cfg.dimension))


        def _build_with_config(config_cls, params: Dict[str, Any], build_fn: Callable[[object], object]) -> object:
            if "config" in params and isinstance(params["config"], config_cls):
                cfg = params["config"]
                return build_fn(cfg)
            cfg, _ = _split_config_kwargs(config_cls, params)
            return build_fn(cfg)


        def _build_problem_from_spec(spec: ProblemSpec) -> object:
            key = str(spec.key).strip().lower()
            builder = _PROBLEM_BUILDERS.get(key)
            if builder is None:
                raise ValueError(f"Unknown problem key: {spec.key}")
            return builder(dict(spec.params or {}))


        def build_problem(registry: ProblemRegistry, key: str) -> object:
            lookup = str(key).strip().lower()
            for spec in tuple(registry.registry or ()):
                if str(spec.key).strip().lower() == lookup:
                    return _build_problem_from_spec(spec)
            raise ValueError(f"Problem key not registered: {key}")


        def _register_builtin_problems() -> None:
            def _example_builder(params: Dict[str, Any]) -> ExampleProblem:
                return _build_with_config(ProblemConfig, params, _build_example_problem)

            register_problem_builder("example", _example_builder)


        _register_builtin_problems()
        """
    )


def _pipeline_config_template() -> str:
    return dedent(
        """\
        # -*- coding: utf-8 -*-
        # Pipeline-layer configuration for this project (registry only).

        from __future__ import annotations

        from dataclasses import dataclass
        from dataclasses import field
        from dataclasses import fields
        from typing import Any, Callable, Dict, Optional

        from nsgablack.representation import (
            ClipRepair,
            GaussianMutation,
            RepresentationPipeline,
            UniformInitializer,
        )


        @dataclass(frozen=True)
        class PipelineConfig:
            low: float = -5.0
            high: float = 5.0
            mutation_sigma: float = 0.25


        @dataclass(frozen=True)
        class PipelineSpec:
            key: str
            params: Dict[str, Any] = field(default_factory=dict)


        @dataclass(frozen=True)
        class PipelineRegistry:
            registry: tuple[PipelineSpec, ...] = ()


        def get_pipeline_registry() -> PipelineRegistry:
            return PipelineRegistry(
                registry=(
                    PipelineSpec(key="default", params={"low": -5.0, "high": 5.0, "mutation_sigma": 0.25}),
                )
            )


        PipelineBuilder = Callable[[Dict[str, Any]], object]

        _PIPELINE_BUILDERS: Dict[str, PipelineBuilder] = {}


        def register_pipeline_builder(key: str, builder: PipelineBuilder) -> None:
            _PIPELINE_BUILDERS[str(key).strip().lower()] = builder


        def _split_config_kwargs(config_cls, params: Dict[str, Any]) -> tuple[object, Dict[str, Any]]:
            if not params:
                return config_cls(), {}
            cfg_fields = {f.name for f in fields(config_cls)}
            cfg_kwargs = {k: v for k, v in params.items() if k in cfg_fields}
            other = {k: v for k, v in params.items() if k not in cfg_fields}
            return config_cls(**cfg_kwargs), other


        def _build_pipeline_from_config(cfg: Optional[PipelineConfig] = None) -> RepresentationPipeline:
            cfg = cfg or PipelineConfig()
            pipeline = RepresentationPipeline(
                initializer=UniformInitializer(low=cfg.low, high=cfg.high),
                mutator=GaussianMutation(sigma=cfg.mutation_sigma, low=cfg.low, high=cfg.high),
                repair=ClipRepair(low=cfg.low, high=cfg.high),
                encoder=None,
            )
            pipeline.context_requires = ()
            pipeline.context_provides = ()
            pipeline.context_mutates = ()
            pipeline.context_cache = ()
            pipeline.context_notes = "No context read/write in this minimal pipeline."
            return pipeline


        def _build_with_config(config_cls, params: Dict[str, Any], build_fn: Callable[[object], object]) -> object:
            if "config" in params and isinstance(params["config"], config_cls):
                cfg = params["config"]
                return build_fn(cfg)
            cfg, _ = _split_config_kwargs(config_cls, params)
            return build_fn(cfg)


        def _build_pipeline_from_spec(spec: PipelineSpec) -> object:
            key = str(spec.key).strip().lower()
            builder = _PIPELINE_BUILDERS.get(key)
            if builder is None:
                raise ValueError(f"Unknown pipeline key: {spec.key}")
            return builder(dict(spec.params or {}))


        def build_pipeline(registry: PipelineRegistry, key: str) -> object:
            lookup = str(key).strip().lower()
            for spec in tuple(registry.registry or ()):
                if str(spec.key).strip().lower() == lookup:
                    return _build_pipeline_from_spec(spec)
            raise ValueError(f"Pipeline key not registered: {key}")


        def _register_builtin_pipelines() -> None:
            def _default_builder(params: Dict[str, Any]) -> RepresentationPipeline:
                return _build_with_config(PipelineConfig, params, _build_pipeline_from_config)

            register_pipeline_builder("default", _default_builder)


        _register_builtin_pipelines()
        """
    )


def _bias_config_template() -> str:
    return dedent(
        """\
        # -*- coding: utf-8 -*-
        # Bias-layer configuration for this project (registry only).

        from __future__ import annotations

        from dataclasses import dataclass
        from dataclasses import field
        from dataclasses import fields
        from typing import Any, Callable, Dict

        from nsgablack.bias import BiasModule


        @dataclass(frozen=True)
        class BiasConfig:
            enable_bias: bool = False


        @dataclass(frozen=True)
        class BiasSpec:
            key: str
            params: Dict[str, Any] = field(default_factory=dict)


        @dataclass(frozen=True)
        class BiasRegistry:
            registry: tuple[BiasSpec, ...] = ()


        def get_bias_registry() -> BiasRegistry:
            return BiasRegistry(
                registry=(
                    BiasSpec(key="none", params={"enable_bias": False}),
                    BiasSpec(key="default", params={"enable_bias": True}),
                )
            )


        BiasBuilder = Callable[[Dict[str, Any]], object]

        _BIAS_BUILDERS: Dict[str, BiasBuilder] = {}


        def register_bias_builder(key: str, builder: BiasBuilder) -> None:
            _BIAS_BUILDERS[str(key).strip().lower()] = builder


        def _split_config_kwargs(config_cls, params: Dict[str, Any]) -> tuple[object, Dict[str, Any]]:
            if not params:
                return config_cls(), {}
            cfg_fields = {f.name for f in fields(config_cls)}
            cfg_kwargs = {k: v for k, v in params.items() if k in cfg_fields}
            other = {k: v for k, v in params.items() if k not in cfg_fields}
            return config_cls(**cfg_kwargs), other


        def _build_with_config(config_cls, params: Dict[str, Any], build_fn: Callable[..., object]) -> object:
            if "config" in params and isinstance(params["config"], config_cls):
                cfg = params["config"]
                return build_fn(cfg=cfg)
            cfg, _ = _split_config_kwargs(config_cls, params)
            return build_fn(cfg=cfg)


        def _build_bias_from_spec(spec: BiasSpec) -> object:
            key = str(spec.key).strip().lower()
            builder = _BIAS_BUILDERS.get(key)
            if builder is None:
                raise ValueError(f"Unknown bias key: {spec.key}")
            return builder(dict(spec.params or {}))


        def build_bias(registry: BiasRegistry, key: str) -> object:
            lookup = str(key).strip().lower()
            for spec in tuple(registry.registry or ()):
                if str(spec.key).strip().lower() == lookup:
                    return _build_bias_from_spec(spec)
            raise ValueError(f"Bias key not registered: {key}")


        def _register_builtin_biases() -> None:
            from .example_bias import build_bias_module

            def _default_builder(params: Dict[str, Any]) -> BiasModule:
                return _build_with_config(BiasConfig, params, build_bias_module)

            register_bias_builder("default", _default_builder)
            register_bias_builder("none", _default_builder)


        _register_builtin_biases()
        """
    )


def _adapter_example_template() -> str:
    return dedent(
        """\
        # -*- coding: utf-8 -*-
        # Example adapter (simple random proposer).

        from __future__ import annotations

        from typing import Any, Dict, Sequence

        import numpy as np

        from nsgablack.adapters.algorithm_adapter import AlgorithmAdapter


        class ExampleAdapter(AlgorithmAdapter):
            def __init__(self, max_candidates: int = 8, seed: int = 0) -> None:
                super().__init__(name="example_adapter")
                self.max_candidates = max(1, int(max_candidates))
                self._rng = np.random.default_rng(int(seed))

            def propose(self, solver: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
                _ = context
                dim = int(getattr(getattr(solver, "problem", None), "dimension", 1))
                out = []
                for _ in range(self.max_candidates):
                    out.append(self._rng.uniform(-1.0, 1.0, size=(dim,)))
                return out
        """
    )


def _adapter_config_template() -> str:
    return dedent(
        """\
        # -*- coding: utf-8 -*-
        # Search-layer configuration (adapter registry + orchestration defaults).

        from __future__ import annotations

        from dataclasses import dataclass
        from dataclasses import field
        from typing import Any, Callable, Dict, Optional, Sequence

        from nsgablack.adapters import (
            AsyncEventDrivenAdapter,
            AsyncEventDrivenConfig,
            EventStrategySpec,
            MultiStrategyConfig,
            SerialPhaseSpec,
            SerialStrategyConfig,
            StrategyChainAdapter,
            StrategyRouterAdapter,
            StrategySpec,
        )

        from .example_adapter import ExampleAdapter


        @dataclass(frozen=True)
        class AdapterSpec:
            key: str
            params: Dict[str, Any] = field(default_factory=dict)


        @dataclass(frozen=True)
        class OrchestrationDefaults:
            multi: MultiStrategyConfig = field(default_factory=MultiStrategyConfig)
            serial: SerialStrategyConfig = field(default_factory=SerialStrategyConfig)
            event: AsyncEventDrivenConfig = field(default_factory=AsyncEventDrivenConfig)


        @dataclass(frozen=True)
        class AdapterRegistry:
            registry: tuple[AdapterSpec, ...] = ()
            orchestration: OrchestrationDefaults = field(default_factory=OrchestrationDefaults)


        def get_adapter_registry() -> AdapterRegistry:
            return AdapterRegistry(
                registry=(
                    AdapterSpec(key="example_adapter", params={"max_candidates": 8, "seed": 0}),
                )
            )


        AdapterBuilder = Callable[[Dict[str, Any]], object]

        _ADAPTER_BUILDERS: Dict[str, AdapterBuilder] = {}


        def register_adapter_builder(key: str, builder: AdapterBuilder) -> None:
            _ADAPTER_BUILDERS[str(key).strip().lower()] = builder


        def _find_spec(registry: AdapterRegistry, key: str) -> Optional[AdapterSpec]:
            lookup = str(key).strip().lower()
            for spec in tuple(registry.registry or ()):
                if str(spec.key).strip().lower() == lookup:
                    return spec
            return None


        def build_adapter_instance(registry: AdapterRegistry, adapter_key: str) -> object | None:
            spec = _find_spec(registry, adapter_key)
            if spec is None:
                return None
            key = str(spec.key).strip().lower()
            builder = _ADAPTER_BUILDERS.get(key)
            if builder is None:
                raise ValueError(f"Unknown adapter key: {spec.key}")
            params = dict(spec.params or {})
            return builder(params)


        def require_adapter(registry: AdapterRegistry, adapter_key: str) -> object:
            adapter = build_adapter_instance(registry, adapter_key)
            if adapter is None:
                raise ValueError(f"Adapter key not registered: {adapter_key}")
            return adapter


        # --- Orchestration language (pure compose, no parameter setting) -----------
        ValueRef = Any | Callable[[dict], Any]
        Cond = Callable[[dict], bool]


        def val(value: Any) -> Callable[[dict], Any]:
            return lambda _c: value


        def _resolve(ref: ValueRef, ctx: dict) -> Any:
            return ref(ctx) if callable(ref) else ref


        def _safe(op: Callable[[Any, Any], bool], left: ValueRef, right: ValueRef) -> Cond:
            def _fn(c: dict) -> bool:
                try:
                    return bool(op(_resolve(left, c), _resolve(right, c)))
                except Exception:
                    return False

            return _fn


        def all_of(*conds: Cond) -> Cond:
            return lambda c: all(bool(cond(c)) for cond in conds)


        def any_of(*conds: Cond) -> Cond:
            return lambda c: any(bool(cond(c)) for cond in conds)


        def not_(cond: Cond) -> Cond:
            return lambda c: not bool(cond(c))


        def _ctx_get(ctx: dict, path: str) -> Any:
            cur: Any = ctx
            for part in str(path).split("."):
                if isinstance(cur, dict) and part in cur:
                    cur = cur.get(part)
                    continue
                return None
            return cur


        def ctx(path: str) -> Callable[[dict], Any]:
            return lambda c: _ctx_get(c, path)


        def truthy(ref: ValueRef) -> Cond:
            return lambda c: bool(_resolve(ref, c))


        def exists(ref: ValueRef) -> Cond:
            return lambda c: _resolve(ref, c) is not None


        def eq(left: ValueRef, right: ValueRef) -> Cond:
            return _safe(lambda a, b: a == b, left, right)


        def ne(left: ValueRef, right: ValueRef) -> Cond:
            return _safe(lambda a, b: a != b, left, right)


        def gt(left: ValueRef, right: ValueRef) -> Cond:
            return _safe(lambda a, b: a > b, left, right)


        def ge(left: ValueRef, right: ValueRef) -> Cond:
            return _safe(lambda a, b: a >= b, left, right)


        def lt(left: ValueRef, right: ValueRef) -> Cond:
            return _safe(lambda a, b: a < b, left, right)


        def le(left: ValueRef, right: ValueRef) -> Cond:
            return _safe(lambda a, b: a <= b, left, right)


        def in_(left: ValueRef, right: ValueRef) -> Cond:
            return _safe(lambda a, b: a in b, left, right)


        def not_in(left: ValueRef, right: ValueRef) -> Cond:
            return _safe(lambda a, b: a not in b, left, right)


        def between(value: ValueRef, low: ValueRef, high: ValueRef) -> Cond:
            return all_of(ge(value, low), le(value, high))


        def custom(fn: Callable[[dict], bool]) -> Cond:
            return fn


        def group(registry: AdapterRegistry, name: str, adapter_keys: Sequence[str]) -> object:
            specs: list[StrategySpec] = []
            for key in adapter_keys:
                adapter = require_adapter(registry, key)
                specs.append(StrategySpec(adapter=adapter, name=str(key)))
            if len(specs) == 1:
                return specs[0].adapter
            base_cfg = registry.orchestration.multi or MultiStrategyConfig()
            return StrategyRouterAdapter(strategies=specs, config=base_cfg, name=str(name))


        def multi(registry: AdapterRegistry, name: str, adapters: Sequence[object]) -> object:
            items = [a for a in adapters if a is not None]
            if len(items) == 1:
                return items[0]
            specs = [StrategySpec(adapter=a, name=getattr(a, "name", f"adapter_{i}")) for i, a in enumerate(items)]
            base_cfg = registry.orchestration.multi or MultiStrategyConfig()
            return StrategyRouterAdapter(strategies=specs, config=base_cfg, name=str(name))


        def phase(name: str, adapter: object, *, steps: int = -1, advance_when: Cond | None = None):
            return SerialPhaseSpec(name=str(name), adapter=adapter, steps=int(steps), advance_when=advance_when)


        def serial(registry: AdapterRegistry, name: str, phases: Sequence[SerialPhaseSpec]) -> object:
            items = [p for p in phases if p is not None]
            if len(items) == 1:
                return items[0].adapter
            base_cfg = registry.orchestration.serial or SerialStrategyConfig()
            return StrategyChainAdapter(phases=items, config=base_cfg, name=str(name))


        def event(registry: AdapterRegistry, name: str, adapters: Sequence[object]) -> object:
            items = [a for a in adapters if a is not None]
            if len(items) == 1:
                return items[0]
            specs = [
                EventStrategySpec(adapter=a, name=getattr(a, "name", f"adapter_{i}"), weight=1.0, enabled=True)
                for i, a in enumerate(items)
            ]
            base_cfg = registry.orchestration.event or AsyncEventDrivenConfig()
            return AsyncEventDrivenAdapter(strategies=specs, config=base_cfg, name=str(name))


        # --- Example: registering a new adapter ------------------------------------
        @dataclass(frozen=True)
        class ExampleAdapterConfig:
            max_candidates: int = 8
            seed: int = 0


        def build_example_adapter(cfg: ExampleAdapterConfig) -> ExampleAdapter:
            return ExampleAdapter(max_candidates=cfg.max_candidates, seed=cfg.seed)


        def _register_builtin_adapters() -> None:
            register_adapter_builder("example_adapter", lambda p: ExampleAdapter(**p))


        _register_builtin_adapters()
        """
    )


def _acceleration_config_template() -> str:
    return dedent(
        """\
        # -*- coding: utf-8 -*-
        # L0 acceleration configuration for this project (registry only).

        from __future__ import annotations

        from dataclasses import dataclass
        from dataclasses import field
        from typing import Any, Dict, Sequence

        from nsgablack.core import GpuBackend, ProcessPoolBackend, ThreadPoolBackend


        @dataclass(frozen=True)
        class AccelerationSpec:
            key: str
            params: Dict[str, Any] = field(default_factory=dict)


        @dataclass(frozen=True)
        class AccelerationRegistry:
            registry: tuple[AccelerationSpec, ...] = ()


        def get_acceleration_registry() -> AccelerationRegistry:
            return AccelerationRegistry(
                registry=(
                    AccelerationSpec(key="thread", params={"scope": "evaluation", "workers": None}),
                    AccelerationSpec(key="process", params={"scope": "evaluation", "workers": None}),
                    AccelerationSpec(key="gpu", params={"scope": "evaluation", "gpu_backend": "auto", "gpu_device": "cuda:0"}),
                )
            )


        def _find_spec(registry: AccelerationRegistry, key: str) -> AccelerationSpec:
            lookup = str(key).strip().lower()
            for spec in tuple(registry.registry or ()):
                if str(spec.key).strip().lower() == lookup:
                    return spec
            raise ValueError(f"Acceleration key not registered: {key}")


        def _set_default_backend(solver, scope: str, backend: str) -> None:
            setter = getattr(solver, "set_acceleration_default_backend", None)
            if callable(setter):
                setter(scope=scope, backend=backend)


        def _register_backend(solver, spec: AccelerationSpec) -> tuple[str, str] | None:
            key = str(spec.key).strip().lower()
            params = dict(spec.params or {})
            scope = str(params.pop("scope", "evaluation"))
            if key == "thread":
                solver.register_acceleration_backend(
                    scope=scope,
                    backend="thread",
                    factory=lambda: ThreadPoolBackend(max_workers=params.get("workers")),
                )
                return scope, "thread"
            if key == "process":
                solver.register_acceleration_backend(
                    scope=scope,
                    backend="process",
                    factory=lambda: ProcessPoolBackend(max_workers=params.get("workers")),
                )
                return scope, "process"
            if key == "gpu":
                solver.register_acceleration_backend(
                    scope=scope,
                    backend="gpu",
                    factory=lambda: GpuBackend(
                        preferred_backend=str(params.get("gpu_backend", "auto")),
                        device=str(params.get("gpu_device", "cuda:0")),
                    ),
                )
                return scope, "gpu"
            if key == "none":
                return None
            raise ValueError(f"Unknown acceleration backend key: {spec.key}")


        def apply_acceleration_backends(
            solver,
            registry: AccelerationRegistry,
            keys: Sequence[str],
        ) -> None:
            default_set = False
            first_registered: tuple[str, str] | None = None
            for key in keys:
                spec = _find_spec(registry, key)
                reg = _register_backend(solver, spec)
                if reg is None:
                    continue
                if first_registered is None:
                    first_registered = reg
                params = dict(spec.params or {})
                if bool(params.get("default")):
                    _set_default_backend(solver, scope=reg[0], backend=reg[1])
                    default_set = True
            if not default_set and first_registered is not None:
                _set_default_backend(solver, scope=first_registered[0], backend=first_registered[1])
        """
    )


def _evaluation_config_template() -> str:
    return dedent(
        """\
        # -*- coding: utf-8 -*-
        # L4 evaluation runtime configuration (provider registry only).

        from __future__ import annotations

        from dataclasses import dataclass
        from dataclasses import field
        from typing import Any, Callable, Dict, Sequence


        @dataclass(frozen=True)
        class EvaluationSpec:
            key: str
            params: Dict[str, Any] = field(default_factory=dict)


        @dataclass(frozen=True)
        class EvaluationRegistry:
            registry: tuple[EvaluationSpec, ...] = ()


        def get_evaluation_registry() -> EvaluationRegistry:
            return EvaluationRegistry(registry=())


        ProviderBuilder = Callable[[Dict[str, Any]], object]

        _EVAL_PROVIDER_BUILDERS: Dict[str, ProviderBuilder] = {}


        def register_evaluation_provider_builder(key: str, builder: ProviderBuilder) -> None:
            _EVAL_PROVIDER_BUILDERS[str(key).strip().lower()] = builder


        def _find_spec(registry: EvaluationRegistry, key: str) -> EvaluationSpec:
            lookup = str(key).strip().lower()
            for spec in tuple(registry.registry or ()):
                if str(spec.key).strip().lower() == lookup:
                    return spec
            raise ValueError(f"Evaluation provider key not registered: {key}")


        def _build_provider_from_spec(spec: EvaluationSpec) -> object:
            key = str(spec.key).strip().lower()
            builder = _EVAL_PROVIDER_BUILDERS.get(key)
            if builder is None:
                raise ValueError(f"Unknown evaluation provider key: {spec.key}")
            params = dict(spec.params or {})
            return builder(params)


        def build_evaluation_providers(registry: EvaluationRegistry, keys: Sequence[str]) -> list[object]:
            providers: list[object] = []
            for key in keys:
                spec = _find_spec(registry, key)
                providers.append(_build_provider_from_spec(spec))
            return providers


        def register_evaluation_runtime(solver, registry: EvaluationRegistry, keys: Sequence[str]) -> None:
            register = getattr(solver, "register_evaluation_provider", None)
            if not callable(register):
                return
            for provider in build_evaluation_providers(registry, keys):
                register(provider)
        """
    )


def _solver_config_template() -> str:
    return dedent(
        """\
        # -*- coding: utf-8 -*-
        # Solver-core configuration for this project (registry only).

        from __future__ import annotations

        from dataclasses import dataclass
        from dataclasses import field
        from dataclasses import fields
        from typing import Any, Callable, Dict

        from nsgablack.core.evolution_solver import EvolutionSolver
        from nsgablack.core.runtime_governance import (
            AdaptiveParametersConfig,
            AdaptiveParametersGovernor,
            CompanionOrchestrator,
            CompanionOrchestratorConfig,
            ConvergenceConfig,
            ConvergenceMonitor,
        )


        @dataclass(frozen=True)
        class SolverCoreConfig:
            pop_size: int = 80
            max_generations: int = 60
            mutation_rate: float = 0.2
            crossover_rate: float = 0.8
            enable_progress_log: bool = True
            report_interval: int = 6
            thread_bias_isolation: str = "deepcopy"
            plugin_strict: bool = False


        @dataclass(frozen=True)
        class SolverProfileSpec:
            key: str
            params: Dict[str, Any] = field(default_factory=dict)


        @dataclass(frozen=True)
        class SolverProfileRegistry:
            registry: tuple[SolverProfileSpec, ...] = ()


        def get_solver_profile_registry() -> SolverProfileRegistry:
            return SolverProfileRegistry(
                registry=(
                    SolverProfileSpec(
                        key="default",
                        params={
                            "pop_size": 80,
                            "max_generations": 60,
                            "mutation_rate": 0.2,
                            "crossover_rate": 0.8,
                            "enable_progress_log": True,
                            "report_interval": 6,
                            "thread_bias_isolation": "deepcopy",
                            "plugin_strict": False,
                        },
                    ),
                )
            )


        ProfileBuilder = Callable[[Dict[str, Any]], SolverCoreConfig]

        _SOLVER_PROFILE_BUILDERS: Dict[str, ProfileBuilder] = {}


        def register_solver_profile_builder(key: str, builder: ProfileBuilder) -> None:
            _SOLVER_PROFILE_BUILDERS[str(key).strip().lower()] = builder


        def _split_config_kwargs(config_cls, params: Dict[str, Any]) -> tuple[object, Dict[str, Any]]:
            if not params:
                return config_cls(), {}
            cfg_fields = {f.name for f in fields(config_cls)}
            cfg_kwargs = {k: v for k, v in params.items() if k in cfg_fields}
            other = {k: v for k, v in params.items() if k not in cfg_fields}
            return config_cls(**cfg_kwargs), other


        def _build_profile_from_spec(spec: SolverProfileSpec) -> SolverCoreConfig:
            key = str(spec.key).strip().lower()
            builder = _SOLVER_PROFILE_BUILDERS.get(key)
            if builder is None:
                raise ValueError(f"Unknown solver profile key: {spec.key}")
            return builder(dict(spec.params or {}))


        def build_solver_profile(registry: SolverProfileRegistry, key: str) -> SolverCoreConfig:
            lookup = str(key).strip().lower()
            for spec in tuple(registry.registry or ()):
                if str(spec.key).strip().lower() == lookup:
                    return _build_profile_from_spec(spec)
            raise ValueError(f"Solver profile key not registered: {key}")


        def apply_solver_core_config(solver, cfg: SolverCoreConfig) -> None:
            solver.pop_size = int(cfg.pop_size)
            solver.max_generations = int(cfg.max_generations)
            solver.mutation_rate = float(cfg.mutation_rate)
            solver.crossover_rate = float(cfg.crossover_rate)
            solver.enable_progress_log = bool(cfg.enable_progress_log)
            solver.report_interval = int(cfg.report_interval)
            solver.parallel_thread_bias_isolation = str(cfg.thread_bias_isolation)
            if hasattr(solver, "plugin_manager") and getattr(solver, "plugin_manager", None) is not None:
                try:
                    solver.plugin_manager.strict = bool(cfg.plugin_strict)
                except Exception:
                    pass


        def apply_solver_profile(solver, registry: SolverProfileRegistry, key: str) -> None:
            cfg = build_solver_profile(registry, key)
            apply_solver_core_config(solver, cfg)


        def _register_builtin_solver_profiles() -> None:
            def _default_builder(params: Dict[str, Any]) -> SolverCoreConfig:
                cfg, _ = _split_config_kwargs(SolverCoreConfig, params)
                return cfg

            register_solver_profile_builder("default", _default_builder)


        _register_builtin_solver_profiles()


        # --- Runtime governance (built-in L3) --------------------------------------
        @dataclass(frozen=True)
        class RuntimeGovernanceConfig:
            enable_convergence_monitor: bool = False
            convergence: ConvergenceConfig = field(default_factory=ConvergenceConfig)
            enable_adaptive_parameters: bool = False
            adaptive: AdaptiveParametersConfig = field(default_factory=AdaptiveParametersConfig)
            enable_companion_orchestrator: bool = False
            companion: CompanionOrchestratorConfig = field(default_factory=CompanionOrchestratorConfig)


        @dataclass(frozen=True)
        class RuntimeGovernanceSpec:
            key: str
            params: Dict[str, Any] = field(default_factory=dict)


        @dataclass(frozen=True)
        class RuntimeGovernanceRegistry:
            registry: tuple[RuntimeGovernanceSpec, ...] = ()


        def get_runtime_governance_registry() -> RuntimeGovernanceRegistry:
            return RuntimeGovernanceRegistry(
                registry=(
                    RuntimeGovernanceSpec(
                        key="default",
                        params={
                            "enable_convergence_monitor": False,
                            "enable_adaptive_parameters": False,
                            "enable_companion_orchestrator": False,
                            "convergence": {},
                            "adaptive": {},
                            "companion": {},
                        },
                    ),
                )
            )


        def _coerce_runtime_cfg(value: Any, cfg_cls):
            if value is None:
                return cfg_cls()
            if isinstance(value, cfg_cls):
                return value
            if isinstance(value, dict):
                return cfg_cls(**value)
            return cfg_cls()


        def _build_runtime_governance_profile(spec: RuntimeGovernanceSpec) -> RuntimeGovernanceConfig:
            params = dict(spec.params or {})
            return RuntimeGovernanceConfig(
                enable_convergence_monitor=bool(params.get("enable_convergence_monitor", False)),
                enable_adaptive_parameters=bool(params.get("enable_adaptive_parameters", False)),
                enable_companion_orchestrator=bool(params.get("enable_companion_orchestrator", False)),
                convergence=_coerce_runtime_cfg(params.get("convergence"), ConvergenceConfig),
                adaptive=_coerce_runtime_cfg(params.get("adaptive"), AdaptiveParametersConfig),
                companion=_coerce_runtime_cfg(params.get("companion"), CompanionOrchestratorConfig),
            )


        def build_runtime_governance_profile(registry: RuntimeGovernanceRegistry, key: str) -> RuntimeGovernanceConfig:
            lookup = str(key).strip().lower()
            for spec in tuple(registry.registry or ()):
                if str(spec.key).strip().lower() == lookup:
                    return _build_runtime_governance_profile(spec)
            raise ValueError(f"Runtime governance profile key not registered: {key}")


        # --- Store profile (context/snapshot backends) ------------------------------
        @dataclass(frozen=True)
        class StoreProfile:
            context_store_backend: str = "memory"  # memory | redis
            context_store_redis_url: str = "redis://localhost:6379/0"
            context_store_key_prefix: str = "nsgablack:context"
            context_store_ttl_seconds: float | None = None

            snapshot_store_backend: str = "memory"  # memory | file | redis
            snapshot_store_redis_url: str = "redis://localhost:6379/0"
            snapshot_store_key_prefix: str = "nsgablack:snapshot"
            snapshot_store_ttl_seconds: float | None = None
            snapshot_store_dir: str | None = None
            snapshot_store_serializer: str = "safe"
            snapshot_store_hmac_env_var: str = "NSGABLACK_SNAPSHOT_HMAC_KEY"
            snapshot_store_unsafe_allow_unsigned: bool = False
            snapshot_store_max_payload_bytes: int = 8_388_608
            snapshot_schema: str = "population_snapshot_v1"


        @dataclass(frozen=True)
        class StoreProfileSpec:
            key: str
            params: Dict[str, Any] = field(default_factory=dict)


        @dataclass(frozen=True)
        class StoreProfileRegistry:
            registry: tuple[StoreProfileSpec, ...] = ()


        def get_store_profile_registry() -> StoreProfileRegistry:
            return StoreProfileRegistry(
                registry=(
                    StoreProfileSpec(
                        key="default",
                        params={
                            "context_store_backend": "memory",
                            "snapshot_store_backend": "memory",
                        },
                    ),
                )
            )


        def _build_store_profile(spec: StoreProfileSpec) -> StoreProfile:
            cfg, other = _split_config_kwargs(StoreProfile, dict(spec.params or {}))
            if other:
                raise ValueError(f"Unknown store profile params: {sorted(other.keys())}")
            return cfg


        def build_store_profile(registry: StoreProfileRegistry, key: str) -> StoreProfile:
            lookup = str(key).strip().lower()
            for spec in tuple(registry.registry or ()):
                if str(spec.key).strip().lower() == lookup:
                    return _build_store_profile(spec)
            raise ValueError(f"Store profile key not registered: {key}")


        def build_evolution_solver(
            problem: Any,
            *,
            bias_module: Any = None,
        ) -> EvolutionSolver:
            return EvolutionSolver(
                problem,
                bias_module=bias_module,
            )


        def apply_store_profile(solver, registry: StoreProfileRegistry, key: str) -> None:
            store = build_store_profile(registry, key)
            setter_ctx = getattr(solver, "set_context_store_backend", None)
            if callable(setter_ctx):
                setter_ctx(
                    backend=str(store.context_store_backend),
                    ttl_seconds=store.context_store_ttl_seconds,
                    redis_url=str(store.context_store_redis_url),
                    key_prefix=str(store.context_store_key_prefix),
                )
            setter_snap = getattr(solver, "set_snapshot_store_backend", None)
            if callable(setter_snap):
                setter_snap(
                    backend=str(store.snapshot_store_backend),
                    ttl_seconds=store.snapshot_store_ttl_seconds,
                    redis_url=str(store.snapshot_store_redis_url),
                    key_prefix=str(store.snapshot_store_key_prefix),
                    base_dir=store.snapshot_store_dir,
                    serializer=str(store.snapshot_store_serializer),
                    hmac_env_var=str(store.snapshot_store_hmac_env_var),
                    unsafe_allow_unsigned=bool(store.snapshot_store_unsafe_allow_unsigned),
                    max_payload_bytes=int(store.snapshot_store_max_payload_bytes),
                )
            if hasattr(solver, "snapshot_schema"):
                solver.snapshot_schema = str(store.snapshot_schema)


        def apply_runtime_governance(
            solver,
            registry: RuntimeGovernanceRegistry,
            key: str,
        ) -> None:
            cfg = build_runtime_governance_profile(registry, key)
            if bool(cfg.enable_convergence_monitor):
                solver._convergence_monitor = ConvergenceMonitor(cfg.convergence)
            else:
                solver._convergence_monitor = None
            if bool(cfg.enable_adaptive_parameters):
                solver._adaptive_governor = AdaptiveParametersGovernor(cfg.adaptive)
            else:
                solver._adaptive_governor = None
            if bool(cfg.enable_companion_orchestrator):
                solver._companion_orchestrator = CompanionOrchestrator(cfg.companion)
            else:
                solver._companion_orchestrator = None
            hook = getattr(solver, "_runtime_governance_on_solver_init", None)
            if callable(hook):
                hook()
        """
    )


def _plugins_config_template() -> str:
    return dedent(
        """\
        # -*- coding: utf-8 -*-
        # Plugin-layer configuration for this project (registries only).

        from __future__ import annotations

        from dataclasses import dataclass
        from dataclasses import field
        from dataclasses import fields
        from typing import Any, Callable, Dict, Sequence

        from .example_plugin import ExampleProjectPlugin


        @dataclass(frozen=True)
        class PluginSpec:
            key: str
            params: Dict[str, Any] = field(default_factory=dict)


        @dataclass(frozen=True)
        class GovernancePluginRegistry:
            registry: tuple[PluginSpec, ...] = ()


        @dataclass(frozen=True)
        class OpsPluginRegistry:
            registry: tuple[PluginSpec, ...] = ()


        def get_governance_plugin_registry() -> GovernancePluginRegistry:
            return GovernancePluginRegistry(registry=())


        def get_ops_plugin_registry() -> OpsPluginRegistry:
            return OpsPluginRegistry(
                registry=(
                    PluginSpec(key="example_plugin", params={"interval": 5, "verbose": True}),
                )
            )


        PluginBuilder = Callable[[Dict[str, Any]], object]


        def _split_config_kwargs(config_cls, params: Dict[str, Any]) -> tuple[object, Dict[str, Any]]:
            if not params:
                return config_cls(), {}
            cfg_fields = {f.name for f in fields(config_cls)}
            cfg_kwargs = {k: v for k, v in params.items() if k in cfg_fields}
            other = {k: v for k, v in params.items() if k not in cfg_fields}
            return config_cls(**cfg_kwargs), other


        def _build_simple(plugin_cls, params: Dict[str, Any]):
            return plugin_cls(**(params or {}))


        def _build_example_plugin(params: Dict[str, Any]) -> object:
            return _build_simple(ExampleProjectPlugin, params)


        _GOVERNANCE_PLUGIN_BUILDERS: Dict[str, PluginBuilder] = {}
        _OPS_PLUGIN_BUILDERS: Dict[str, PluginBuilder] = {
            "example_plugin": _build_example_plugin,
        }


        def register_governance_plugin_builder(key: str, builder: PluginBuilder) -> None:
            _GOVERNANCE_PLUGIN_BUILDERS[str(key).strip().lower()] = builder


        def register_ops_plugin_builder(key: str, builder: PluginBuilder) -> None:
            _OPS_PLUGIN_BUILDERS[str(key).strip().lower()] = builder


        def _find_spec(registry: Sequence[PluginSpec], key: str) -> PluginSpec:
            lookup = str(key).strip().lower()
            for spec in tuple(registry or ()):
                if str(spec.key).strip().lower() == lookup:
                    return spec
            raise ValueError(f"Plugin key not registered: {key}")


        def _build_plugin_from_spec(spec: PluginSpec, builders: Dict[str, PluginBuilder]) -> object:
            key = str(spec.key).strip().lower()
            builder = builders.get(key)
            if builder is None:
                raise ValueError(f"Unknown plugin key: {spec.key}")
            params = dict(spec.params or {})
            return builder(params)


        def build_governance_plugins(registry: GovernancePluginRegistry, keys: Sequence[str]) -> list[object]:
            plugins: list[object] = []
            for key in keys:
                spec = _find_spec(registry.registry, key)
                plugins.append(_build_plugin_from_spec(spec, _GOVERNANCE_PLUGIN_BUILDERS))
            return plugins


        def build_ops_plugins(registry: OpsPluginRegistry, keys: Sequence[str]) -> list[object]:
            plugins: list[object] = []
            for key in keys:
                spec = _find_spec(registry.registry, key)
                plugins.append(_build_plugin_from_spec(spec, _OPS_PLUGIN_BUILDERS))
            return plugins


        # --- Observability + checkpoint registries ---------------------------------
        @dataclass(frozen=True)
        class ObservabilitySpec:
            key: str
            params: Dict[str, Any] = field(default_factory=dict)


        @dataclass(frozen=True)
        class ObservabilityRegistry:
            registry: tuple[ObservabilitySpec, ...] = ()


        def get_observability_registry() -> ObservabilityRegistry:
            return ObservabilityRegistry(
                registry=(
                    ObservabilitySpec(
                        key="default",
                        params={
                            "profile": "default",
                            "enable_profiler": None,
                            "enable_decision_trace": None,
                            "run_dir": "runs",
                        },
                    ),
                    ObservabilitySpec(
                        key="quickstart",
                        params={
                            "profile": "quickstart",
                            "enable_profiler": None,
                            "enable_decision_trace": None,
                            "run_dir": "runs",
                        },
                    ),
                )
            )


        @dataclass(frozen=True)
        class CheckpointSpec:
            key: str
            params: Dict[str, Any] = field(default_factory=dict)


        @dataclass(frozen=True)
        class CheckpointRegistry:
            registry: tuple[CheckpointSpec, ...] = ()


        def get_checkpoint_registry() -> CheckpointRegistry:
            return CheckpointRegistry(
                registry=(
                    CheckpointSpec(
                        key="default",
                        params={
                            "checkpoint_dir": "runs/checkpoints",
                            "auto_resume": True,
                            "strict": True,
                            "trust_checkpoint": False,
                        },
                    ),
                )
            )


        def get_observability_spec(registry: ObservabilityRegistry, key: str) -> ObservabilitySpec:
            lookup = str(key).strip().lower()
            for spec in tuple(registry.registry or ()):
                if str(spec.key).strip().lower() == lookup:
                    return spec
            raise ValueError(f"Observability key not registered: {key}")


        def get_checkpoint_spec(registry: CheckpointRegistry, key: str) -> CheckpointSpec:
            lookup = str(key).strip().lower()
            for spec in tuple(registry.registry or ()):
                if str(spec.key).strip().lower() == lookup:
                    return spec
            raise ValueError(f"Checkpoint key not registered: {key}")
        """
    )


def _catalog_project_registry_template() -> str:
    return dedent(
        """\
        # -*- coding: utf-8 -*-
        # Project-local Catalog registration.
        # Preferred local registration source is `catalog/entries.toml`.

        from __future__ import annotations

        def get_project_entries():
            return []
        """
    )


def _project_registry_template() -> str:
    return dedent(
        """\
        # -*- coding: utf-8 -*-
        # Project-local Catalog registration.
        # Preferred local registration source is `catalog/entries.toml`.

        from __future__ import annotations

        def get_project_entries():
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
        companions = ["project.pipeline.default"]
        context_requires = []
        context_provides = []
        context_mutates = []
        context_cache = []
        context_notes = ["Defines objective/constraint semantics only; no runtime context writes."]
        use_when = ["Define project objective/constraint semantics."]
        minimal_wiring = ["from problem.example_problem import ExampleProblem"]
        required_companions = ["project.pipeline.default"]
        config_keys = ["dimension"]
        example_entry = "build_solver:build_solver"

        [[entry]]
        key = "project.pipeline.default"
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
        key = "project.bias.default"
        title = "build_bias_module"
        kind = "bias"
        import_path = "bias.domain.example_bias:build_bias_module"
        tags = ["project", "example", "bias"]
        summary = "Example bias module (empty by default)."
        companions = ["project.problem.example"]
        context_requires = []
        context_provides = []
        context_mutates = []
        context_cache = []
        context_notes = ["Bias is empty by default; add soft preferences here."]
        use_when = ["Need a project bias module entry."]
        minimal_wiring = ["from bias.domain.example_bias import build_bias_module"]
        required_companions = []
        config_keys = ["enable_bias"]
        example_entry = "build_solver:build_solver"

        [[entry]]
        key = "project.adapter.example"
        title = "ExampleAdapter"
        kind = "adapter"
        import_path = "adapter.example_adapter:ExampleAdapter"
        tags = ["project", "example", "adapter"]
        summary = "Example adapter that proposes random candidates."
        companions = ["project.problem.example", "project.pipeline.default"]
        context_requires = []
        context_provides = []
        context_mutates = []
        context_cache = []
        context_notes = ["Adapter template for propose/update integration."]
        use_when = ["Need a minimal adapter starting point."]
        minimal_wiring = ["from adapter.example_adapter import ExampleAdapter"]
        required_companions = []
        config_keys = ["max_candidates", "seed"]
        example_entry = "build_solver:build_solver"

        [[entry]]
        key = "project.plugin.example"
        title = "ExampleProjectPlugin"
        kind = "plugin"
        import_path = "plugins.example_plugin:ExampleProjectPlugin"
        tags = ["project", "example", "plugin"]
        summary = "Example plugin template with explicit context contracts."
        companions = ["project.solver.build"]
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
        required_companions = ["project.solver.build"]
        config_keys = ["interval", "verbose"]
        example_entry = "build_solver:build_solver"

        [[entry]]
        key = "project.solver.build"
        title = "build_solver"
        kind = "example"
        import_path = "build_solver:build_solver"
        tags = ["project", "example", "solver"]
        summary = "Example solver assembly entry."
        companions = ["project.problem.example", "project.pipeline.default"]
        context_requires = []
        context_provides = []
        context_mutates = []
        context_cache = []
        context_notes = ["Assembly entrypoint; context contract is delegated to registered components."]
        use_when = ["Need runnable assembly entry for CLI and Run Inspector."]
        minimal_wiring = ["python run_solver.py"]
        required_companions = ["project.problem.example", "project.pipeline.default"]
        config_keys = ["dimension", "pop_size", "generations", "enable_bias"]
        example_entry = "build_solver:build_solver"
        """
    )


def _build_solver_template() -> str:
    return dedent(
        """\
        # -*- coding: utf-8 -*-
        # Project build_solver entry (my_project-style layout).

        from __future__ import annotations

        import argparse
        from datetime import datetime

        from adapter.config import event, group, phase, serial
        from assembly import (
            apply_solver_profile,
            attach_acceleration,
            attach_checkpoint,
            attach_evaluation,
            attach_governance,
            attach_observability,
            attach_ops,
            attach_search,
            build_modeling,
        )
        from config import get_project_config
        from solver.config import apply_runtime_governance, apply_store_profile, build_evolution_solver


        def _normalize_strategy(value: str | None) -> str:
            if value is None:
                return "default"
            return str(value).strip().lower()


        def build_solver(
            run_id: str | None = None,
            *,
            strategy: str | None = None,
            quickstart: bool = False,
        ):
            cfg = get_project_config()
            strategy_key = _normalize_strategy(strategy)

            # --- Modeling -----------------------------------------------------
            problem, pipeline, bias_module = build_modeling(
                cfg,
                problem_key="example",
                pipeline_key="default",
                bias_key="none",
            )
            solver = build_evolution_solver(problem, bias_module=bias_module)
            apply_store_profile(solver, cfg.store_profiles, "default")
            apply_runtime_governance(solver, cfg.runtime_governance, "default")
            solver.set_representation_pipeline(pipeline)

            # --- Core ---------------------------------------------------------
            apply_solver_profile(solver, cfg, "default")

            # --- Search orchestration (built-in) ------------------------------
            if strategy_key not in {"", "default", "none"}:
                search_adapter = build_search(cfg.adapters, primary_key=strategy_key, mode="single")
                attach_search(solver, search_adapter)

            # --- L0 -----------------------------------------------------------
            attach_acceleration(solver, cfg, ())

            # --- L4 -----------------------------------------------------------
            attach_evaluation(solver, cfg, ())

            # --- L3 Governance ------------------------------------------------
            attach_governance(solver, cfg, ())

            # --- L1/L2 Observability + Ops -----------------------------------
            run_id = str(run_id) if run_id else datetime.now().strftime("%Y%m%d_%H%M%S")
            obs_profile = "quickstart" if bool(quickstart) else "default"
            attach_observability(solver, cfg, run_id, obs_profile)
            attach_ops(solver, cfg, ())

            # Optional checkpoint
            # attach_checkpoint(solver, cfg, "default")
            return solver


        # --- Search orchestration (built-in) --------------------------------------
        def build_search(registry, *, primary_key: str, mode: str) -> object | None:
            base = group(registry, "primary", [primary_key])
            mode = str(mode or "single").lower()
            if "serial" in mode or "multi" in mode:
                phases = [phase("primary", base)]
                return serial(registry, "search_flow", phases)
            if "event" in mode:
                return event(registry, "event_flow", [base])
            return base


        def _build_parser() -> argparse.ArgumentParser:
            parser = argparse.ArgumentParser(
                description="Build and run the project scaffold.",
                formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            )
            parser.add_argument(
                "--check",
                action="store_true",
                help="Build and validate assembly only; do not execute solver.run().",
            )
            parser.add_argument("--run-id", default=None, help="Optional run id. Auto-generated when omitted.")
            parser.add_argument(
                "--strategy",
                default="default",
                help="Search strategy key (default).",
            )
            parser.add_argument(
                "--quickstart",
                action="store_true",
                help="Use quickstart observability profile.",
            )
            return parser


        def main(argv: list[str] | None = None) -> None:
            parser = _build_parser()
            args = parser.parse_args(argv)
            solver = build_solver(run_id=args.run_id, strategy=args.strategy, quickstart=bool(args.quickstart))
            if bool(args.check):
                plugin_count = len(getattr(getattr(solver, "plugin_manager", None), "plugins", []) or [])
                providers = getattr(getattr(solver, "evaluation_mediator", None), "list_providers", None)
                provider_count = len(tuple(providers())) if callable(providers) else 0
                pipeline = getattr(solver, "representation_pipeline", None)
                mutator_name = type(getattr(pipeline, "mutator", None)).__name__
                print(
                    "[check] assembly ok | "
                    f"problem={type(getattr(solver, 'problem', None)).__name__} | "
                    f"pipeline={type(getattr(solver, 'representation_pipeline', None)).__name__} | "
                    f"mutator={mutator_name} | "
                    f"adapter={type(getattr(solver, 'adapter', None)).__name__} | "
                    f"providers={provider_count} | "
                    f"plugins={plugin_count}"
                )
                return
            result = solver.run(return_dict=True)
            pareto_payload = result.get("pareto_solutions", None)
            if isinstance(pareto_payload, dict):
                objs = pareto_payload.get("objectives")
            else:
                objs = result.get("pareto_objectives", None)
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
        """\
        # BUILD_SOLVER_REGISTRATION

        This guide summarizes the recommended assembly order in `build_solver.py`.

        ## Order
        1. build_modeling (problem + pipeline + bias)
        2. build_evolution_solver
        3. apply store + runtime governance profiles
        4. apply solver profile
        5. attach search adapter (optional)
        6. attach acceleration (L0)
        7. attach evaluation runtime (L4)
        8. attach governance plugins (L3)
        9. attach observability + ops plugins (L1/L2)
        10. attach checkpoint (optional)

        ## Notes
        - Keep parameters in registries; keep selection here.
        - Keep algorithm semantics out of plugins.
        - Use `project doctor --build` after edits.
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
        if name not in _NON_PACKAGE_FOLDERS:
            _write_file(folder / "__init__.py", "", overwrite=force)
        if name == "adapter":
            _write_file(folder / "README.md", _adapter_readme(), overwrite=force)
        elif name == "plugins":
            _write_file(folder / "README.md", _plugin_readme(), overwrite=force)
        else:
            _write_file(folder / "README.md", _readme_for_folder(name), overwrite=force)

    # Subpackages for the my_project-style layout.
    for parent, subs in {
        "bias": ("algorithmic", "domain"),
        "plugins": ("observability", "checkpoint"),
        "problem": ("data", "evaluation"),
    }.items():
        base = root / parent
        for sub in subs:
            folder = base / sub
            folder.mkdir(parents=True, exist_ok=True)
            _write_file(folder / "__init__.py", "", overwrite=force)

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
    _write_file(root / "catalog" / "project_registry.py", _catalog_project_registry_template(), overwrite=force)
    _write_file(root / "assembly.py", _assembly_template(), overwrite=force)
    _write_file(root / "config.py", _project_config_template(), overwrite=force)
    _write_file(root / "run_solver.py", _run_solver_template(), overwrite=force)
    _write_file(root / "build_solver.py", _build_solver_template(), overwrite=force)

    _write_file(root / "problem" / "config.py", _problem_config_template(), overwrite=force)
    _write_file(root / "problem" / "example_problem.py", _problem_template(), overwrite=force)
    _write_file(root / "problem" / "template_problem.py", _problem_class_template(), overwrite=force)

    _write_file(root / "pipeline" / "config.py", _pipeline_config_template(), overwrite=force)
    _write_file(root / "pipeline" / "example_pipeline.py", _pipeline_template(), overwrite=force)
    _write_file(root / "pipeline" / "template_pipeline.py", _pipeline_class_template(), overwrite=force)

    _write_file(root / "bias" / "domain" / "config.py", _bias_config_template(), overwrite=force)
    _write_file(root / "bias" / "domain" / "example_bias.py", _bias_template(), overwrite=force)
    _write_file(root / "bias" / "template_bias.py", _bias_class_template(), overwrite=force)

    _write_file(root / "adapter" / "config.py", _adapter_config_template(), overwrite=force)
    _write_file(root / "adapter" / "example_adapter.py", _adapter_example_template(), overwrite=force)
    _write_file(root / "adapter" / "template_adapter.py", _adapter_class_template(), overwrite=force)

    _write_file(root / "acceleration" / "config.py", _acceleration_config_template(), overwrite=force)
    _write_file(root / "evaluation" / "config.py", _evaluation_config_template(), overwrite=force)
    _write_file(root / "solver" / "config.py", _solver_config_template(), overwrite=force)

    _write_file(root / "plugins" / "config.py", _plugins_config_template(), overwrite=force)
    _write_file(root / "plugins" / "example_plugin.py", _plugin_template(), overwrite=force)
    _write_file(root / "plugins" / "template_plugin.py", _plugin_class_template(), overwrite=force)
    (root / ".vscode").mkdir(parents=True, exist_ok=True)
    _write_file(root / ".vscode" / "nsgablack.code-snippets", _vscode_snippets_template(), overwrite=force)

    return root
