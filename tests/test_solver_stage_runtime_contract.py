from __future__ import annotations

from nsgablack.core.solver_stage import CompletionPolicy, StageRunner, StageSpec


def test_stage_runner_does_not_teardown_a_run_entrypoint_twice() -> None:
    class Runnable:
        def __init__(self) -> None:
            self.teardown_count = 0

        def teardown(self) -> None:
            self.teardown_count += 1

        def run(self):
            try:
                return {"status": "ok"}
            finally:
                self.teardown()

    case = Runnable()
    runner = StageRunner([StageSpec(name="run_case", factory=lambda: case)])

    runner.run()

    assert case.teardown_count == 1


def test_stage_runner_owns_manual_step_lifecycle_and_injects_parent_resource_context() -> None:
    class StepOnly:
        def __init__(self, resource_context) -> None:
            self.resource_context = dict(resource_context)
            self.setup_count = 0
            self.teardown_count = 0
            self.steps = 0

        def setup(self) -> None:
            self.setup_count += 1

        def step(self) -> None:
            self.steps += 1

        def teardown(self) -> None:
            self.teardown_count += 1

    built: list[StepOnly] = []

    def factory(*, resource_context):
        case = StepOnly(resource_context)
        built.append(case)
        return case

    runner = StageRunner(
        [
            StageSpec(
                name="step_case",
                factory=factory,
                completion=CompletionPolicy(max_steps=2),
            )
        ],
        resource_context={"threads": 2, "namespace": "project.outer"},
    )

    result = runner.run()

    assert result["stage_count"] == 1
    assert built[0].resource_context["threads"] == 2
    assert built[0].setup_count == 1
    assert built[0].steps == 2
    assert built[0].teardown_count == 1
