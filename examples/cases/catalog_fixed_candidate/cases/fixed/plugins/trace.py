"""只读、无文件写入的结果观察；不另外调用 evaluate。"""
import json
from blackbase.participation import ParticipationContract
from nsgablack.plugins.base import Plugin


class FixedCandidateTrace(Plugin):
    participation = ParticipationContract()
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Read exact pool references after the run; no context writes.",)

    def __init__(self):
        super().__init__(name="fixed_candidate_trace")

    def on_solver_finish(self, result):
        solver = self.solver
        refs = solver.adapter.get_solution_pool_roots(solver) or ()
        objectives, violations = solver.solution_pool.read_raw_feedback(refs)
        payload = {
            "steps": int(solver.run_progress_steps),
            "evaluations": int(solver.evaluation_count),
            "candidates": solver.solution_pool.read(refs).numeric_matrix.tolist(),
            "raw_objectives": objectives.tolist(),
            "raw_violations": violations.tolist(),
            "accepted_refs": len(refs),
        }
        print("fixed-candidate-result " + json.dumps(payload, sort_keys=True))
