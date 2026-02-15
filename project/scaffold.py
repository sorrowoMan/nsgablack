# -*- coding: utf-8 -*-
"""Project scaffolding."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from typing import Dict


_FOLDERS = [
    "problem",
    "pipeline",
    "bias",
    "adapter",
    "plugins",
    "data",
    "assets",
]


_FOLDER_DESCRIPTIONS: Dict[str, str] = {
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

        {desc}

        ## Boundary
        - Keep only this layer's responsibility.
        - Do not hide cross-layer logic inside this folder.

        ## Input / Output Contract
        - Input: data source, parameters, context fields read.
        - Output: return objects, context fields written, side effects.
        - If context is used, prefer explicit declaration:
          `context_requires/context_provides/context_mutates/context_cache`.

        ## Minimal Example
        - Keep at least one runnable file, or point to the entry file path here.
        """
    )


def _root_readme(project_name: str) -> str:
    return dedent(
        f"""\
        # {project_name}

        NSGABlack local project scaffold.

        ## Structure
        - `problem/`: problem definition
        - `pipeline/`: representation + hard constraints
        - `bias/`: soft preference
        - `adapter/`: strategy orchestration (optional)
        - `plugins/`: engineering capabilities (optional)
        - `data/`: project input data
        - `assets/`: outputs

        ## Recommended Flow
        1. Read `START_HERE.md`.
        2. Read `COMPONENT_REGISTRATION.md`.
        3. Run `python -m nsgablack project doctor --path . --build`.
        4. Use `build_solver.py` as the single assembly entry.

        ## Entry Files
        - `build_solver.py`: wire problem/pipeline/bias/strategy
        - `project_registry.py`: project-local Catalog registration
        - `COMPONENT_REGISTRATION.md`: what/why/how to register components
        """
    )


def _start_here() -> str:
    return dedent(
        """\
        # START_HERE

        6-step bootstrap for a new project.

        ## Step 1 - Health check first
        ```powershell
        python -m nsgablack project doctor --path . --build
        ```
        - Read `COMPONENT_REGISTRATION.md` first if you will add new reusable components.

        ## Step 2 - Implement problem
        - File: `problem/example_problem.py`
        - Required:
          - `evaluate(x)` returns objective vector (`numpy.ndarray`)
          - `evaluate_constraints(x)` returns violation vector (empty if no constraints)

        ## Step 3 - Implement pipeline
        - File: `pipeline/example_pipeline.py`
        - Keep hard feasibility in this layer.

        ## Step 4 - Add bias if needed
        - File: `bias/example_bias.py`
        - Bias should encode preference, not hard constraints.

        ## Step 5 - Assemble only
        - File: `build_solver.py`
        - Keep it as wiring, avoid re-implementing framework internals.

        ## Step 6 - Run and inspect
        ```powershell
        python build_solver.py
        python -m nsgablack project catalog list --path .
        ```

        ## Optional
        - Run Inspector: `python -m nsgablack run_inspector --entry build_solver.py:build_solver`
        - Include global catalog in search:
          `python -m nsgablack project catalog search vns --path . --global`
        """
    )


def _component_registration_guide() -> str:
    return dedent(
        """\
        # COMPONENT_REGISTRATION

        This file defines the local project registration contract.

        ## Why register components
        - Make components discoverable in Catalog and Run Inspector.
        - Keep assembly reproducible (`build_solver.py` + stable keys).
        - Make context read/write behavior auditable (`context_*` fields).

        ## What should be registered
        Register reusable components that may be searched, toggled, or reused:
        - problem builders
        - pipelines / biases / adapters / plugins
        - solver assembly entries

        Do not register one-off helper scripts or private debug code.

        ## Where to register
        - Local project entries: `project_registry.py`
        - Local keys should be short; loader auto-prefixes with `project.`
          (example: `pipeline.example` -> `project.pipeline.example`)

        ## Minimal entry contract
        Each `CatalogEntry` should include:
        - `key`, `kind`, `title`, `import_path`
        - `tags`, `summary`
        - `context_requires`, `context_provides`, `context_mutates`, `context_cache`
        - `use_when`, `minimal_wiring`, `required_companions`, `config_keys`, `example_entry`

        Usage fields are mandatory for discoverability UX.
        Context fields are mandatory for contract auditability.
        If omitted, framework may infer defaults, but CI/doctor should treat this as non-compliant.

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

        ## Validation
        Run after changing registry entries:
        ```powershell
        python -m nsgablack project doctor --path . --build --strict
        python -m nsgablack project catalog list --path .
        python tools/catalog_integrity_checker.py --check-usage --strict-usage --check-context --context-kinds plugin --require-context-notes --strict-context
        ```

        ## Scope in UI
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


def _adapter_readme() -> str:
    return dedent(
        """\
        # adapter

        Strategy layer for propose/update search logic.

        ## Notes
        - Typical projects can start without custom adapters.
        - Add adapter only when default solver loop is not enough.

        ## Recommended context declaration
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

        Engineering plugin layer: logging, parallelism, monitor, replay, storage.

        ## Notes
        - Keep plugins focused on capabilities, not core problem modeling.
        - Prefer explicit context contracts for each plugin.

        ## Typical starters
        - `BenchmarkHarnessPlugin`
        - `ModuleReportPlugin`
        - `BoundaryGuardPlugin`
        """
    )


def _project_registry_template() -> str:
    return dedent(
        """\
        # -*- coding: utf-8 -*-
        \"\"\"Project-local Catalog registration.\"\"\"

        from __future__ import annotations

        from nsgablack.catalog import CatalogEntry


        def get_project_entries():
            return [
                CatalogEntry(
                    key="problem.example",
                    title="ExampleProblem",
                    kind="tool",
                    import_path="problem.example_problem:ExampleProblem",
                    tags=("project", "example", "problem"),
                    summary="Example two-objective problem.",
                    context_requires=(),
                    context_provides=(),
                    context_mutates=(),
                    context_cache=(),
                    context_notes=("Defines objective/constraint semantics only; no runtime context writes.",),
                    use_when=("Define project objective/constraint semantics.",),
                    minimal_wiring=("from problem.example_problem import ExampleProblem",),
                    required_companions=("project.pipeline.example",),
                    config_keys=("dimension",),
                    example_entry="build_solver:build_solver",
                ),
                CatalogEntry(
                    key="pipeline.example",
                    title="build_pipeline",
                    kind="representation",
                    import_path="pipeline.example_pipeline:build_pipeline",
                    tags=("project", "example", "pipeline"),
                    summary="Example representation pipeline.",
                    companions=("project.problem.example",),
                    context_requires=(),
                    context_provides=(),
                    context_mutates=(),
                    context_cache=(),
                    context_notes=("Pipeline handles init/mutate/repair; no additional runtime context keys.",),
                    use_when=("Need init/mutate/repair wiring for vector representation.",),
                    minimal_wiring=(
                        "from pipeline.example_pipeline import build_pipeline",
                        "solver.set_representation_pipeline(build_pipeline())",
                    ),
                    required_companions=("project.problem.example",),
                    config_keys=(),
                    example_entry="build_solver:build_solver",
                ),
                CatalogEntry(
                    key="solver.example",
                    title="build_solver",
                    kind="example",
                    import_path="build_solver:build_solver",
                    tags=("project", "example", "solver"),
                    summary="Example solver assembly entry.",
                    companions=("project.problem.example", "project.pipeline.example"),
                    context_requires=(),
                    context_provides=(),
                    context_mutates=(),
                    context_cache=(),
                    context_notes=("Assembly entrypoint; context contract is delegated to registered components.",),
                    use_when=("Need runnable assembly entry for CLI and Run Inspector.",),
                    minimal_wiring=("python build_solver.py",),
                    required_companions=("project.problem.example", "project.pipeline.example"),
                    config_keys=("dimension", "pop_size", "generations", "enable_bias"),
                    example_entry="build_solver:build_solver",
                ),
            ]
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
        from problem.example_problem import ExampleProblem


        def build_solver(argv: list[str] | None = None) -> BlackBoxSolverNSGAII:
            parser = argparse.ArgumentParser(add_help=False)
            parser.add_argument("--dimension", type=int, default=8)
            parser.add_argument("--pop-size", type=int, default=80)
            parser.add_argument("--generations", type=int, default=60)
            parser.add_argument("--enable-bias", action="store_true")
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
    _write_file(root / "build_solver.py", _build_solver_template(), overwrite=force)
    _write_file(root / "problem" / "example_problem.py", _problem_template(), overwrite=force)
    _write_file(root / "pipeline" / "example_pipeline.py", _pipeline_template(), overwrite=force)
    _write_file(root / "bias" / "example_bias.py", _bias_template(), overwrite=force)

    return root
