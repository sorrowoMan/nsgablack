"""Preference memory joins the existing step transaction and checkpoint path."""


class BiasStateParticipant:
    name = "solver.bias"

    def __init__(self, solver):
        self.solver = solver

    def snapshot_step_state(self):
        module = self.solver.bias_module
        getter = getattr(module, "get_state", None)
        setter = getattr(module, "set_state", None)
        if callable(getter) != callable(setter):
            raise TypeError("Bias state requires both get_state and set_state")
        return {"state": getter() if callable(getter) else None}

    def restore_step_state(self, snapshot):
        if snapshot["state"] is not None:
            self.solver.bias_module.set_state(snapshot["state"])

    def step_transaction_children(self):
        return ()

    def commit_step_state(self, snapshot):
        return None
