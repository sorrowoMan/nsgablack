"""Validate small task inputs and rebuild the original supply scenario locally."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Mapping

import numpy as np

from blackbase.project import case_import_context
from blackbase.resources import ArtifactBinding
from blackbase.wire import thaw_wire_mapping

TASK_SCHEMA = "supply_adjustment_nested.production_task/v1"
PORTABLE_TASK_SCHEMA = "supply_adjustment_nested.production_task/v2"
PARENT_PROJECT = Path(__file__).resolve().parents[3]


def compute_scenario_digest(bom_matrix, supply_matrix) -> str:
    digest = hashlib.sha256(b"supply_adjustment_nested.production_scenario/v1\0")
    bom = np.asarray(bom_matrix, dtype=float)
    if bom.ndim != 2 or not np.all(np.isfinite(bom)):
        raise ValueError("scenario digest requires a finite two-dimensional BOM")
    for name, value in (("bom", bom > 0), ("supply", supply_matrix)):
        array = np.asarray(value, dtype="<f8", order="C")
        if array.ndim != 2 or not np.all(np.isfinite(array)):
            raise ValueError("scenario digest requires finite two-dimensional data")
        digest.update(name.encode("ascii") + b"\0")
        digest.update(str(array.shape).encode("ascii") + b"\0" + array.tobytes(order="C"))
    return "sha256:" + digest.hexdigest()


def _verified_source_payloads(source: Mapping, *, publisher=None):
    if not isinstance(source, Mapping) or set(source) != {"bom", "supply"}:
        raise ValueError("production task source must declare bom and supply")
    result, payloads = {}, {}
    for name in ("bom", "supply"):
        item = dict(source[name])
        expected = str(item["sha256"])
        if set(item) == {"path", "sha256"}:
            path = Path(item["path"]).expanduser().resolve()
            payload = path.read_bytes()
            normalized = {"path": str(path), "sha256": expected}
        elif set(item) == {"binding", "sha256", "suffix"}:
            if publisher is None:
                raise ValueError("portable production source requires its formal Artifact reader")
            if item["suffix"] not in {".csv", ".xlsx", ".xls"}:
                raise ValueError("portable source must retain a supported input file suffix")
            binding = ArtifactBinding.from_dict(item["binding"])
            if binding.ref.checksum != "sha256:" + expected:
                raise ValueError("portable source digest disagrees with Artifact identity")
            if (binding.ref.metadata.get("source_suffix") != item["suffix"]
                    or binding.ref.metadata.get("source_sha256") != expected):
                raise ValueError("portable source format or digest disagrees with its published declaration")
            payload = publisher.read_verified(binding)
            if not isinstance(payload, bytes):
                raise TypeError("production source Artifact reader must return bytes")
            normalized = {"binding": binding.as_dict(), "sha256": expected, "suffix": item["suffix"]}
        else:
            raise ValueError(f"source.{name} requires an explicit path or Artifact binding descriptor")
        if len(expected) != 64 or hashlib.sha256(payload).hexdigest() != expected:
            raise ValueError(f"production task source.{name} SHA256 mismatch")
        result[name], payloads[name] = normalized, payload
    return result, payloads


def verified_source(source: Mapping, *, publisher=None) -> dict:
    return _verified_source_payloads(source, publisher=publisher)[0]


def production_code_manifest(case_dir):
    """Describe trusted predeployed domain code by stable relative names."""
    case_dir = Path(case_dir).resolve()
    files = {}
    for path in sorted(case_dir.rglob("*.py")):
        path.resolve().relative_to(case_dir)
        files[path.relative_to(case_dir).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    if not files or "problem/production_problem.py" not in files:
        raise ValueError("predeployed production Case is missing its original model")
    return {"schema": "production_scheduling.code_manifest/v1", "files": files}


def portable_production_case_dir():
    # An administrator-controlled process environment, never a task path.
    configured = os.environ.get("NSGABLACK_PRODUCTION_CASE_DIR", "").strip()
    return Path(configured).expanduser().resolve() if configured else (
        PARENT_PROJECT.parent / "production_scheduling/cases/production_scheduling"
    ).resolve()


@dataclass(frozen=True)
class PreparedProductionTask:
    task: dict
    outer_problem: object
    adjusted_supply: np.ndarray
    inner_config: object
    production_case_dir: Path
    builder: object

    def build_solver(self, *, resource_context):
        return self.builder(
            bom_matrix=self.outer_problem.bom_matrix,
            supply_matrix=self.adjusted_supply,
            production_case_dir=self.production_case_dir,
            cfg=self.inner_config,
            resource_context=resource_context,
        )


def prepare_task(task: Mapping, *, publisher=None) -> PreparedProductionTask:
    if not isinstance(task, Mapping):
        raise ValueError("production_inner requires component_overrides.task")
    task = thaw_wire_mapping(task)
    required = {"schema", "source", "machines", "materials", "days", "shifts", "candidate_token",
                "scenario_digest", "inner_config"}
    portable = task.get("schema") == PORTABLE_TASK_SCHEMA
    optional = {"max_moved_events", "code_manifest"} if portable else {"max_moved_events", "production_case_dir"}
    if portable:
        required.add("code_manifest")
    if required.difference(task) or set(task).difference(required | optional):
        raise ValueError("production task has missing or unsupported fields")
    if (task["schema"] not in {TASK_SCHEMA, PORTABLE_TASK_SCHEMA}
            or not isinstance(task["candidate_token"], str) or not task["candidate_token"].strip()):
        raise ValueError("production task requires its supported schema and outer candidate token")
    for name in ("machines", "materials", "days"):
        if type(task[name]) is not int or task[name] < 1:
            raise ValueError(f"production task {name} must be a positive integer")
    if task["days"] != 31:
        raise ValueError("production task preserves the original day0..30 planning window")
    if not isinstance(task["source"], Mapping) or set(task["source"]) != {"bom", "supply"}:
        raise ValueError("production task source must declare bom and supply")
    if portable and any(set(dict(item)) != {"binding", "sha256", "suffix"} for item in task["source"].values()):
        raise ValueError("portable production task cannot contain sender-local source paths")
    if not portable and any(set(dict(item)) != {"path", "sha256"} for item in task["source"].values()):
        raise ValueError("legacy production task requires explicit local source paths")
    task["source"], payloads = _verified_source_payloads(task["source"], publisher=publisher)
    default_case = PARENT_PROJECT.parent / "production_scheduling/cases/production_scheduling"
    production_case_dir = portable_production_case_dir() if portable else Path(task.get("production_case_dir", default_case)).resolve()
    if portable and task["code_manifest"] != production_code_manifest(production_case_dir):
        raise ValueError("predeployed production code does not match its frozen manifest")
    with case_import_context(production_case_dir.parents[1], production_case_dir.name):
        load_data = importlib.import_module("refactor_data").load_production_data
        if portable:
            with TemporaryDirectory(prefix="production-inputs-") as temporary:
                paths = {}
                for name in ("bom", "supply"):
                    paths[name] = Path(temporary) / (name + task["source"][name]["suffix"])
                    paths[name].write_bytes(payloads[name])
                data = load_data(base_dir=production_case_dir, bom_path=paths["bom"], supply_path=paths["supply"],
                    machines=task["machines"], materials=task["materials"], days=task["days"], fallback=False)
        else:
            data = load_data(base_dir=production_case_dir, bom_path=Path(task["source"]["bom"]["path"]),
                supply_path=Path(task["source"]["supply"]["path"]), machines=task["machines"],
                materials=task["materials"], days=task["days"], fallback=False)
    with case_import_context(PARENT_PROJECT, "supply_adjustment_nested"):
        problem_type = importlib.import_module("cases.supply_adjustment_nested.problem").SupplyEventShiftProblem
        inner_module = importlib.import_module("cases.supply_adjustment_nested.inner_solver")
        inner_config = inner_module.InnerProductionSolverConfig(**dict(task["inner_config"]))
        if type(inner_config.seed) is not int or type(inner_config.max_evaluations) is not int or inner_config.max_evaluations < 1:
            raise ValueError("production task requires explicit integer seed and positive inner max_evaluations")
        if any(type(value) is not int or value < 1 for value in (inner_config.pop_size, inner_config.generations)):
            raise ValueError("production task requires positive integer population and generation counts")
        outer_problem = problem_type(
            base_supply=data.supply_matrix, bom_matrix=data.bom_matrix,
            production_case_dir=production_case_dir, inner_solver_cfg=inner_config,
            material_ids=np.arange(1, task["materials"] + 1),
            max_moved_events=task.get("max_moved_events"),
        )
        builder = inner_module.build_inner_production_solver
    values = np.asarray(task["shifts"], dtype=float)
    shifts = outer_problem.decode_shifts(values)
    if values.shape != shifts.shape or not np.array_equal(values, shifts):
        raise ValueError("production task shifts must already satisfy the repaired today-fixed problem")
    adjusted = outer_problem.apply_shifts(shifts)
    if not np.array_equal(adjusted[:, 0], outer_problem.base_supply[:, 0]):
        raise ValueError("production task changes today's inventory")
    if compute_scenario_digest(data.bom_matrix, adjusted) != task["scenario_digest"]:
        raise ValueError("production task scenario_digest mismatch")
    task["shifts"] = shifts.tolist()
    adjusted.setflags(write=False)
    return PreparedProductionTask(task, outer_problem, adjusted, inner_config, production_case_dir, builder)
