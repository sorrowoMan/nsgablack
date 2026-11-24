"""只在最终提交后写本地观察文件，不改变档案选择。"""
import json
from pathlib import Path
from blackbase.participation import ParticipationContract
from nsgablack.plugins.base import Plugin
from nsgablack.utils.engineering.file_io import atomic_write_text


class ArchiveSummary(Plugin):
    participation = ParticipationContract(vetoes=("finalization",))
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Observes committed archive/Pool equality and writes a local report."

    def __init__(self, output_dir):
        super().__init__(name="archive_summary")
        self.output_dir = Path(output_dir)

    def _payload(self):
        solver, adapter = self.solver, self.solver.adapter
        refs = adapter.get_population_solution_refs(solver)
        batch = solver.solution_pool.read(refs)
        entries = adapter.algorithm_unit.entries
        return {"case": "map_elites_archive", "run_id": solver.run_session.run_id, "evaluations": solver.evaluation_count,
            "logical_steps": solver.run_progress_steps, "problem_calls": solver.problem.calls,
            "pool_id": solver.solution_pool.pool_id, "cells": [entry["cell"] for entry in entries],
            "candidates": batch.numeric_matrix.tolist(), "costs": [entry["quality"] for entry in entries],
            "refs": [ref.as_dict() for ref in refs], "components": adapter.get_runtime_context_projection(solver)}

    def on_solver_finalization_prepare(self, result):
        solver = self.solver
        authority = solver.get_population_authority_identity()
        if authority is not None and solver.snapshot_store.read_verified(authority.snapshot).data.get(
                "solution_pool_ref") != solver.solution_pool.publication_ref():
            raise ValueError("archive authority and Pool manifest disagree")
        payload = self._payload()
        runtime = getattr(solver, "case_runtime", None)
        if runtime is not None and runtime.artifact_publisher is not None:
            runtime.begin_finalization_transaction("case_finalization").publish(
                "summary", payload, serializer="json", kind="case-summary")

    def on_solver_finalized(self, result):
        summary = self._payload()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.output_dir / "summary.json", json.dumps(summary, ensure_ascii=False, indent=2))
