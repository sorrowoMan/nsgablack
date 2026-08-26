"""Outer optimization objective evaluated by complete nested Trainer Cases."""

from __future__ import annotations

import threading

import numpy as np

from blackbase.project import CaseRunRequest, ExecutionControl
from blackbase.types import TrainerResult
from nsgablack.core import BlackBoxProblem


class NestedTrainingOptimizationProblem(BlackBoxProblem):
    def __init__(self) -> None:
        super().__init__(
            name="outer_model_design_search",
            dimension=2,
            bounds={"x0": [0.0, 1.0], "x1": [0.0, 1.0]},
            objectives=("validation_loss", "model_complexity"),
        )
        self.case_runtime = None
        self._records: list[dict] = []
        self._record_lock = threading.RLock()

    def set_case_runtime(self, runtime) -> None:
        self.case_runtime = runtime

    def evaluate(self, candidate, context=None):
        del context
        if self.case_runtime is None:
            raise RuntimeError("outer Problem requires an injected CaseRuntimeContext")
        point = np.asarray(candidate, dtype=float).reshape(-1)
        self.case_runtime.checkpoint()
        request = CaseRunRequest(
            project_name=self.case_runtime.request.project_name,
            stage_name="candidate_training",
            case_name="nested_trainer",
            case_kind="trainer",
            control=ExecutionControl.with_timeout(
                20.0,
                metadata={"semantic_scope": "outer.candidate_training"},
            ),
            resource_request={
                "workers": 1,
                "threads": 2,
                "gpus": 0,
                "backend": "local",
                "device": "cpu",
            },
            budget_request={"evaluations": 3},
            component_overrides={"outer_candidate": point.tolist()},
            metadata={"topology_edge": "solver->trainer"},
        )
        child = self.case_runtime.invoke(request)
        child.raise_for_failure("candidate Trainer Case failed")
        trainer_result = TrainerResult.from_dict(child.output)
        if trainer_result.best_objectives is None:
            raise RuntimeError("nested Trainer completed without objectives")
        objectives = np.asarray(trainer_result.best_objectives, dtype=float).reshape(-1)
        nested_audit = dict(trainer_result.report.get("nested_audit", {}) or {})
        publication = child.artifact_publications.get("training_summary")
        record = {
            "candidate": point.tolist(),
            "objectives": objectives.tolist(),
            "trainer_identity": child.identity.as_dict(),
            "trainer_status": child.status,
            "trainer_resource_grant": dict(
                child.request.resource_context.get("grant", {}) or {}
            ),
            "trainer_resource_binding_current": bool(
                dict(child.resource_usage.get("binding", {}) or {}).get("current", False)
            ),
            "trainer_budget_usage": dict(child.budget_usage),
            "trainer_deadline_at": float(child.control.deadline_at),
            "trainer_summary_ref": (
                None
                if "training_summary" not in child.artifact_refs
                else child.artifact_refs["training_summary"].as_dict()
            ),
            "trainer_publication_digest": (
                None if publication is None else publication.receipt_digest
            ),
            "inner": nested_audit,
        }
        with self._record_lock:
            self._records.append(record)
        return objectives

    def invocation_records(self) -> list[dict]:
        with self._record_lock:
            return [dict(record) for record in self._records]
