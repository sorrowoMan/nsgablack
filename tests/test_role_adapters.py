import numpy as np


def test_role_adapter_contract_strict_requires_keys():
    from nsgablack.adapters import AlgorithmAdapter, RoleAdapter

    class Dummy(AlgorithmAdapter):
        def __init__(self):
            super().__init__(name="dummy")

        def propose(self, solver, context):
            return []

    role = RoleAdapter(
        "tester",
        Dummy(),
        requires_context_keys=("need_this",),
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
    from nsgablack.adapters import AlgorithmAdapter, RoleAdapter, MultiRoleControllerAdapter
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, GaussianMutation, ClipRepair

    class Sphere(BlackBoxProblem):
        def __init__(self, dim=4, low=-5.0, high=5.0):
            super().__init__(name="sphere", dimension=dim, bounds={f"x{i}": (low, high) for i in range(dim)})
            self.low, self.high = low, high

        def evaluate(self, x):
            x = np.asarray(x, dtype=float)
            return float(np.sum(x * x))

    class Explorer(AlgorithmAdapter):
        def __init__(self):
            super().__init__(name="explorer_inner")

        def propose(self, solver, context):
            return [solver.mutate_candidate(solver.init_candidate(context), context) for _ in range(8)]

    class Exploiter(AlgorithmAdapter):
        def __init__(self):
            super().__init__(name="exploiter_inner")

        def propose(self, solver, context):
            if solver.best_x is None:
                return [solver.init_candidate(context) for _ in range(8)]
            return [solver.mutate_candidate(solver.best_x, context) for _ in range(8)]

    problem = Sphere()
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=problem.low, high=problem.high),
        mutator=GaussianMutation(sigma=0.5, low=problem.low, high=problem.high),
        repair=ClipRepair(low=problem.low, high=problem.high),
    )

    controller = MultiRoleControllerAdapter(
        [
            RoleAdapter("explorer", Explorer(), max_candidates=8),
            RoleAdapter("exploiter", Exploiter(), max_candidates=8),
        ]
    )

    solver = ComposableSolver(problem=problem, adapter=controller, representation_pipeline=pipeline)
    solver.max_steps = 5
    result = solver.run()

    assert result["status"] in {"completed", "stopped"}
    assert solver.best_objective is not None
    ctx = solver.get_context()
    assert isinstance(ctx.get("candidate_roles"), list)
    assert isinstance(ctx.get("role_reports"), dict)
