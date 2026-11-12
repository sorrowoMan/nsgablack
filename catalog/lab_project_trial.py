"""Typed existing-Project trials over the shared Project/Case/L0 runtime.

The model proposes existing argparse parameters.  A separate caller confirms
the exact proposal digest before this module runs a detached project copy.
No model text becomes Python, an import target, a path or a shell command.
"""
from __future__ import annotations

import ast
import base64
from collections.abc import Mapping
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from .lab_jobs import spec_digest
from .lab_runner import TrialError, _execute, _public_binding, _public_logs, _read_json, _trial_environment


PROPOSAL_SCHEMA = "nsgablack.project_trial/v1"
REPORT_SCHEMA = "nsgablack.project_trial_report/v1"
MAX_STEPS = 32
MAX_TIMEOUT_SECONDS = 180
MAX_SNAPSHOT_BYTES = 64 * 1024 * 1024
MAX_ARTIFACT_ARCHIVE_BYTES = 512 * 1024
MAX_ARCHIVE_INPUT_BYTES = 8 * 1024 * 1024
_NAME = re.compile(r"[a-zA-Z][a-zA-Z0-9_]{0,79}\Z")
_RUNTIME_NAMES = frozenset({
    "help", "check", "ui", "seed", "run_id", "run_dir", "export", "output", "output_dir",
    "generations", "max_generations", "max_steps", "steps", "threads", "workers", "gpus",
    "device", "gpu", "parallel", "parallel_backend", "parallel_workers", "parallel_chunk_size",
    "parallel_strict", "parallel_verbose", "parallel_no_precheck", "no_run_logs", "no_export",
    "pareto_export", "sanity_check_export", "allow_infeasible_update", "no_pipeline", "no_bias",
    "single_objective", "no_decision_trace", "no_profile", "no_bias_md",
})


def _error(code, message):
    return TrialError(code, message)


def _literal(node, fallback=None):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError):
        return fallback


def _case_argument_files(project: Path, case: Path, manifest: dict) -> list[dict]:
    """Use exactly the source registry closure, including its secret filtering."""
    prefix = case.relative_to(project).as_posix() + "/"
    return [{**row, "absolute_path": project / row["path"]}
            for row in manifest["files"]
            if row["path"].startswith(prefix) and row["path"].endswith(".py")
            and "tests" not in Path(row["path"]).parts]


def _arguments(case: Path, allowed_files: list[dict]) -> tuple[dict, list[dict]]:
    """Inspect literal argparse declarations; never import a user parser."""
    arguments, provenance = {}, []
    rows = sorted(allowed_files, key=lambda item: str(item["absolute_path"]))
    for row in rows[:128]:
        path = row["absolute_path"]
        if (path.is_symlink() or not path.resolve().is_relative_to(case.resolve())
                or path.stat().st_size > 512000):
            continue
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise _error("project_snapshot_changed", "读取参数时项目文件身份已改变。")
        try:
            tree = ast.parse(raw.decode("utf-8-sig"))
        except (UnicodeError, SyntaxError):
            continue
        parser_functions = [node for node in ast.walk(tree)
                            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                            and node.name == "build_parser"]
        if not parser_functions:
            continue
        found = False
        for node in (item for function in parser_functions for item in ast.walk(function)):
            if (not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute)
                    or node.func.attr != "add_argument"):
                continue
            flags = [_literal(arg) for arg in node.args]
            flags = [flag for flag in flags if isinstance(flag, str)
                     and re.fullmatch(r"--[a-z][a-z0-9-]{0,79}", flag)]
            if not flags:
                continue
            keywords = {item.arg: item.value for item in node.keywords if item.arg}
            if any(key not in {"dest", "type", "default", "choices", "action", "help", "required"}
                   for key in keywords):
                continue
            dest = _literal(keywords.get("dest"), flags[0][2:].replace("-", "_"))
            if not isinstance(dest, str) or not _NAME.fullmatch(dest):
                continue
            action = _literal(keywords.get("action"))
            default = _literal(keywords.get("default"))
            choices = _literal(keywords.get("choices"))
            kind_node = keywords.get("type")
            kind = kind_node.id if isinstance(kind_node, ast.Name) else None
            if action in {"store_true", "store_false"}:
                kind = "bool"
                if "default" not in keywords:
                    default = action == "store_false"
            elif action is not None:
                continue
            elif kind is None:
                kind = "str"
            if kind not in {"int", "float", "str", "bool"}:
                continue
            if choices is not None:
                if (not isinstance(choices, (list, tuple)) or not 1 <= len(choices) <= 40
                        or any(type(item) not in {int, float, str, bool} for item in choices)):
                    continue
                choices = list(choices)
            description = _literal(keywords.get("help"), "")
            record = {"flag": flags[0], "type": kind, "default": default,
                      "description": str(description)[:400], "action": action}
            if choices is not None:
                record["choices"] = choices
            if dest in arguments and any(arguments[dest].get(key) != record.get(key)
                                         for key in ("flag", "type", "default", "choices", "action")):
                raise _error("parameter_ambiguous", "Case 中有同名但不同含义的参数声明，不能猜测装配。")
            arguments[dest] = record
            found = True
        if found:
            provenance.append({"path": path.relative_to(case).as_posix(),
                               "sha256": hashlib.sha256(raw).hexdigest()})
    return arguments, provenance


def _exposed(arguments):
    result = {}
    for name, rule in arguments.items():
        if name in _RUNTIME_NAMES:
            continue
        # Free strings are usually paths, addresses or names interpreted by the
        # Case. Only finite declared choices cross this first execution surface.
        if rule["type"] == "str" and "choices" not in rule:
            continue
        value = {key: item for key, item in rule.items() if key not in {"action", "flag"}}
        value["option"] = rule["flag"]
        # Integer sizes keep the existing conservative trial policy. Known
        # population/batch counts keep it even if a parser declares a float.
        # Other floats are algorithm values (weights, scales, offsets, etc.);
        # their magnitude or sign is not an execution-resource declaration.
        count_parameter = any(token in name for token in ("pop_size", "population", "batch_size", "ants"))
        if rule["type"] == "int" or (rule["type"] == "float" and count_parameter):
            value["minimum"] = -10000 if isinstance(rule["default"], (int, float)) and rule["default"] < 0 else 0
            value["maximum"] = 128 if count_parameter else 10000
            value["bounds_source"] = "trial_resource_policy"
            if isinstance(rule["default"], (int, float)) and not value["minimum"] <= rule["default"] <= value["maximum"]:
                value["requires_override"] = True
        if rule["type"] in {"int", "float"} and type(rule["default"]) in {int, float}:
            try:
                finite_default = math.isfinite(rule["default"])
            except OverflowError:
                finite_default = False
            if not finite_default:
                # Nonfinite defaults cannot cross JSON or be silently used by
                # an omitted override. Keep the parser unchanged, publish no
                # invented replacement, and require an explicit finite value.
                value.pop("default", None)
                value["requires_override"] = True
                value["description"] += " 原默认值不是有限数值，必须显式设置有限值。"
        result[name] = value
    return result


def project_parameter_schema(sources, project_id: str, case_name: str, *,
                             allow_parameterless: bool = False) -> dict:
    if type(allow_parameterless) is not bool:
        raise _error("invalid_parameter_mode", "无额外参数模式必须显式声明。")
    manifest = sources.snapshot_manifest(project_id)
    project = sources.resolve_project(project_id)
    case = sources.resolve_case(project_id, case_name)
    arguments, provenance = _arguments(case, _case_argument_files(project, case, manifest))
    if not arguments and not allow_parameterless:
        raise _error("parameter_contract_missing", "此 Case 尚未提供可静态检查的参数契约。")
    return {"schema": "nsgablack.project_parameter_schema/v1", "project_id": project_id,
            "case_name": case_name, "project_revision": manifest["source_digest"],
            "properties": _exposed(arguments), "parameter_sources": provenance,
            "parameter_mode": "declared" if arguments else "none",
            "runtime_owned": sorted(set(arguments) & _RUNTIME_NAMES),
            "budget": {"max_steps": {"minimum": 1, "maximum": MAX_STEPS, "default": 8},
                       "timeout_seconds": {"minimum": 5, "maximum": MAX_TIMEOUT_SECONDS, "default": 120},
                       "threads": 1, "gpus": 0},
            "execution": "existing_project_case_l0", "requires_explicit_run": True}


def validate_project_proposal(sources, proposal: Mapping, *,
                              allow_parameterless: bool = False) -> dict:
    if (not isinstance(proposal, Mapping) or set(proposal) - {
            "schema", "project_id", "project_revision", "case_name", "parameters", "budget", "seed"}
            or proposal.get("schema", PROPOSAL_SCHEMA) != PROPOSAL_SCHEMA):
        raise _error("invalid_project_proposal", "项目试跑建议字段不符合契约。")
    project_id, case_name = proposal.get("project_id"), proposal.get("case_name")
    if not isinstance(project_id, str) or not isinstance(case_name, str):
        raise _error("invalid_project_proposal", "项目与 Case 身份不能为空。")
    schema = project_parameter_schema(sources, project_id, case_name,
                                      allow_parameterless=allow_parameterless)
    if proposal.get("project_revision") != schema["project_revision"]:
        raise _error("project_revision_changed", "项目源码或数据已改变，请重新读取后生成建议。")
    parameters = proposal.get("parameters", {})
    if not isinstance(parameters, Mapping) or set(parameters) - set(schema["properties"]):
        raise _error("project_parameter_unknown", "建议含有未声明或由运行器管理的参数。")
    if any(rule.get("requires_override") and name not in parameters
           for name, rule in schema["properties"].items()):
        raise _error("project_parameter_override_required", "原 Case 的默认值不满足本次参数或资源要求，请显式设置有效参数。")
    normalized = {}
    for name, value in parameters.items():
        rule = schema["properties"][name]
        kind = rule["type"]
        if ((kind == "int" and type(value) is not int)
                or (kind == "float" and type(value) not in {float, int})
                or (kind == "bool" and type(value) is not bool)
                or (kind == "str" and type(value) is not str)):
            raise _error("project_parameter_type", "建议参数类型与原 Case 声明不一致。")
        if kind in {"int", "float"}:
            try:
                finite = math.isfinite(value)
            except OverflowError:
                finite = False
            if not finite:
                raise _error("project_parameter_bounds", "建议数值参数必须是有限数值。")
            if (("minimum" in rule and value < rule["minimum"])
                    or ("maximum" in rule and value > rule["maximum"])):
                raise _error("project_parameter_bounds", "建议参数超出本次试跑的资源范围。")
        if "choices" in rule and value not in rule["choices"]:
            raise _error("project_parameter_choice", "建议参数不在原 Case 的可选值中。")
        normalized[name] = float(value) if kind == "float" else value
    budget = proposal.get("budget", {})
    if not isinstance(budget, Mapping) or set(budget) - {"max_steps", "timeout_seconds", "threads", "gpus"}:
        raise _error("invalid_project_budget", "项目试跑预算字段无效。")
    steps, timeout = budget.get("max_steps", 8), budget.get("timeout_seconds", 120)
    if (type(steps) is not int or not 1 <= steps <= MAX_STEPS
            or type(timeout) not in {int, float} or not math.isfinite(timeout)
            or not 5 <= timeout <= MAX_TIMEOUT_SECONDS
            or budget.get("threads", 1) != 1 or type(budget.get("threads", 1)) is not int
            or budget.get("gpus", 0) != 0 or type(budget.get("gpus", 0)) is not int):
        raise _error("invalid_project_budget", "本次项目试跑仅允许有界步骤、单线程和无 GPU。")
    seed = proposal.get("seed", 42)
    if type(seed) is not int or not 0 <= seed < 2**31:
        raise _error("invalid_project_seed", "随机种子必须是非负整数。")
    return {"schema": PROPOSAL_SCHEMA, "project_id": project_id,
            "project_revision": schema["project_revision"], "case_name": case_name,
            "parameters": normalized, "budget": {"max_steps": steps, "timeout_seconds": float(timeout),
                                                    "threads": 1, "gpus": 0}, "seed": seed}


def _argv(arguments, proposal, project: Path, run_id: str):
    values = dict(proposal["parameters"])
    for name in ("max_steps", "generations", "max_generations", "steps"):
        if name in arguments:
            values[name] = proposal["budget"]["max_steps"]
    forced = {"seed": proposal["seed"], "parallel_backend": "thread", "parallel_workers": 1,
              "threads": 1, "workers": 1, "gpus": 0, "gpu": False,
              "run_id": run_id, "run_dir": str(project / "results" / "runtime"),
              "export": str(project / "results" / "exports" / "plan.csv"),
              "pareto_export": 4, "no_run_logs": True, "sanity_check_export": True}
    for name, value in forced.items():
        if name in arguments and ("choices" not in arguments[name] or value in arguments[name]["choices"]):
            values[name] = value
    result = []
    for name, value in values.items():
        rule = arguments[name]
        if rule["action"] == "store_true":
            if value:
                result.append(rule["flag"])
        elif rule["action"] == "store_false":
            if not value:
                result.append(rule["flag"])
        else:
            result.extend((rule["flag"], str(value)))
    return result


def _copy_snapshot(source: Path, target: Path, manifest: dict):
    if manifest["total_bytes"] > MAX_SNAPSHOT_BYTES:
        raise _error("project_too_large", "项目快照超过本次试跑的复制范围。")
    for row in manifest["files"]:
        relative = Path(row["path"])
        path = source / relative
        if (relative.is_absolute() or ".." in relative.parts or path.is_symlink()
                or not path.resolve().is_relative_to(source.resolve()) or not path.is_file()):
            raise _error("project_snapshot_changed", "复制时项目文件身份已改变。")
        data = path.read_bytes()
        if len(data) != row["size_bytes"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise _error("project_snapshot_changed", "复制时项目源码或数据发生变化。")
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)


def _prepare_project(sources, proposal, folder: Path, run_id: str):
    source = sources.resolve_project(proposal["project_id"])
    manifest = sources.snapshot_manifest(proposal["project_id"])
    if manifest["source_digest"] != proposal["project_revision"]:
        raise _error("project_revision_changed", "确认后项目发生变化，未启动运行。")
    project = folder / "project"
    project.mkdir()
    _copy_snapshot(source, project, manifest)
    for path in (project / "results", project / "results" / "exports", project / "results" / "runtime"):
        path.mkdir(parents=True, exist_ok=True)
    case = project / "cases" / proposal["case_name"]
    arguments, _ = _arguments(case, _case_argument_files(project, case, manifest))
    argv = _argv(arguments, proposal, project, run_id)
    (project / "project_config.original.txt").write_bytes((project / "project_config.py").read_bytes())
    l0 = {"namespace": f"catalog.project_trial.{run_id}",
          "offer": {"threads": 1, "gpus": 0, "backend": "local", "device_tokens": []},
          "policy": {"mode": "strict", "cpu_oversubscribe": False},
          "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
          "compute_backend": "auto", "execution_backend": "local"}
    stages = [{"name": "trial", "cases": [proposal["case_name"]], "policy": "serial", "mode": "build",
               "resource_requests": {proposal["case_name"]: {"threads": 1, "gpus": 0, "backend": "local"}},
               "component_overrides": {proposal["case_name"]: {"argv": argv} if arguments else {}}}]
    config = (f"PROJECT_NAME = {('project_trial_' + run_id)!r}\nL0 = {l0!r}\nSTAGES = {stages!r}\n"
              "GROUPS = {'default': {'stages': ['trial']}}\n")
    (project / "project_config.py").write_text(config, encoding="utf-8")
    (project / "run_project.py").write_text(
        "from pathlib import Path\nfrom nsgablack.project.project_runner import main\n"
        "if __name__ == '__main__':\n    raise SystemExit(main(project_root=Path(__file__).resolve().parent))\n",
        encoding="utf-8")
    original = case / "build_solver.py"
    original.rename(case / "_project_trial_original_build_solver.py")
    original.write_text(
        "from nsgablack.catalog.lab_project_trial import build_observed_case\n"
        "def build_solver(*args, resource_context=None, component_overrides=None, **kwargs):\n"
        "    kwargs.update(resource_context=resource_context, component_overrides=component_overrides)\n"
        "    return build_observed_case(__file__, __package__, args, kwargs)\n", encoding="utf-8")
    (project / "project_trial_proposal.json").write_text(json.dumps(proposal, ensure_ascii=False), encoding="utf-8")
    (project / "project_trial_inputs.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return project, manifest, argv


def _detached(value):
    return json.loads(json.dumps(value, allow_nan=False, default=lambda item:
                                item.tolist() if hasattr(item, "tolist") else item.as_dict()))


def build_observed_case(wrapper_file, package, args, kwargs):
    """Trusted wrapper installed only inside the detached trial Project."""
    case = Path(wrapper_file).resolve().parent
    project = case.parents[1]
    proposal = _read_json(project / "project_trial_proposal.json")
    name = f"{package}._project_trial_original_build_solver" if package else f"project_trial_builder_{uuid4().hex}"
    spec = importlib.util.spec_from_file_location(name, case / "_project_trial_original_build_solver.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    solver = module.build_solver(*args, **kwargs)
    if not all(callable(getattr(solver, method, None)) for method in ("set_max_steps", "set_random_seed", "add_plugin")):
        raise ValueError("Project trial requires the existing optimization Solver control surface")
    solver.set_max_steps(proposal["budget"]["max_steps"])
    solver.set_random_seed(proposal["seed"])
    solver.add_plugin(_report_plugin(proposal, project))
    return solver


def _data_observation(problem, project):
    data = getattr(problem, "data", None)
    result = {"arrays": {}, "scalars": {}, "files": {}, "declared_path_fields": 0, "unresolved_path_fields": []}
    try:
        fields = vars(data) if data is not None else {}
    except TypeError:
        fields = {}
    for name, value in list(fields.items())[:40]:
        if type(value) in {int, float, bool} and (type(value) is bool or math.isfinite(value)):
            result["scalars"][name] = value
        if hasattr(value, "shape") and hasattr(value, "dtype"):
            result["arrays"][name] = {"shape": [int(n) for n in value.shape], "dtype": str(value.dtype)}
        if name.endswith("_path"):
            result["declared_path_fields"] += 1
            if value is None:
                result["unresolved_path_fields"].append(name)
                continue
            path = Path(value).resolve()
            if not path.is_relative_to(project.resolve()) or not path.is_file() or path.is_symlink():
                raise ValueError("runtime data path escaped the detached project")
            raw = path.read_bytes()
            result["files"][name] = {"path": path.relative_to(project).as_posix(),
                                    "sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}
    return result


def _report_plugin(proposal, project):
    from blackbase.participation import ParticipationContract
    from nsgablack.plugins.base import Plugin
    from nsgablack.utils.engineering.file_io import atomic_write_text

    class ProjectTrialReport(Plugin):
        participation = ParticipationContract(vetoes=("finalization",))
        state_recovery_level = "L1"
        state_recovery_notes = "Bounded committed observations and a formally published trial report."
        context_notes = ("Read-only existing Pool, Problem metadata and declared data paths; no evaluations.",)

        def __init__(self):
            super().__init__(name="project_trial_report")
            self.records, self.initial, self.payload = [], None, None

        def observe(self):
            solver = self.solver
            projection = solver.adapter.get_runtime_context_projection(solver)
            tasks = projection.get("unit_tasks", {})
            phases = {str(projection["phase"])} if "phase" in projection else set()
            phases.update(str(item["phase"]) for item in tasks.values()
                          if isinstance(item, Mapping) and "phase" in item)
            return {"steps": int(solver.run_progress_steps), "evaluations": int(solver.evaluation_count),
                    "phases": sorted(phases)}

        def on_solver_init(self, solver):
            self.initial = {"dimension": int(solver.problem.dimension),
                            "objective_names": list(solver.problem.objectives or ()),
                            "problem_class": type(solver.problem).__name__,
                            "adapter_class": type(solver.adapter).__name__,
                            "data": _data_observation(solver.problem, project)}
            if self.initial["data"]["unresolved_path_fields"]:
                raise ValueError("declared input data path is missing; synthetic fallback is not a valid trial")

        def on_generation_committed(self, generation, outcome):
            del generation, outcome
            if len(self.records) >= proposal["budget"]["max_steps"]:
                raise ValueError("trial progress exceeded confirmed budget")
            self.records.append(self.observe())

        def on_solver_finalization_prepare(self, result):
            del result
            solver, pool = self.solver, self.solver.solution_pool
            refs = pool.select(stage="accepted")[-16:]
            raw_f, raw_v = pool.read_raw_feedback(refs)
            runtime = solver.case_runtime
            if runtime is None:
                raise ValueError("trial report requires Project Artifact authority")
            final = self.observe()
            self.payload = _detached({"schema": REPORT_SCHEMA, "proposal_digest": spec_digest(proposal),
                "proposal": proposal, "project_identity": runtime.identity.as_dict(),
                "initial": self.initial, "effective_data": _data_observation(solver.problem, project),
                "steps": final["steps"], "evaluations": final["evaluations"], "records": self.records,
                "result_files": _result_file_manifest(project),
                "resource_binding": _public_binding(solver.resource_binding_audit),
                "raw_results": {"scope": "last_16_accepted", "refs": [ref.as_dict() for ref in refs],
                    "candidates": pool.read(refs).numeric_matrix.tolist(),
                    "raw_objectives": raw_f.tolist(), "raw_violations": raw_v.tolist()}})
            runtime.publish_artifact("project_trial_report", self.payload, serializer="json",
                kind="project_trial_report", media_type="application/json",
                metadata={"schema": REPORT_SCHEMA, "proposal_digest": spec_digest(proposal)})

        def on_solver_finalized(self, result):
            del result
            if self.payload is None:
                raise ValueError("trial report was not prepared")
            atomic_write_text(project / "results" / "project_trial_report.json",
                              json.dumps(self.payload, ensure_ascii=False, indent=2, allow_nan=False))

        def get_state(self):
            return _detached({"records": self.records, "initial": self.initial,
                              "proposal_digest": spec_digest(proposal)})

        def set_state(self, state):
            if not isinstance(state, Mapping) or state.get("proposal_digest") != spec_digest(proposal):
                raise ValueError("trial report state belongs to a different proposal")
            self.records, self.initial = _detached(state["records"]), _detached(state["initial"])

    return ProjectTrialReport()


def _verify_published_report(project, case, trace):
    from blackbase.resources import ArtifactAuthority, FilesystemArtifactPublicationLedger, FilesystemArtifactStore
    name = "project_trial_report"
    publication, ref = case.artifact_publications.get(name), case.artifact_refs.get(name)
    if publication is None or ref is None or publication.ref != ref or publication.case_run_id != case.identity.case_run_id:
        raise _error("project_report_unpublished", "试跑报告没有本次 Case 的正式发布收据。")
    try:
        authority = ArtifactAuthority.from_dict(case.request.resource_context["metadata"]["artifact_authority"])
        target = Path(ref.uri).resolve()
        if not Path(authority.root).resolve().is_relative_to(project.resolve()) or not target.is_relative_to(Path(authority.root).resolve()):
            raise ValueError("scope")
        ledger = FilesystemArtifactPublicationLedger(authority, project_run_id=case.identity.project_run_id,
                                                     case_run_id=case.identity.case_run_id)
        if not ledger.verify(publication):
            raise ValueError("ledger")
        published = json.loads(FilesystemArtifactStore(authority.root).read_verified(ref).decode("utf-8"))
        if published != trace:
            raise ValueError("projection")
    except (ValueError, TypeError, KeyError, OSError, RuntimeError):
        raise _error("project_report_invalid", "试跑报告与正式发布内容不一致。") from None
    return {"publication_id": publication.publication_id, "checksum": ref.checksum,
            "receipt_digest": publication.receipt_digest, "size_bytes": ref.size_bytes}


def _safe_result_path(project: Path, relative: str) -> Path:
    from .lab_project_sources import _linked
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != "results":
        raise _error("project_artifact_scope", "结果文件不属于本次项目结果区域。")
    target = project / path
    if not target.resolve().is_relative_to((project / "results").resolve()):
        raise _error("project_artifact_scope", "结果文件超出本次项目结果区域。")
    current = project
    for part in path.parts:
        current = current / part
        if _linked(current):
            raise _error("project_artifact_link", "结果文件或父目录不能是链接。")
    return target


def _result_file_manifest(project: Path) -> list[dict]:
    """Bind generated result bytes before the final report is published."""
    from .lab_project_sources import _SENSITIVE_NAME, _SENSITIVE_CONTENT, _linked
    result = []
    for path in sorted((project / "results").rglob("*")):
        if _linked(path):
            raise _error("project_artifact_link", "结果文件或父目录不能是链接。")
        if not path.is_file() or path.name in {"project_trial_report.json", "lab_report.json"}:
            continue
        relative = path.relative_to(project).as_posix()
        _safe_result_path(project, relative)
        size = path.stat().st_size
        row = {"path": relative, "size_bytes": size, "sha256": None}
        if size <= 4 * 1024 * 1024:
            raw = path.read_bytes()
            row["sha256"] = hashlib.sha256(raw).hexdigest()
            text = raw.decode("utf-8", errors="ignore") if path.suffix.lower() in {".json", ".txt", ".csv"} else ""
            row["download_allowed"] = not bool(_SENSITIVE_NAME.search(relative) or _SENSITIVE_CONTENT.search(text))
        else:
            row["download_allowed"] = False
        result.append(row)
        if len(result) > 1024:
            raise _error("project_artifacts_exceeded", "结果文件数量超过本次试跑的证据范围。")
    return result


def _artifact_archive(project: Path, records: list[dict], run_id: str) -> tuple[dict | None, bool]:
    """Only receipt-bound, unchanged managed exports become download bytes."""
    buffer = io.BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED):
        pass
    included, omitted, used = [], [], 0
    suffixes = {".csv", ".xlsx", ".json", ".txt", ".png", ".svg", ".pdf"}
    for row in records:
        relative = row["path"]
        if not relative.startswith("results/exports/"):
            continue
        path = _safe_result_path(project, relative)
        if (not row.get("download_allowed") or not row.get("sha256")
                or path.suffix.lower() not in suffixes
                or used + row["size_bytes"] > MAX_ARCHIVE_INPUT_BYTES):
            omitted.append(relative)
            continue
        raw = path.read_bytes()
        if len(raw) != row["size_bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise _error("project_artifact_changed", "结果文件与正式发布的摘要不一致。")
        candidate = io.BytesIO(buffer.getvalue())
        with ZipFile(candidate, "a", compression=ZIP_DEFLATED, compresslevel=6) as archive:
            archive.writestr(relative, raw)
        if len(candidate.getvalue()) > MAX_ARTIFACT_ARCHIVE_BYTES:
            omitted.append(relative)
            continue
        buffer, used = candidate, used + len(raw)
        included.append(relative)
    if not included:
        return None, bool(omitted)
    raw = buffer.getvalue()
    return {"filename": f"{run_id}-results.zip", "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw), "base64": base64.b64encode(raw).decode("ascii"),
            "file_count": len(included), "included_files": included, "omitted_files": omitted,
            "truncated": bool(omitted)}, bool(omitted)


def _verified_results(project, proposal, run_id):
    from blackbase.project.execution import CaseRunResult
    from blackbase.project.run_manifest import ProjectRunManifest
    from blackbase.wire import thaw_wire_mapping
    manifest = ProjectRunManifest.from_dict(_read_json(project / ".blackbase" / "runs" / run_id / "manifest.json"))
    if (manifest.run_id != run_id or manifest.status != "ok" or manifest.exit_code != 0
            or manifest.framework != "nsgablack" or len(manifest.cases) != 1):
        raise _error("project_not_successful", "正式 Project 没有交付本次单 Case 的成功收据。")
    row = manifest.cases[0]
    case = CaseRunResult.from_dict(row["result"])
    if (case.status != "succeeded" or not case.ok or case.request.case_name != proposal["case_name"]
            or case.identity.project_run_id != run_id):
        raise _error("project_case_not_successful", "Case 没有交付本次运行身份的成功结果。")
    binding = dict(case.resource_usage.get("binding", {}))
    if binding.get("current") is not True:
        raise _error("project_resource_unbound", "Case 未确认本次 L0 资源授权。")
    effective = binding.get("effective", {})
    resources = effective.get("resources", {})
    if resources.get("threads", effective.get("threads")) != 1 or resources.get("gpus") != 0:
        raise _error("project_resource_mismatch", "实际资源与已确认的单线程无 GPU 预算不一致。")
    trace = _read_json(project / "results" / "project_trial_report.json")
    if (trace.get("schema") != REPORT_SCHEMA or trace.get("proposal_digest") != spec_digest(proposal)
            or trace.get("project_identity") != case.identity.as_dict()):
        raise _error("project_report_mismatch", "试跑报告与本次建议或运行身份不一致。")
    publication = _verify_published_report(project, case, trace)
    inputs = _read_json(project / "project_trial_inputs.json")
    bound_files = {row["path"]: row["sha256"] for row in inputs["files"]}
    if trace["initial"]["data"]["files"] != trace["effective_data"]["files"]:
        raise _error("project_data_changed", "试跑期间实际数据文件发生改变。")
    if any(bound_files.get(row["path"]) != row["sha256"] for row in trace["effective_data"]["files"].values()):
        raise _error("project_data_unbound", "实际数据与确认的项目快照不一致。")
    report = thaw_wire_mapping(case.output.get("report", {}))
    if (type(trace.get("steps")) is not int or not 0 < trace["steps"] <= proposal["budget"]["max_steps"]
            or report.get("steps", report.get("steps_executed", report.get("generation"))) != trace["steps"]
            or report.get("evaluation_count") != trace["evaluations"]):
        raise _error("project_progress_disagrees", "提交步骤或求值计数与正式 Case 报告不一致。")
    metrics, artifacts = [], trace.get("result_files", [])
    for row in artifacts:
        path = _safe_result_path(project, row["path"])
        if row.get("sha256"):
            raw = path.read_bytes()
            if len(raw) != row["size_bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
                raise _error("project_artifact_changed", "结果文件与正式发布的摘要不一致。")
        if (path.name.endswith(".audit.json") and row.get("sha256")
                and row.get("download_allowed") and len(metrics) < 16):
            metrics.append({"path": row["path"], "report": _read_json(path)})
    archive, truncated = _artifact_archive(project, artifacts, run_id)
    return {"steps": trace["steps"], "evaluations": trace["evaluations"],
            "effective_problem": trace["initial"], "effective_data": trace["effective_data"],
            "records": trace["records"], "raw_results": trace["raw_results"],
            "metrics": metrics, "artifacts": artifacts, "artifact_archive": archive,
            "download_truncated": truncated, "resource_binding": _public_binding(binding),
            "project_result": {"run_id": run_id, "status": manifest.status, "exit_code": manifest.exit_code,
                "case_name": proposal["case_name"], "case_status": case.status,
                "case_identity": case.identity.as_dict(), "publication": publication}}


def run_project_trial(sources, proposal: Mapping, *, confirmed_digest: str,
                      workspace_root: str | Path | None = None,
                      timeout_seconds: float | None = None,
                      allow_parameterless: bool = False) -> dict:
    """Run only a separately confirmed, still-current typed Project proposal."""
    normalized = validate_project_proposal(sources, proposal,
                                           allow_parameterless=allow_parameterless)
    digest = spec_digest(normalized)
    if confirmed_digest != digest:
        raise _error("project_confirmation_mismatch", "运行确认与当前建议不一致，未启动项目。")
    if (timeout_seconds is not None and (type(timeout_seconds) not in {int, float}
            or not math.isfinite(timeout_seconds) or not 5 <= timeout_seconds <= MAX_TIMEOUT_SECONDS)):
        raise _error("invalid_project_budget", "运行服务的时间上界无效。")
    effective_timeout = min(normalized["budget"]["timeout_seconds"],
                            timeout_seconds if timeout_seconds is not None else MAX_TIMEOUT_SECONDS)
    run_id = "project-trial-" + uuid4().hex
    if workspace_root is None:
        folder = Path(tempfile.mkdtemp(prefix="nsgablack-project-trial-"))
    else:
        root = Path(workspace_root).resolve()
        root.mkdir(parents=True, exist_ok=True)
        folder = root / run_id
        folder.mkdir()
    started = time.monotonic()
    project = None
    try:
        project, inputs, argv = _prepare_project(sources, normalized, folder, run_id)
        environment = _trial_environment(folder)
        environment["CUDA_VISIBLE_DEVICES"] = ""
        code, logs, timed_out = _execute(project, run_id, environment, effective_timeout)
        if timed_out:
            raise _error("project_trial_timed_out", "正式项目超过本次试跑时间预算，进程树已停止。")
        if code != 0:
            raise _error("project_trial_failed", "正式项目运行失败，原项目与数据保持不变。")
        result = _verified_results(project, normalized, run_id)
        return {"schema": REPORT_SCHEMA, "status": "succeeded", "success": True, "error": None,
                "project_id": normalized["project_id"], "case_name": normalized["case_name"],
                "proposal_digest": digest, "project_revision": normalized["project_revision"],
                "proposal": normalized, "run_id": run_id, "elapsed_seconds": time.monotonic() - started,
                "input_manifest": inputs, "effective_argv": [value.replace(str(project), "<trial-project>") for value in argv],
                "timed_out": False, "effective_timeout_seconds": effective_timeout,
                "logs": _public_logs(logs, folder), **result}
    except TrialError as exc:
        return {"schema": REPORT_SCHEMA, "status": "failed",
                "project_id": normalized["project_id"], "case_name": normalized["case_name"],
                "timed_out": exc.code == "project_trial_timed_out", "effective_timeout_seconds": effective_timeout,
                "success": False, "proposal_digest": digest, "project_revision": normalized["project_revision"],
                "run_id": run_id, "elapsed_seconds": time.monotonic() - started,
                "error": {"code": exc.code, "message": str(exc)},
                "logs": _public_logs(locals().get("logs", ""), folder)}


__all__ = ["PROPOSAL_SCHEMA", "REPORT_SCHEMA", "project_parameter_schema",
           "validate_project_proposal", "run_project_trial"]
