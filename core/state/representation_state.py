"""The currently bound pipeline joins the existing step transaction."""
class RepresentationStateParticipant:
    name = "solver.representation"

    def __init__(self, solver):
        self.solver = solver

    def snapshot_step_state(self):
        component = self.solver.representation_pipeline
        getter, setter = getattr(component, "get_state", None), getattr(component, "set_state", None)
        if callable(getter) != callable(setter):
            raise TypeError("pipeline state requires both get_state and set_state")
        return {"state": getter() if callable(getter) else None}

    def restore_step_state(self, snapshot):
        if snapshot["state"] is not None:
            self.solver.representation_pipeline.set_state(snapshot["state"])

    def step_transaction_children(self):
        return ()

    def commit_step_state(self, snapshot):
        return None
