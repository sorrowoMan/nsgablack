"""Observe committed raw evidence; no evaluation, comparison or search decisions."""
import copy
import hashlib
import io
import time

import numpy as np
from blackbase.participation import ParticipationContract
from blackbase.types import CandidateBatch
from nsgablack.core.evaluation_feedback import OptimizationFeedbackBatch
from nsgablack.plugins.base import Plugin


def numeric_digest(values):
    values = np.asarray(values, dtype="<f8", order="C")
    return hashlib.sha256(str(values.shape).encode("ascii") + b"\0" + values.tobytes()).hexdigest()


class ProductionAblationAudit(Plugin):
    participation = ParticipationContract(vetoes=("finalization",))
    state_recovery_level = "L1"

    def __init__(self, *, arm, seed):
        super().__init__(name="production_ablation_audit")
        self.arm, self.seed = str(arm), int(seed)
        self.batches = []
        self.observer_seconds = 0.0
        self.packing_seconds = 0.0
        self._encoded = None

    def on_solver_init(self, solver):
        if solver.run_progress_steps == 0:
            self.batches = []
            self.observer_seconds = 0.0

    def on_generation_committed(self, generation, outcome):
        started = time.perf_counter()
        event = self.solver.get_last_evaluation_event()
        if event is None or any(b["event_id"] == event.event_id for b in self.batches):
            raise ValueError("ablation requires one distinct evaluation event per committed step")
        batch = CandidateBatch.from_dict(event.candidate_payload)
        feedback = OptimizationFeedbackBatch.from_dict(event.feedback_payload)
        raw, violations = feedback.raw_objectives, feedback.raw_violations
        if raw.shape != (len(batch.semantic_states), 4):
            raise ValueError("ablation raw feedback must retain all four original objectives")
        self.batches.append({"event_id": event.event_id, "step": int(generation),
            "count": len(raw), "cumulative_evaluations": int(event.evaluation_count),
            "initial_values_sha256": numeric_digest(batch.numeric_matrix) if not self.batches else "",
            "objectives": raw.copy(), "violations": violations.copy(),
            "tokens": tuple(batch.candidate_tokens),
            "numeric_hashes": tuple(numeric_digest(row) for row in batch.numeric_matrix)})
        self.observer_seconds += time.perf_counter() - started

    def on_solver_finish(self, result):
        if not self.batches or sum(b["count"] for b in self.batches) != self.solver.evaluation_count:
            raise ValueError("successful ablation trace must account for every actual evaluation")
        started = time.perf_counter()
        data = io.BytesIO()
        np.savez_compressed(data,
            raw_objectives=np.vstack([b["objectives"] for b in self.batches]),
            raw_violations=np.concatenate([b["violations"] for b in self.batches]),
            candidate_tokens=np.asarray([t for b in self.batches for t in b["tokens"]], dtype="U"),
            numeric_hashes=np.asarray([h for b in self.batches for h in b["numeric_hashes"]], dtype="U"),
            batch_counts=np.asarray([b["count"] for b in self.batches]),
            event_ids=np.asarray([b["event_id"] for b in self.batches], dtype="U"),
            cumulative_evaluations=np.asarray([b["cumulative_evaluations"] for b in self.batches]))
        self._encoded = data.getvalue()
        self.packing_seconds = time.perf_counter() - started

    def on_solver_finalization_prepare(self, result):
        runtime = self.solver.case_runtime
        if runtime is None or self._encoded is None:
            raise ValueError("ablation observations require formal Project Artifact publication")
        tx = runtime.begin_finalization_transaction("case_finalization")
        tx.publish("ablation_observations", self._encoded, serializer="bytes",
            kind="production-ablation-observations", media_type="application/x-npz",
            metadata={"schema": "production.ablation_observations/v1", **self.get_report()})

    def get_state(self):
        return {"schema": "production.ablation_audit/v1", "arm": self.arm, "seed": self.seed,
                "batches": copy.deepcopy(self.batches), "observer_seconds": self.observer_seconds}

    def set_state(self, state):
        if state.get("schema") != "production.ablation_audit/v1" or (state.get("arm"), state.get("seed")) != (self.arm, self.seed):
            raise ValueError("ablation audit configuration mismatch")
        self.batches = copy.deepcopy(state["batches"])
        self.observer_seconds = float(state["observer_seconds"])

    def get_report(self):
        return {"arm": self.arm, "seed": self.seed, "evaluations": sum(b["count"] for b in self.batches),
            "batch_count": len(self.batches), "initial_count": self.batches[0]["count"] if self.batches else 0,
            "initial_values_sha256": self.batches[0]["initial_values_sha256"] if self.batches else None,
            "observer_seconds": self.observer_seconds, "packing_seconds": self.packing_seconds,
            "scope": "all committed raw evaluation batches; not an algorithm-owned final population"}
