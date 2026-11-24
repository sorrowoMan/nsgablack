"""Prepare the optional outer working collection without seeding or evaluation."""
from blackbase.participation import ParticipationContract
from nsgablack.plugins.base import Plugin


class PrepareWorkingPool(Plugin):
    participation = ParticipationContract()
    state_recovery_level = "L0"
    state_recovery_notes = "The collection is restored with the Solver pool checkpoint."

    def __init__(self, collection):
        super().__init__("prepare_outer_working_pool")
        self.collection = collection

    def on_solver_init(self, solver):
        if solver.run_session.resume_loaded:
            if not solver.solution_pool.has_subpool(self.collection):
                raise ValueError("restored outer working pool is missing")
            return
        solver.solution_pool.create_subpool(self.collection)
