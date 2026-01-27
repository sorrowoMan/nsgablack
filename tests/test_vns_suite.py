def test_attach_vns_can_upgrade_gaussian_mutator(sample_problem):
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, GaussianMutation, ClipRepair, ContextGaussianMutation
    from nsgablack.utils.suites import attach_vns

    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=-5.0, high=5.0),
        mutator=GaussianMutation(sigma=0.6, low=-5.0, high=5.0),
        repair=ClipRepair(low=-5.0, high=5.0),
    )

    solver = ComposableSolver(problem=sample_problem, representation_pipeline=pipeline)
    attach_vns(solver, batch_size=4, k_max=2, ensure_context_mutator=True)

    assert isinstance(solver.representation_pipeline.mutator, ContextGaussianMutation)

