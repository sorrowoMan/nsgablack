import json
from pathlib import Path

from blackbase.participation import ParticipationContract
from nsgablack.plugins.base import Plugin


class DistributionReport(Plugin):
    participation = ParticipationContract(vetoes=("finalization",))
    context_requires = context_provides = context_mutates = context_cache = ()
    context_notes = "Reads committed CMA Unit and Pool identities; does not write shared context keys."

    def __init__(self, output_dir):
        super().__init__("cma_distribution_report")
        self.output_dir = Path(output_dir)

    def _summary(self):
        solver, unit = self.solver, self.solver.adapter.algorithm_unit
        return dict(schema="algorithm_semantics.cmaes/v1", run_id=solver.run_session.run_id,
            evaluations=int(solver.evaluation_count), logical_steps=int(solver.run_progress_steps),
            problem_calls=len(solver.problem.calls), mean=unit.mean.tolist(),
            covariance=unit.covariance.tolist(), sigma=unit.sigma, path_c=unit.path_c.tolist(),
            path_sigma=unit.path_sigma.tolist(), iteration=unit.iteration,
            cohort_count=len(unit.last_cohort["refs"]),
            selected_indices=list(unit.last_cohort["selected_indices"]),
            best_objective=unit.best["objective"], best_candidate=unit.best["candidate"].tolist(),
            pool_id=solver.solution_pool.pool_id)

    def on_solver_finalization_prepare(self, result):
        runtime = self.solver.case_runtime
        if runtime is not None:
            runtime.begin_finalization_transaction("case_finalization").publish(
                "summary", self._summary(), serializer="json", kind="case-summary")

    def on_solver_finalized(self, result):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "summary.json").write_text(json.dumps(self._summary(), ensure_ascii=False,
            indent=2, allow_nan=False), encoding="utf-8")
