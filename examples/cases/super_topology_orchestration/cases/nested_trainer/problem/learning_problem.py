"""MLBlack learning semantics owned by the nested Trainer."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from blackbase.wire import thaw_wire_value
from mlblack.core import Feedback, LearningProblem

from ..evaluation.fit_method import NestedFitMethod


class NestedLearningProblem(LearningProblem):
    name = "synthetic_capacity_regularization_fit"
    objective_count = 2

    def __init__(self, outer_candidate) -> None:
        candidate = np.asarray(outer_candidate, dtype=float).reshape(-1)
        if candidate.shape != (2,):
            raise ValueError("nested Trainer expects a two-dimensional outer candidate")
        self.outer_candidate = candidate.copy()
        self.provider = NestedFitMethod()
        self.case_runtime = None

    def prepare_model_for_evaluation(self, model, state, context):
        del state, context
        if self.case_runtime is None:
            raise RuntimeError("nested Trainer requires an injected CaseRuntimeContext")
        self.case_runtime.checkpoint()
        calibration, child, result = self.provider.solve_calibration(
            self.case_runtime, target=self.calibration_target,
        )
        resource = child.request.resource_context
        grant = child.request.child_grant
        lease = resource.get("lease", {})
        return {
            **model,
            "calibration": calibration,
            "nested_audit": {
                "trainer_identity": self.case_runtime.identity.as_dict(),
                "inner_identity": child.identity.as_dict(),
                "inner_status": child.status,
                "inner_resource_grant": dict(child.request.resource_context.get("grant", {})),
                "inner_resource_lineage": {
                    "namespace": resource.get("namespace"),
                    "lease_id": lease.get("lease_id"),
                    "parent_lease_id": None if grant is None else grant.parent_lease_id,
                    "fencing_token": lease.get("fencing_token"),
                    "grant_id": None if grant is None else grant.grant_id,
                },
                "inner_resource_binding_current": bool(
                    child.resource_usage.get("binding", {}).get("current", False)
                ),
                "inner_budget_usage": dict(child.budget_usage),
                "inner_deadline_at": float(child.control.deadline_at),
                "inner_cancellation": child.control.cancellation.as_dict(),
                "inner_best_objectives": result.best_objectives.tolist(),
                "inner_pool": dict(result.metadata["solution_pool"]),
                "calibration_target": self.calibration_target,
                "selected_calibration": calibration,
            },
        }

    def restore_model_for_evaluation(self, model, state, feedback, context):
        """Restore the calibration from its recorded child result, without a run."""
        del state, context
        audit = feedback.info.get("nested_audit")
        if not isinstance(audit, Mapping) or "selected_calibration" not in audit:
            raise ValueError("nested model restoration requires recorded calibration evidence")
        calibration = float(audit["selected_calibration"])
        if not np.isfinite(calibration):
            raise ValueError("recorded nested calibration must be finite")
        if float(audit.get("calibration_target", np.nan)) != self.calibration_target:
            raise ValueError("nested calibration evidence belongs to another outer problem")
        return {**model, "calibration": calibration, "nested_audit": thaw_wire_value(audit)}

    @property
    def calibration_target(self) -> float:
        capacity, regularization = self.outer_candidate
        return float(np.clip(0.5 * (capacity - regularization), -1.0, 1.0))

    def score(self, calibration: float) -> tuple[float, float]:
        capacity, regularization = self.outer_candidate
        loss = (
            (float(capacity) - 0.65) ** 2
            + (float(regularization) - 0.25) ** 2
            + 0.2 * (float(calibration) - self.calibration_target) ** 2
        )
        complexity = float(capacity**2 + 0.5 * regularization)
        return float(loss), complexity

    def evaluate(self, candidate, state=None, context=None) -> Feedback:
        del state, context
        calibration = float(candidate["calibration"])
        loss, complexity = self.score(calibration)
        return Feedback(
            objectives=np.asarray([loss, complexity], dtype=float),
            loss=loss,
            metrics={"validation_loss": loss, "complexity": complexity},
            info={"nested_audit": candidate.get("nested_audit", {})},
        )
