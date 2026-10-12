import pytest

from blackbase.project import collect_failure_evidence
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.core.semantic_extension import SolverSemanticExtension
from nsgablack.adapters.algorithm_adapter import AlgorithmAdapter


def solver():
    return ComposableSolver(BlackBoxProblem(name="ports", dimension=1, bounds={"x0": (-1, 1)}))


def test_semantic_ports_share_reset_setup_restore_context_and_deadline():
    events = []
    component = object()

    class Extension(SolverSemanticExtension):
        def prepare_run(self, control):
            events.append("prepare")

        def setup(self, control):
            events.append("setup")

        def project_context(self, control, context):
            return {**context, "semantic_value": len(events)}

        def checkpoint_components(self, control):
            return {"semantic_component": component}

        def should_execute_step(self, control, index):
            events.append("predicate")
            return True

    control = solver()
    control.register_semantic_extension(Extension())
    def restore():
        events.append("restore")
        control.run_session.mark_restored(0)
    control.queue_restore_envelope(restore)
    control.prepare_fresh_run()
    control.setup()
    control._apply_pending_restore_envelopes()
    assert events == ["prepare", "setup", "restore"]
    assert control.build_context()["semantic_value"] == 3
    assert control.checkpoint_components()["semantic_component"] is component
    assert control.should_execute_step(0)
    control._run_progress_deadline_remaining_seconds = 0
    assert not control.should_execute_step(0)
    assert events.count("predicate") == 1


def test_checkpoint_extension_cannot_replace_control_plane_owner():
    class Collision(SolverSemanticExtension):
        def checkpoint_components(self, control):
            return {"runtime_controller": object()}

    control = solver()
    control.register_semantic_extension(Collision())
    with pytest.raises(ValueError, match="duplicate checkpoint component owner"):
        control.checkpoint_components()


def test_cleanup_runs_all_after_adapter_failure_and_carries_transport_evidence():
    events = []

    def fail(name, error):
        def operation():
            events.append(name)
            raise error
        return operation

    class Adapter(AlgorithmAdapter):
        def propose(self, control, context):
            return ()

        def update(self, control, candidates, feedback, context):
            pass

        def teardown(self, control):
            fail("adapter", ValueError("adapter failure"))()

    class Extension(SolverSemanticExtension):
        def cleanup_components(self, control):
            return {"resource_a": fail("a", RuntimeError("a failure")),
                    "resource_b": fail("b", OSError("b failure"))}

    control = solver()
    control.set_adapter(Adapter(name="adapter"))
    control.register_semantic_extension(Extension())
    with pytest.raises(ValueError, match="adapter failure") as captured:
        control.teardown()
    assert events == ["adapter", "a", "b"]
    assert len(collect_failure_evidence(captured.value)["solver_teardown"]) == 3


def test_cleanup_discovery_failure_does_not_skip_other_extensions():
    events = []

    class Broken(SolverSemanticExtension):
        name = "broken"
        def cleanup_components(self, control):
            raise ValueError("discovery failed")

    class Working(SolverSemanticExtension):
        name = "working"
        def cleanup_components(self, control):
            return {"resource": lambda: events.append("closed")}

    control = solver()
    control.register_semantic_extension(Broken())
    control.register_semantic_extension(Working())
    with pytest.raises(ValueError, match="discovery failed"):
        control.teardown()
    assert events == ["closed"]
