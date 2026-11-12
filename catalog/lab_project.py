"""Bounded Lab specifications exported through the formal Project scaffold.

Preview, download and trial execution use the same generated source.  No user
code, paths, import names or command strings are accepted by this module.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from functools import lru_cache
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

SPEC_SCHEMA = "nsgablack.lab.spec/v1"
REPORT_SCHEMA = "nsgablack.lab.report/v1"

_COMMON_PARAMETERS = {
    "seed": {"label": "随机种子", "type": "int", "min": 0, "max": 2147483647},
    "dimension": {"label": "候选维度", "type": "int", "min": 2, "max": 8},
    "initial_count": {"label": "母池初始解数", "type": "int", "min": 1, "max": 64},
    "max_steps": {"label": "逻辑提交步数上限", "type": "int", "min": 1, "max": 50},
}
_POPULATION_PARAMETER = {
    "population_size": {"label": "算法种群大小", "type": "int", "min": 4, "max": 24},
}
_STAGE_PARAMETERS = {
    "ga_steps": {"label": "GA 搜索步数", "type": "int", "min": 1, "max": 8},
    "local_steps": {"label": "每个成员的 VNS 步数（含起点评估）", "type": "int", "min": 1, "max": 4},
}
_COMMON_COMPONENTS = ["repr.continuous"]
_RECIPES = (
    dict(id="ga", title="GA / NSGA-II 种群搜索", description="从母池取初值，交叉后变异，按原生非支配排序与拥挤度留存。",
         components=["adapter.nsga2", *_COMMON_COMPONENTS],
         defaults=dict(seed=17, dimension=2, initial_count=12, population_size=6, max_steps=8),
         parameters={**_COMMON_PARAMETERS, **_POPULATION_PARAMETER}),
    dict(id="vns", title="VNS 单点邻域搜索", description="从母池取一个初值；当前点和邻域由 VNS Unit 维护，原始双目标保留。",
         components=["adapter.vns", *_COMMON_COMPONENTS],
         defaults=dict(seed=17, dimension=2, initial_count=12, max_steps=8),
         parameters=_COMMON_PARAMETERS),
    dict(id="moead", title="MOEA/D 方向分解搜索", description="按权重方向搜索并自动发布带实例来源的目标投影子池。",
         components=["adapter.moead", *_COMMON_COMPONENTS],
         defaults=dict(seed=17, dimension=2, initial_count=12, population_size=6, max_steps=8),
         parameters={**_COMMON_PARAMETERS, **_POPULATION_PARAMETER}),
    dict(id="ga_vns", title="GA → VNS → GA 返回竞争", description="GA 成员视图交给 VNS 逐个精修；本次最终选择回到 GA 原生生存竞争。",
         components=["adapter.nsga2", "adapter.vns", "adapter.search_plan", *_COMMON_COMPONENTS],
         defaults=dict(seed=17, dimension=2, initial_count=12, population_size=6,
                       max_steps=16, ga_steps=2, local_steps=2),
         parameters={**_COMMON_PARAMETERS, **_POPULATION_PARAMETER, **_STAGE_PARAMETERS}),
)


def list_recipes() -> tuple[dict, ...]:
    """Return detached UI metadata; it is not another executable registry."""
    return deepcopy(_RECIPES)


def normalize_spec(value: Mapping) -> dict:
    """Validate a closed data schema, refusing coercion and irrelevant fields."""
    if not isinstance(value, Mapping):
        raise TypeError("实验配置必须是对象")
    from .lab_assembly import ASSEMBLY_SCHEMA, normalize_assembly
    if value.get("schema") == ASSEMBLY_SCHEMA:
        return normalize_assembly(value)
    raw = dict(value)
    if any(not isinstance(key, str) for key in raw):
        raise ValueError("实验配置的键必须是字符串")
    if raw.get("schema", SPEC_SCHEMA) != SPEC_SCHEMA:
        raise ValueError("不支持的实验配置 schema")
    recipe_id = raw.get("recipe", "ga")
    recipe = next((row for row in _RECIPES if row["id"] == recipe_id), None)
    if recipe is None:
        raise ValueError("未知配方；请选择 ga、vns、moead 或 ga_vns")
    allowed = {"schema", "recipe", *recipe["parameters"]}
    unknown = set(raw).difference(allowed)
    if unknown:
        raise ValueError("不支持的参数：" + ", ".join(sorted(unknown)))
    normalized = {"schema": SPEC_SCHEMA, "recipe": recipe_id, **recipe["defaults"]}
    normalized.update(raw)
    for name, rule in recipe["parameters"].items():
        item = normalized[name]
        if type(item) is not int or not rule["min"] <= item <= rule["max"]:
            raise ValueError(f"{name} 必须是 {rule['min']} 到 {rule['max']} 的整数")
    if "population_size" in normalized and normalized["initial_count"] < normalized["population_size"]:
        raise ValueError("母池初始解数不能少于本配方的种群大小；不会自动补足")
    return normalized


def _source(text: str) -> str:
    return dedent(text).lstrip("\n").rstrip() + "\n"


_PROJECT_CONFIG = _source('''
    """Project 独占 L0 授权；Case 内只装配算法。"""
    L0 = {
        "namespace": "algorithm_lab",
        "offer": {"threads": 1, "gpus": 0, "backend": "local", "device_tokens": []},
        "policy": {"mode": "strict", "gpu_sharing": "exclusive", "cpu_oversubscribe": False},
        "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
        "compute_backend": "auto", "execution_backend": "local",
    }
    STAGES = [{"name": "search", "cases": ["search"], "policy": "serial",
               "resource_requests": {"search": {"threads": 1, "gpus": 0, "backend": "local"}}}]
    GROUPS = {"default": {"stages": ["search"]}}
''')

_PROBLEM = _source('''
    """可直接修改的原始双目标问题；不在此定义算法选择偏好。"""
    import numpy as np
    from nsgablack.core import BlackBoxProblem


    class TwoCenters(BlackBoxProblem):
        def __init__(self, dimension):
            super().__init__(name="lab_two_centers", dimension=dimension,
                             bounds=[(-2., 2.)] * dimension, objectives=["left", "right"])

        def evaluate(self, x):
            x = np.asarray(x, dtype=float)
            left, right = np.zeros(self.dimension), np.zeros(self.dimension)
            left[0], right[0] = -1., 1.
            return [float(np.sum((x - left) ** 2)), float(np.sum((x - right) ** 2))]


    def build_problem(dimension):
        return TwoCenters(dimension)
''')

_PIPELINE = _source('''
    """问题候选源与问题修复；不创建算法 Unit。"""
    from nsgablack.representation import ClipRepair, RepresentationPipeline, UniformInitializer


    def build_pipeline(*, resource_context=None, component_overrides=None):
        del resource_context, component_overrides
        return RepresentationPipeline(initializer=UniformInitializer(-2., 2.),
                                      repair=ClipRepair(-2., 2.))
''')

_CHANGE = _source('''
    """用户可编辑的普通变化函数；框架拥有评估、接纳和事务。"""
    import numpy as np
    from nsgablack.adapters import ChangeBatchResult, ChangeResult


    def ga_change(request, *, rng):
        """两父代掩码交叉，再加小幅高斯变异。"""
        a, b = request.parents[:2]
        mask = rng.random(a.shape) < .5
        children = (np.where(mask, a, b), np.where(mask, b, a))
        return ChangeBatchResult(tuple(ChangeResult(
            child + rng.normal(0., .12, child.shape), source_refs=request.source_refs[:2])
            for child in children[:min(2, request.max_outputs)]))


    def vns_change(request, *, rng):
        """当前点邻域变化；VNS 仍拥有邻域切换和接受规则。"""
        return ChangeResult(request.candidate + rng.normal(
            0., float(request.parameters["sigma"]), request.candidate.shape))


    def moead_change(request, *, rng):
        """在该方向给出的父代上重组；方向比较不在变化函数里重写。"""
        center = np.mean(request.parents, axis=0)
        return ChangeResult(.7 * request.candidate + .3 * center
                            + rng.normal(0., .12, request.candidate.shape))
''')

_ADAPTER = _source('''
    """装配原生算法与 PoolTask；不编写第二套搜索循环。"""
    from nsgablack.adapters import (MOEADAdapter, MultiStrategyConfig, NSGA2Adapter,
        PoolTaskAdapter, PoolTaskSpec, RoleSpec, StrategyRouterAdapter, StrategySpec, VNSAdapter, subpools)
    from nsgablack.adapters.search_plan import SearchPlanAdapter, serial, stage
    from .changes import ga_change, moead_change, vns_change


    def current_refinement_results(control, context):
        del context
        return control.adapter.get_pool_task_results(control, "vns")


    def build_adapter(settings):
        recipe = settings["recipe"]
        size = settings.get("population_size", 1)
        cfg = MultiStrategyConfig(total_batch_size=max(size, 2), adapt_weights=False)
        if recipe in {"ga", "ga_vns"}:
            ga = NSGA2Adapter(name="ga", population_size=size, offspring_size=size, change=ga_change)
        if recipe in {"vns", "ga_vns"}:
            vns = VNSAdapter(name="vns", batch_size=1, k_max=3, base_sigma=.15,
                             scale=1.7, max_sigma=.7, restart_on_stagnation=False,
                             change=vns_change)
        if recipe == "ga_vns":
            # 初始化和返回竞争是两个明确输入位置，仍只拥有同一个 GA 实例。
            # 外层竞争任务仅在 return 启用；内层初始化任务完成后透明转发。
            ga_search = ga
            ga = PoolTaskAdapter(ga_search, PoolTaskSpec(mode="initialize", count=size,
                phases=("ga",), shuffle=False), role="ga_seed", namespace="lab")
            return SearchPlanAdapter(serial(
                stage("ga", steps=settings["ga_steps"], label="ga"),
                stage("vns", label="vns"), stage("ga", label="return")),
                strategies=[
                    StrategySpec(name="ga", adapter=ga, pool_task=PoolTaskSpec(
                        current_refinement_results, mode="compete", phases=("return",),
                        count="all", shuffle=False)),
                    StrategySpec(name="vns", adapter=vns, pool_task=PoolTaskSpec(
                        subpools.all(ga_search), mode="refine", count="all",
                        steps=settings["local_steps"], shuffle=False))],
                config=cfg, name="ga_vns")
        if recipe == "moead":
            leaf = MOEADAdapter(name="moead", population_size=size, batch_size=2,
                neighborhood_size=min(size, 4), decomposition="weighted_sum",
                random_seed=settings["seed"], change=moead_change)
        else:
            leaf = ga if recipe == "ga" else vns
        return StrategyRouterAdapter(name="lab_search", roles=[RoleSpec("search", leaf,
            pool_task=PoolTaskSpec(mode="initialize", count=size, shuffle=False))], config=cfg)
''')

_BUILD = _source('''
    """唯一装配真相；预览、试跑和下载均使用这一份源码。"""
    from pathlib import Path
    from nsgablack.core import ComposableSolver
    from nsgablack.project import apply_solver_component_overrides
    from .adapter import build_adapter
    from .config import SPEC
    from .pipeline import build_pipeline
    from .plugins import PipelineSource, LabReport
    from .problem import build_problem


    def build_solver(config=None, *, resource_context=None, component_overrides=None):
        settings = {**SPEC, **dict(config or {})}
        solver = ComposableSolver(problem=build_problem(settings["dimension"]),
            representation_pipeline=build_pipeline(), adapter=build_adapter(settings),
            resource_context=resource_context, plugin_strict=True, snapshot_strict=True)
        solver.set_random_seed(settings["seed"])
        solver.set_max_steps(settings["max_steps"])
        solver.add_plugin(PipelineSource(settings["initial_count"]))
        solver.add_plugin(LabReport(settings, Path(__file__).resolve().parents[2] / "results"))
        apply_solver_component_overrides(solver, component_overrides)
        return solver
''')

_PLUGINS = _source('''
    """启动源和只读报告；不改算法选择，不分配全局资源。"""
    from collections.abc import Mapping
    import json
    from blackbase.participation import ParticipationContract
    from nsgablack.plugins.base import Plugin
    from nsgablack.adapters.subpools import adapter_path
    from nsgablack.utils.engineering.file_io import atomic_write_text


    def detached(value):
        return json.loads(json.dumps(value, allow_nan=False, default=lambda item:
            item.tolist() if hasattr(item, "tolist") else item.as_dict()))


    class PipelineSource(Plugin):
        participation = ParticipationContract()
        state_recovery_level = "L1"
        state_recovery_notes = "Explicit run identity and completed initialization state."
        context_notes = ("Pipeline supplies seeds before Adapter initialization; no Unit creation.",)

        def __init__(self, count):
            super().__init__(name="lab_pipeline_source")
            self.count, self.run_id, self.seeded = count, None, False

        def on_solver_init(self, solver):
            if self.run_id == solver.run_session.run_id and self.seeded:
                return
            if solver.run_session.resume_loaded:
                raise ValueError("restored run is missing its completed seed state")
            self.run_id, self.seeded = solver.run_session.run_id, False
            solver.init_population(self.count, solver.build_context())
            self.seeded = True

        def get_state(self):
            return {"count": self.count, "run_id": self.run_id, "seeded": self.seeded}

        def set_state(self, state):
            if (not isinstance(state, Mapping) or state.get("count") != self.count
                    or type(state.get("seeded")) is not bool):
                raise ValueError("invalid source state")
            self.run_id, self.seeded = state.get("run_id"), state["seeded"]


    class LabReport(Plugin):
        participation = ParticipationContract(vetoes=("finalization",))
        state_recovery_level = "L1"
        state_recovery_notes = "Bounded JSON committed observations; final report uses Project publication."
        context_notes = ("Observes Pool and existing Unit only; never calls ensure_unit or evaluate.",)

        def __init__(self, spec, output_dir):
            super().__init__(name="lab_report")
            self.spec, self.output_dir = dict(spec), output_dir
            self.run_id, self.records, self.initial, self.payload = None, [], None, None

        def observe(self):
            solver, pool = self.solver, self.solver.solution_pool
            units = []

            def visit(adapter, path):
                unit = getattr(adapter, "algorithm_unit", None)
                population = getattr(unit, "population", None)
                units.append({"path": "/".join(path), "type": type(adapter).__name__,
                    "unit_exists": unit is not None,
                    "current_exists": getattr(adapter, "current_unit", None) is not None,
                    "population_members": 0 if population is None else len(population),
                    "published_views": list(pool.subpools_created_by(
                        adapter_path(solver.adapter, adapter)))})
                for index, child in enumerate(adapter.step_transaction_children()):
                    visit(child, (*path, f"{index}:{child.name}"))

            visit(solver.adapter, (solver.adapter.name,))
            refs = pool.select(stage="accepted")
            raw_f, raw_v = pool.read_raw_feedback(refs)
            best = None if not len(refs) else float(raw_f.sum(axis=1).min())
            feasible = raw_v <= 0.
            feasible_count = int(feasible.sum())
            best_feasible = None if not feasible_count else float(raw_f[feasible].sum(axis=1).min())
            projection = solver.adapter.get_runtime_context_projection(solver)
            tasks = projection.get("unit_tasks", {})
            phases = sorted({item["phase"] for item in tasks.values() if "phase" in item})
            return {"steps": int(solver.run_progress_steps),
                "evaluations": int(solver.evaluation_count), "accepted_count": len(refs),
                "pool_records": int(pool.record_count), "best_raw_sum": best,
                "feasible_count": feasible_count, "best_feasible_raw_sum": best_feasible,
                "phases": phases, "units": units}

        def on_solver_init(self, solver):
            if self.run_id != solver.run_session.run_id:
                self.run_id, self.records, self.payload = solver.run_session.run_id, [], None
                self.initial = self.observe()

        def on_generation_committed(self, generation, outcome):
            del generation
            if not outcome.get("committed", False) or len(self.records) >= self.spec["max_steps"]:
                raise ValueError("report only accepts bounded committed steps")
            self.records.append(self.observe())

        def on_solver_finalization_prepare(self, result):
            del result
            solver, pool = self.solver, self.solver.solution_pool
            final = self.observe()
            refs = pool.select(stage="accepted")[-128:]
            raw_f, raw_v = pool.read_raw_feedback(refs)
            runtime = solver.case_runtime
            if runtime is None:
                raise ValueError("Lab report requires the formal Project/Case artifact authority")
            self.payload = detached({"schema": "nsgablack.lab.report/v1", "spec": self.spec,
                "project_identity": runtime.identity.as_dict(), "run_id": self.run_id,
                "steps": final["steps"], "evaluations": final["evaluations"],
                "initial": self.initial, "records": self.records, "units": final["units"],
                "pool": {"records": final["pool_records"], "accepted_count": final["accepted_count"],
                         "initial_count": len(pool.select(stage="initial")),
                         "views": [{"descriptor": pool.subpool_descriptor(name),
                                    "metadata": pool.subpool_metadata(name),
                                    "members": len(pool.subpool_refs(name))}
                                   for name in pool.published_subpool_names()]},
                "plan_completed": (solver.adapter.cursor.completed
                                   if hasattr(solver.adapter, "cursor") else None),
                "resource_binding_audit": getattr(solver, "resource_binding_audit", {}),
                "result": {"scope": "last_128_accepted", "refs": [ref.as_dict() for ref in refs],
                    "candidates": pool.read(refs).numeric_matrix.tolist(),
                    "raw_objectives": raw_f.tolist(), "raw_violations": raw_v.tolist()}})
            runtime.publish_artifact("lab_report", self.payload, serializer="json",
                kind="lab_report", media_type="application/json",
                metadata={"schema": self.payload["schema"], "recipe": self.spec["recipe"]})

        def on_solver_finalized(self, result):
            del result
            if self.payload is None:
                raise ValueError("finalized report was not prepared")
            # 展示副本；权威版本与发布收据位于 Project Artifact ledger。
            atomic_write_text(self.output_dir / "lab_report.json",
                              json.dumps(self.payload, ensure_ascii=False, indent=2, allow_nan=False))

        def get_state(self):
            return detached({"spec": self.spec, "run_id": self.run_id,
                             "initial": self.initial, "records": self.records})

        def set_state(self, state):
            if (not isinstance(state, Mapping) or state.get("spec") != self.spec
                    or not isinstance(state.get("records"), list)
                    or len(state["records"]) > self.spec["max_steps"]):
                raise ValueError("invalid Lab report checkpoint")
            saved = detached(dict(state))
            self.run_id, self.initial, self.records = saved["run_id"], saved["initial"], saved["records"]
            self.payload = None
''')


def _overlay(spec: dict) -> dict[str, str]:
    from .lab_assembly import ASSEMBLY_SCHEMA, assembly_overlay
    if spec.get("schema") == ASSEMBLY_SCHEMA:
        return assembly_overlay(spec)
    recipe = next(row for row in _RECIPES if row["id"] == spec["recipe"])
    readme = f"""# 算法实验台导出项目

本项目使用正式 Project → Case → Scaffold；Project 的 L0 给 Case 授权一个 CPU 线程。
配方：**{recipe['title']}**。{recipe['description']}

## 运行

在已安装匹配版本 nsgablack / blackbase 的 Python 环境中运行；不会自动安装依赖。

```shell
python run_project.py --check --build-check
python run_project.py
```

官方运行记录：`.blackbase/runs/<run-id>/manifest.json`。
`lab_report` Artifact 经 Case 发布事务交付，`results/lab_report.json` 是方便查看的相同内容副本。

## 修改位置

- `cases/search/config.py`：实际参数，与 `lab_spec.json` 相同。
- `cases/search/build_solver.py`：唯一装配入口。
- `cases/search/problem/__init__.py`：原始双目标；边界 [-2,2]，左/右中心为 (-1,0,...) 与 (1,0,...)。
- `cases/search/pipeline/main.py`：初值源与问题修复。
- `cases/search/adapter/changes.py`：普通变化函数；可以直接编辑，无需写新 Adapter 基类。
- `cases/search/adapter/__init__.py`：算法装配、PoolTask 输入与搜索计划。
- `cases/search/plugins/__init__.py`：先将初值放进母池，再只读记录结果。

母池初值数量、算法种群大小、后代批次与历史存储量是独立概念。
Unit 由实际 Adapter 懒创建，观察不会创建 Unit。原始双目标不会被 VNS 的目标和或 MOEA/D 方向评分覆盖。
组合配方是 GA → VNS → GA 返回竞争：VNS 从 GA 精确成员视图逐项精修，当前任务的最终引用回到 GA 比较。
`max_steps` 是独立提交预算；过小可提前结束计划，报告 `plan_completed` 会明确体现。
本版不执行浏览器上传的任意 Python；下载后可在自己的环境中修改这些正式源码。
"""
    return {
        "project_config.py": _PROJECT_CONFIG,
        "lab_spec.json": json.dumps(spec, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        "README.md": readme,
        "cases/search/README.md": "# search\n\n本 Case 的正式装配与运行说明见项目根 README.md。\n",
        "cases/search/config.py": '"""本 Case 的实际实验参数。"""\nSPEC = ' + repr(spec) + "\n",
        "cases/search/build_solver.py": _BUILD,
        "cases/search/problem/__init__.py": _PROBLEM,
        "cases/search/pipeline/main.py": _PIPELINE,
        "cases/search/pipeline/__init__.py": "from .main import build_pipeline\n",
        "cases/search/adapter/__init__.py": _ADAPTER,
        "cases/search/adapter/changes.py": _CHANGE,
        "cases/search/plugins/__init__.py": _PLUGINS,
    }


@lru_cache(maxsize=32)
def _render_files(canonical: str) -> tuple[tuple[str, str], ...]:
    from nsgablack.project.scaffold import add_case, create_project

    spec = json.loads(canonical)
    with TemporaryDirectory(prefix="nsgablack-lab-export-") as scratch:
        root = create_project(Path(scratch) / "algorithm_lab")
        add_case("search", "solver", project_root=root)
        for relative, source in _overlay(spec).items():
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source, encoding="utf-8", newline="\n")
        return tuple((path.relative_to(root).as_posix(), path.read_text(encoding="utf-8"))
                     for path in sorted(root.rglob("*")) if path.is_file())


def preview_files(spec: Mapping, *, design_notes="") -> dict[str, str]:
    """Produce the exact exported source without importing a generated Case."""
    normalized = normalize_spec(spec)
    canonical = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    files = dict(_render_files(canonical))
    from .lab_design import normalize_notes
    design_notes = normalize_notes(design_notes)
    if design_notes:
        from .lab_design import export_design_markdown, export_workspace
        files["DESIGN.md"] = export_design_markdown(design_notes)
        files["lab_workspace.json"] = export_workspace(normalized, design_notes=design_notes).decode("utf-8")
    return files


def export_project(spec: Mapping, destination: Path, *, design_notes="") -> Path:
    """Write a new standard Project, refusing any existing target directory."""
    files = preview_files(spec, design_notes=design_notes)
    target = Path(destination).absolute()
    target.mkdir(parents=True, exist_ok=False)
    for relative, source in files.items():
        path = target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8", newline="\n")
    return target


def project_archive(spec: Mapping, *, design_notes="") -> bytes:
    """Deterministic ZIP of the same files shown and executed by the Lab."""
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for name, source in preview_files(spec, design_notes=design_notes).items():
            info = ZipInfo("algorithm_lab/" + name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, source.encode("utf-8"))
    return output.getvalue()


__all__ = ["SPEC_SCHEMA", "REPORT_SCHEMA", "list_recipes", "normalize_spec",
           "preview_files", "export_project", "project_archive"]
