import numpy as np
import pytest


def test_role_adapter_contract_strict_requires_keys():
    from nsgablack.adapters import AlgorithmAdapter, RoleAdapter

    class Dummy(AlgorithmAdapter):
        def __init__(self):
            super().__init__(name="dummy")

        def propose(self, control, context):
            return []

        def update(self, control, candidates, feedback, context):
            _ = (control, candidates, feedback, context)

    role = RoleAdapter(
        "tester",
        Dummy(),
        context_requires=("need_this",),
        strict_contract=True,
    )

    try:
        role.propose(object(), {})
        assert False, "expected KeyError"
    except KeyError as e:
        assert "need_this" in str(e)


def test_multi_role_controller_adapter_runs_with_composable_solver():
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import AlgorithmAdapter, RoleAdapter, RoleRouterAdapter
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, GaussianMutation, ClipRepair

    class Sphere(BlackBoxProblem):
        def __init__(self, dim=4, low=-5.0, high=5.0):
            super().__init__(name="sphere", dimension=dim, bounds={f"x{i}": (low, high) for i in range(dim)})
            self.low, self.high = low, high

        def evaluate(self, candidate):
            candidate = np.asarray(candidate, dtype=float)
            return float(np.sum(candidate * candidate))

    class Explorer(AlgorithmAdapter):
        def __init__(self):
            super().__init__(name="explorer_inner")

        def propose(self, control, context):
            return [control.mutate_candidate(control.init_candidate(context), context) for _ in range(8)]

        def update(self, control, candidates, feedback, context):
            _ = (control, candidates, feedback, context)

    class Exploiter(AlgorithmAdapter):
        def __init__(self):
            super().__init__(name="exploiter_inner")

        def propose(self, control, context):
            if control.best_x is None:
                return [control.init_candidate(context) for _ in range(8)]
            return [control.mutate_candidate(control.best_x, context) for _ in range(8)]

        def update(self, control, candidates, feedback, context):
            _ = (control, candidates, feedback, context)

    problem = Sphere()
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=problem.low, high=problem.high),
        mutator=GaussianMutation(sigma=0.5, low=problem.low, high=problem.high),
        repair=ClipRepair(low=problem.low, high=problem.high),
    )

    controller = RoleRouterAdapter(
        [
            RoleAdapter("explorer", Explorer(), max_candidates=8),
            RoleAdapter("exploiter", Exploiter(), max_candidates=8),
        ]
    )

    control = ComposableSolver(problem=problem, adapter=controller, representation_pipeline=pipeline)
    control.max_steps = 5
    result = control.run()

    assert result["status"] in {"ok", "stopped"}
    assert control.best_objective is not None
    ctx = control.get_context()
    assert isinstance(ctx.get("candidate_roles"), list)
    assert isinstance(ctx.get("role_reports"), dict)


def test_role_router_rejects_ambiguous_adapter_names():
    from nsgablack.adapters import AlgorithmAdapter, RoleAdapter, RoleRouterAdapter

    class Dummy(AlgorithmAdapter):
        def propose(self, control, context):
            del control, context
            return ()

        def update(self, control, candidates, feedback, context):
            del control, candidates, feedback, context

    with pytest.raises(ValueError, match="names must be unique"):
        RoleRouterAdapter(
            [
                RoleAdapter("first", Dummy("first"), name="duplicate"),
                RoleAdapter("second", Dummy("second"), name="duplicate"),
            ]
        )


def test_role_adapter_restore_rejects_builder_role_mismatch():
    from nsgablack.adapters import AlgorithmAdapter, RoleAdapter

    class Dummy(AlgorithmAdapter):
        def propose(self, control, context):
            del control, context
            return ()

        def update(self, control, candidates, feedback, context):
            del control, candidates, feedback, context

    source = RoleAdapter("source", Dummy("inner"), name="role")
    target = RoleAdapter("target", Dummy("inner"), name="role")

    with pytest.raises(ValueError, match="identity mismatch"):
        target.set_state(source.get_state())
