from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from blackbase.context import RuntimeContextProjection, RuntimeProjectionIssue
from blackbase.resources import DataRef
from nsgablack.adapters import (
    AlgorithmAdapter,
    AsyncEventDrivenAdapter,
    CompositeAdapter,
    EventCaseSpec,
    EventStrategySpec,
    RoleAdapter,
    RoleRouterAdapter,
    SerialPhaseSpec,
    StrategyChainAdapter,
)
from nsgablack.adapters.differential_evolution import (
    DEConfig,
    DifferentialEvolutionAdapter,
)
from nsgablack.adapters.nsga2 import NSGA2Adapter, NSGA2Config
from nsgablack.adapters.multi_strategy.adapter import (
    StrategyRouterAdapter,
    StrategySpec,
)
from nsgablack.adapters.simulated_annealing import (
    SAConfig,
    SimulatedAnnealingAdapter,
)
from nsgablack.core.solver_helpers.control_plane_helpers import (
    collect_runtime_context_projection,
)
from nsgablack.core.solver_helpers import control_plane_helpers
from nsgablack.core import BlackBoxProblem, IncumbentState, SolverBase
from nsgablack.core.state.context_keys import (
    KEY_ADAPTER_BEST_OBJECTIVES,
    KEY_ADAPTER_BEST_SCORE,
    KEY_ADAPTER_BEST_X,
    KEY_BEST_CANDIDATE_REF,
    KEY_BEST_OBJECTIVE,
    KEY_BEST_X,
    KEY_EVALUATION_COUNT,
    KEY_GENERATION,
    KEY_RUNTIME_PROJECTION_AUDIT,
)


class _ProjectionSolver:
    def __init__(self, adapter) -> None:
        self.adapter = adapter
        self.generation = 7
        self.evaluation_count = 11
        self.best_x = np.asarray([1.0, 2.0])
        self.best_objective = 3.0
        self.context_store = None

    def get_incumbent(self):
        return None


class _ProjectionHealthAdapter(AlgorithmAdapter):
    def __init__(self, projection: RuntimeContextProjection, *, name: str) -> None:
        super().__init__(name=name)
        self.projection = projection
        self.projection_calls = 0

    def propose(self, control, context):
        del control, context
        return []

    def update(self, control, candidates, feedback, context):
        del control, candidates, feedback, context

    def get_runtime_context_projection(self, solver):
        del solver
        self.projection_calls += 1
        return self.projection


def _failed_projection(component: str) -> RuntimeContextProjection:
    return RuntimeContextProjection(
        status="error",
        component_count=1,
        failed_component_count=1,
        issue_samples=(RuntimeProjectionIssue(component, "error"),),
    )


def test_adapter_projection_cannot_overwrite_solver_owned_runtime_fields() -> None:
    class ConflictingAdapter:
        def __init__(self) -> None:
            self.calls = 0

        def get_runtime_context_projection(self, solver):
            assert solver is not None
            self.calls += 1
            return {
                KEY_GENERATION: -1,
                KEY_EVALUATION_COUNT: -2,
                KEY_BEST_X: np.asarray([9.0, 9.0]),
                KEY_BEST_CANDIDATE_REF: "snapshot://wrong",
                KEY_BEST_OBJECTIVE: np.asarray([9.0, 9.0]),
                KEY_ADAPTER_BEST_SCORE: 18.0,
            }

    adapter = ConflictingAdapter()
    solver = _ProjectionSolver(adapter)
    reports = []

    projection = collect_runtime_context_projection(
        solver,
        report_soft_error_fn=lambda **payload: reports.append(payload),
    )

    assert adapter.calls == 1
    assert projection[KEY_GENERATION] == 7
    assert projection[KEY_EVALUATION_COUNT] == 11
    assert np.allclose(projection[KEY_BEST_X], [1.0, 2.0])
    assert projection[KEY_BEST_OBJECTIVE] == 3.0
    assert KEY_BEST_CANDIDATE_REF not in projection
    assert projection[KEY_ADAPTER_BEST_SCORE] == 18.0
    assert len(reports) == 1
    assert reports[0]["event"] == "adapter_runtime_context_projection_reserved_keys"
    assert "best_objective" in str(reports[0]["exc"])


def test_adapter_projection_internal_type_error_is_not_retried() -> None:
    class BrokenAdapter:
        def __init__(self) -> None:
            self.calls = 0

        def get_runtime_context_projection(self, solver):
            assert solver is not None
            self.calls += 1
            raise TypeError("projection body failed")

    adapter = BrokenAdapter()
    solver = _ProjectionSolver(adapter)
    reports = []

    projection = collect_runtime_context_projection(
        solver,
        report_soft_error_fn=lambda **payload: reports.append(payload),
    )

    assert adapter.calls == 1
    assert projection[KEY_GENERATION] == 7
    assert len(reports) == 1
    assert reports[0]["event"] == "adapter_runtime_context_projection"
    assert str(reports[0]["exc"]) == "projection body failed"
    audit = projection[KEY_RUNTIME_PROJECTION_AUDIT]
    assert audit["status"] == "error"
    assert audit["current"] is False
    assert audit["projection_error"]["type"] == "TypeError"
    assert audit["projection_error"]["message"] == "projection body failed"


def test_adapter_projection_rejects_non_mapping_result_as_unhealthy() -> None:
    class InvalidAdapter:
        def get_runtime_context_projection(self, solver):
            assert solver is not None
            return ["not", "a", "mapping"]

    solver = _ProjectionSolver(InvalidAdapter())
    reports = []

    projection = collect_runtime_context_projection(
        solver,
        report_soft_error_fn=lambda **payload: reports.append(payload),
    )

    audit = projection[KEY_RUNTIME_PROJECTION_AUDIT]
    assert audit["status"] == "invalid_result"
    assert audit["current"] is False
    assert audit["projection_error"]["type"] == "TypeError"
    assert "must return a Mapping" in audit["projection_error"]["message"]
    assert [item["event"] for item in reports] == [
        "adapter_runtime_context_projection_invalid_result"
    ]


def test_runtime_projection_error_summary_is_bounded() -> None:
    class BrokenAdapter:
        def get_runtime_context_projection(self, solver):
            assert solver is not None
            raise RuntimeError("z" * 10_000)

    solver = _ProjectionSolver(BrokenAdapter())
    reports = []

    projection = collect_runtime_context_projection(
        solver,
        report_soft_error_fn=lambda **payload: reports.append(payload),
    )

    audit = projection[KEY_RUNTIME_PROJECTION_AUDIT]
    error = audit["projection_error"]
    assert audit["status"] == "error"
    assert audit["current"] is False
    assert audit["audit_truncated"] is True
    assert error["message_truncated"] is True
    assert len(error["message"].encode("utf-8")) <= 384
    assert len(error["message_hash"]) == 64
    assert len(json.dumps(audit, ensure_ascii=False).encode("utf-8")) <= 4_096
    assert len(reports) == 1
    assert len(str(reports[0]["exc"]).encode("utf-8")) <= 384


def test_missing_adapter_projector_is_healthy_unavailable() -> None:
    solver = _ProjectionSolver(object())

    projection = collect_runtime_context_projection(solver)

    audit = projection[KEY_RUNTIME_PROJECTION_AUDIT]
    assert audit["status"] == "unavailable"
    assert audit["current"] is True
    assert audit["projection_error"] is None


def test_oversized_adapter_best_candidate_is_not_exposed_in_context() -> None:
    class Adapter:
        def get_runtime_context_projection(self, solver):
            return {
                KEY_ADAPTER_BEST_X: np.arange(100, dtype=float),
                KEY_ADAPTER_BEST_OBJECTIVES: np.asarray([1.0, 2.0]),
                KEY_ADAPTER_BEST_SCORE: 3.0,
            }

    solver = _ProjectionSolver(Adapter())
    solver._candidate_can_inline_in_context = lambda candidate: False

    projection = collect_runtime_context_projection(solver)

    assert KEY_ADAPTER_BEST_X not in projection
    assert np.allclose(projection[KEY_ADAPTER_BEST_OBJECTIVES], [1.0, 2.0])
    assert projection[KEY_ADAPTER_BEST_SCORE] == 3.0
    audit = projection[KEY_RUNTIME_PROJECTION_AUDIT]
    assert audit["current"] is False
    assert audit["omitted_fields"][0]["key"] == KEY_ADAPTER_BEST_X
    assert audit["omitted_fields"][0]["reason"] == "candidate_inline_limit"


def test_direct_collector_uses_bounded_authoritative_incumbent_projection() -> None:
    class Problem(BlackBoxProblem):
        def __init__(self) -> None:
            super().__init__(dimension=512, objectives=("cost",))

        def evaluate(self, candidate, context=None):
            del context
            return np.asarray([np.sum(np.asarray(candidate, dtype=float))])

    solver = SolverBase(Problem(), context_inline_candidate_max_bytes=1)
    solver.set_incumbent(
        IncumbentState(
            candidate=np.arange(512, dtype=float),
            objectives=np.asarray([1.0]),
            constraint_violation=0.0,
            score=1.0,
            policy_id="objective_sum/v1",
            evaluation_id="eval-large",
        )
    )

    projection = collect_runtime_context_projection(solver)

    assert KEY_BEST_X not in projection
    assert projection[KEY_BEST_CANDIDATE_REF]
    assert projection[KEY_BEST_OBJECTIVE] == 1.0


def test_arbitrary_oversized_adapter_field_is_omitted_and_audited() -> None:
    class Adapter:
        def get_runtime_context_projection(self, solver):
            del solver
            return {
                "huge_matrix": np.zeros((64, 64), dtype=float),
                KEY_ADAPTER_BEST_SCORE: 2.0,
            }

    solver = _ProjectionSolver(Adapter())
    solver.runtime_context_projection_field_max_bytes = 128
    solver.runtime_context_projection_total_max_bytes = 1_024
    reports = []

    projection = collect_runtime_context_projection(
        solver,
        report_soft_error_fn=lambda **payload: reports.append(payload),
    )

    assert "huge_matrix" not in projection
    assert projection[KEY_ADAPTER_BEST_SCORE] == 2.0
    audit = projection[KEY_RUNTIME_PROJECTION_AUDIT]
    assert audit["current"] is False
    assert len(audit["omitted_fields"]) == 1
    omitted = audit["omitted_fields"][0]
    assert omitted["key"] == "huge_matrix"
    assert omitted["reason"] == "field_limit"
    assert omitted["estimated_bytes"] > 128
    assert [item["event"] for item in reports] == [
        "adapter_runtime_context_projection_budget"
    ]


def test_adapter_runtime_projection_has_an_aggregate_budget() -> None:
    class Adapter:
        def get_runtime_context_projection(self, solver):
            del solver
            return {
                "first": "a" * 60,
                "second": "b" * 60,
                "third": "c" * 60,
            }

    solver = _ProjectionSolver(Adapter())
    solver.runtime_context_projection_field_max_bytes = 100
    solver.runtime_context_projection_total_max_bytes = 135

    projection = collect_runtime_context_projection(solver)

    assert projection["first"] == "a" * 60
    assert projection["second"] == "b" * 60
    assert "third" not in projection
    assert projection[KEY_RUNTIME_PROJECTION_AUDIT]["omitted_fields"] == [
        {"key": "third", "reason": "total_limit", "estimated_bytes": 60}
    ]


def test_runtime_projection_audit_and_soft_error_are_bounded() -> None:
    field_count = 10_000
    long_suffix = "x" * 256

    class Adapter:
        def get_runtime_context_projection(self, solver):
            del solver
            return {
                f"oversized_{index}_{long_suffix}": "y" * 64
                for index in range(field_count)
            }

    solver = _ProjectionSolver(Adapter())
    solver.runtime_context_projection_field_max_bytes = 8
    solver.runtime_context_projection_total_max_bytes = 64
    reports = []

    projection = collect_runtime_context_projection(
        solver,
        report_soft_error_fn=lambda **payload: reports.append(payload),
    )

    audit = projection[KEY_RUNTIME_PROJECTION_AUDIT]
    assert audit["status"] == "ok"
    assert audit["current"] is False
    assert audit["omitted_field_count"] == field_count
    assert audit["reason_counts"] == {"field_limit": field_count}
    assert len(audit["omitted_fields"]) == audit["audit_sample_limit"] == 16
    assert audit["audit_truncated"] is True
    assert all(item.get("key_truncated") is True for item in audit["omitted_fields"])
    assert all(len(item.get("key_hash", "")) == 16 for item in audit["omitted_fields"])
    assert len(audit["signature"]) == 64
    assert len(json.dumps(audit, ensure_ascii=False).encode("utf-8")) <= 4_096
    assert len(reports) == 1
    assert reports[0]["event"] == "adapter_runtime_context_projection_budget"
    assert len(str(reports[0]["exc"]).encode("utf-8")) <= 512

    repeated = collect_runtime_context_projection(
        solver,
        report_soft_error_fn=lambda **payload: reports.append(payload),
    )
    assert repeated[KEY_RUNTIME_PROJECTION_AUDIT]["signature"] == audit["signature"]
    assert len(reports) == 1


def test_fresh_run_resets_runtime_projection_audit_and_report_signature() -> None:
    class Problem(BlackBoxProblem):
        def __init__(self) -> None:
            super().__init__(dimension=1, objectives=("cost",))

        def evaluate(self, candidate, context=None):
            del context
            return np.asarray([float(np.asarray(candidate)[0])])

    class BrokenAdapter:
        def get_runtime_context_projection(self, solver):
            assert solver is not None
            raise TypeError("same failure in every run")

    solver = SolverBase(Problem())
    solver.adapter = BrokenAdapter()
    reports = []

    solver.prepare_fresh_run()
    collect_runtime_context_projection(
        solver,
        report_soft_error_fn=lambda **payload: reports.append(payload),
    )
    collect_runtime_context_projection(
        solver,
        report_soft_error_fn=lambda **payload: reports.append(payload),
    )
    assert len(reports) == 1
    assert solver.get_runtime_projection_audit()["status"] == "error"

    solver.prepare_fresh_run()
    assert solver.get_runtime_projection_audit() == {}
    assert solver._runtime_projection_audit_report_signature is None
    collect_runtime_context_projection(
        solver,
        report_soft_error_fn=lambda **payload: reports.append(payload),
    )
    assert len(reports) == 2
    assert reports[0]["event"] == reports[1]["event"]


def test_formal_lightweight_data_ref_can_cross_runtime_projection_gate() -> None:
    ref = DataRef(
        uri="artifact://runtime/weights",
        media_type="application/json",
        metadata={"lineage": {"runs": ["run-1"]}},
    )

    class Adapter:
        def get_runtime_context_projection(self, solver):
            del solver
            return {"weights_ref": ref}

    solver = _ProjectionSolver(Adapter())
    solver.runtime_context_projection_field_max_bytes = 512
    solver.runtime_context_projection_total_max_bytes = 1_024

    projection = collect_runtime_context_projection(solver)

    assert projection["weights_ref"] is not ref
    detached = projection["weights_ref"].as_dict()
    detached["metadata"]["lineage"]["runs"].append("run-2")
    assert ref.as_dict()["metadata"] == {"lineage": {"runs": ["run-1"]}}
    assert projection["weights_ref"].as_dict()["metadata"] == {
        "lineage": {"runs": ["run-1"]}
    }
    assert projection[KEY_RUNTIME_PROJECTION_AUDIT]["current"] is True


def test_runtime_projection_detaches_sa_array_from_adapter_state() -> None:
    adapter = SimulatedAnnealingAdapter(SAConfig(batch_size=1))
    adapter.current_x = np.asarray([1.0, 2.0])
    adapter._last_runtime_projection = {"sa_current_x": adapter.current_x}
    solver = _ProjectionSolver(adapter)

    projection = collect_runtime_context_projection(solver)
    projection["sa_current_x"][0] = 99.0

    assert adapter.current_x.tolist() == [1.0, 2.0]


def test_runtime_projection_detaches_multi_strategy_shared_state() -> None:
    controller = StrategyRouterAdapter(strategies=[])
    controller.shared_state = {
        "best_score": 4.0,
        "nested": {"history": [1, 2], "vector": np.asarray([3.0, 4.0])},
    }
    controller._runtime_shared_projection = {"shared": controller.shared_state}
    solver = _ProjectionSolver(controller)

    projection = collect_runtime_context_projection(solver)
    projection["shared"]["best_score"] = -999.0
    projection["shared"]["nested"]["history"].append(3)
    projection["shared"]["nested"]["vector"][0] = -1.0

    assert controller.shared_state["best_score"] == 4.0
    assert controller.shared_state["nested"]["history"] == [1, 2]
    assert controller.shared_state["nested"]["vector"].tolist() == [3.0, 4.0]


def test_reserved_fake_audit_cannot_consume_projection_budget() -> None:
    class Adapter:
        def get_runtime_context_projection(self, solver):
            del solver
            return {
                KEY_RUNTIME_PROJECTION_AUDIT: "x" * 100_000,
                "valid_metric": "v" * 40,
            }

    solver = _ProjectionSolver(Adapter())
    solver.runtime_context_projection_field_max_bytes = 64
    solver.runtime_context_projection_total_max_bytes = 64

    projection = collect_runtime_context_projection(solver)
    audit = projection[KEY_RUNTIME_PROJECTION_AUDIT]

    assert projection["valid_metric"] == "v" * 40
    assert audit["conflict_count"] == 1
    assert audit["reserved_conflicts"] == [KEY_RUNTIME_PROJECTION_AUDIT]
    assert audit["omitted_field_count"] == 0


def test_runtime_projection_audit_copies_are_recursively_detached() -> None:
    class Adapter:
        def get_runtime_context_projection(self, solver):
            del solver
            return {"oversized": "x" * 128}

    solver = _ProjectionSolver(Adapter())
    solver.runtime_context_projection_field_max_bytes = 8
    projection = collect_runtime_context_projection(solver)
    exposed = projection[KEY_RUNTIME_PROJECTION_AUDIT]

    exposed["reason_counts"]["field_limit"] = -1
    exposed["omitted_fields"][0]["reason"] = "rewritten"

    assert solver._runtime_projection_audit["reason_counts"] == {"field_limit": 1}
    assert solver._runtime_projection_audit["omitted_fields"][0]["reason"] == "field_limit"


def test_multi_strategy_reports_partial_child_projection_failure() -> None:
    class GoodAdapter:
        def get_runtime_context_projection(self, solver):
            del solver
            return {"child_metric": 7}

    class BrokenAdapter:
        def get_runtime_context_projection(self, solver):
            del solver
            raise TypeError("child body failed")

    controller = StrategyRouterAdapter(
        strategies=(
            StrategySpec(adapter=GoodAdapter(), name="good"),
            StrategySpec(adapter=BrokenAdapter(), name="broken"),
        )
    )
    controller.units = controller._build_units()
    solver = _ProjectionSolver(controller)
    reports = []

    projection = collect_runtime_context_projection(
        solver,
        report_soft_error_fn=lambda **payload: reports.append(payload),
    )
    audit = projection[KEY_RUNTIME_PROJECTION_AUDIT]

    assert projection["child_metric"] == 7
    assert audit["status"] == "degraded"
    assert audit["current"] is False
    assert audit["component_audit"]["component_count"] == 2
    assert audit["component_audit"]["successful_component_count"] == 1
    assert audit["component_audit"]["failed_component_count"] == 1
    assert audit["component_audit"]["issue_samples"][0]["reason"] == "error"
    assert [item["event"] for item in reports] == [
        "adapter_runtime_context_projection_degraded"
    ]


def test_multi_strategy_reports_error_when_all_child_projections_fail() -> None:
    class InvalidAdapter:
        def get_runtime_context_projection(self, solver):
            del solver
            return ["invalid"]

    controller = StrategyRouterAdapter(
        strategies=(StrategySpec(adapter=InvalidAdapter(), name="invalid"),)
    )
    controller.units = controller._build_units()
    solver = _ProjectionSolver(controller)

    projection = collect_runtime_context_projection(solver)
    audit = projection[KEY_RUNTIME_PROJECTION_AUDIT]

    assert audit["status"] == "error"
    assert audit["current"] is False
    assert audit["component_audit"]["invalid_component_count"] == 1


def test_multi_strategy_propagates_nested_projection_cause_digest() -> None:
    def nested_failure(component: str) -> RuntimeContextProjection:
        return RuntimeContextProjection(
            status="error",
            component_count=1,
            failed_component_count=1,
            issue_samples=(
                RuntimeProjectionIssue(component=component, reason="error"),
            ),
        )

    class NestedAdapter:
        def __init__(self) -> None:
            self.projection = nested_failure("grandchild-a")

        def get_runtime_context_projection(self, solver):
            del solver
            return self.projection

    nested = NestedAdapter()
    controller = StrategyRouterAdapter(
        strategies=(StrategySpec(adapter=nested, name="nested"),)
    )
    controller.units = controller._build_units()
    solver = _ProjectionSolver(controller)
    reports = []

    first = collect_runtime_context_projection(
        solver,
        report_soft_error_fn=lambda **payload: reports.append(payload),
    )[KEY_RUNTIME_PROJECTION_AUDIT]
    first_child_digest = nested.projection.audit_digest

    nested.projection = nested_failure("grandchild-b")
    second = collect_runtime_context_projection(
        solver,
        report_soft_error_fn=lambda **payload: reports.append(payload),
    )[KEY_RUNTIME_PROJECTION_AUDIT]
    second_child_digest = nested.projection.audit_digest

    assert first["component_audit"]["component_count"] == 1
    assert second["component_audit"]["component_count"] == 1
    assert first["component_audit"]["failed_component_count"] == 1
    assert second["component_audit"]["failed_component_count"] == 1
    assert first["component_audit"]["issue_samples"][0]["cause_digest"] == (
        first_child_digest
    )
    assert second["component_audit"]["issue_samples"][0]["cause_digest"] == (
        second_child_digest
    )
    assert first_child_digest != second_child_digest
    assert first["component_audit"]["audit_digest"] != second["component_audit"][
        "audit_digest"
    ]
    assert first["signature"] != second["signature"]
    assert len(reports) == 2


def test_all_composite_adapters_propagate_child_projection_health() -> None:
    cases = []

    composite_child = _ProjectionHealthAdapter(
        _failed_projection("composite-grandchild"),
        name="composite-child",
    )
    cases.append((CompositeAdapter([composite_child]), composite_child))

    async_child = _ProjectionHealthAdapter(
        _failed_projection("async-grandchild"),
        name="async-child",
    )
    cases.append(
        (
            AsyncEventDrivenAdapter(
                [EventStrategySpec(adapter=async_child, name="async")]
            ),
            async_child,
        )
    )

    role_child = _ProjectionHealthAdapter(
        _failed_projection("role-grandchild"),
        name="role-child",
    )
    cases.append((RoleAdapter("worker", role_child), role_child))

    router_child = _ProjectionHealthAdapter(
        _failed_projection("router-grandchild"),
        name="router-child",
    )
    cases.append(
        (
            RoleRouterAdapter([RoleAdapter("worker", router_child)]),
            router_child,
        )
    )

    serial_child = _ProjectionHealthAdapter(
        _failed_projection("serial-grandchild"),
        name="serial-child",
    )
    serial = StrategyChainAdapter(
        [SerialPhaseSpec(name="active", adapter=serial_child)]
    )
    serial.setup(None)
    cases.append((serial, serial_child))

    for adapter, child in cases:
        projection = adapter.get_runtime_context_projection(None)
        audit = projection.as_audit()

        assert projection.status == "error", adapter.__class__.__name__
        assert projection.component_count == 1, adapter.__class__.__name__
        assert projection.failed_component_count == 1, adapter.__class__.__name__
        assert audit["issue_samples"][0]["reason"] == "nested_error"
        assert len(audit["issue_samples"][0]["cause_digest"]) == 64
        assert child.projection_calls == 1, adapter.__class__.__name__


def test_strategy_chain_only_projects_the_active_child() -> None:
    active = _ProjectionHealthAdapter(
        _failed_projection("active-grandchild"),
        name="active-child",
    )
    inactive = _ProjectionHealthAdapter(
        _failed_projection("inactive-grandchild"),
        name="inactive-child",
    )
    chain = StrategyChainAdapter(
        [
            SerialPhaseSpec(name="active", adapter=active),
            SerialPhaseSpec(name="inactive", adapter=inactive),
        ]
    )
    chain.setup(None)

    projection = chain.get_runtime_context_projection(None)

    assert projection.component_count == 1
    assert projection.status == "error"
    assert active.projection_calls == 1
    assert inactive.projection_calls == 0


def test_async_event_case_only_projects_the_active_child() -> None:
    active = _ProjectionHealthAdapter(
        _failed_projection("active-event-grandchild"),
        name="active-event",
    )
    inactive = _ProjectionHealthAdapter(
        _failed_projection("inactive-event-grandchild"),
        name="inactive-event",
    )
    router = AsyncEventDrivenAdapter(
        [
            EventCaseSpec(adapter=active, name="active"),
            EventCaseSpec(adapter=inactive, name="inactive"),
        ]
    )
    router._active_case_name = "active"

    projection = router.get_runtime_context_projection(None)

    assert projection.component_count == 1
    assert projection.status == "error"
    assert active.projection_calls == 1
    assert inactive.projection_calls == 0


def test_async_event_case_before_selection_projects_no_children() -> None:
    first = _ProjectionHealthAdapter(
        _failed_projection("first-event-grandchild"),
        name="first-event",
    )
    second = _ProjectionHealthAdapter(
        _failed_projection("second-event-grandchild"),
        name="second-event",
    )
    router = AsyncEventDrivenAdapter(
        [
            EventCaseSpec(adapter=first, name="first"),
            EventCaseSpec(adapter=second, name="second"),
        ]
    )

    projection = router.get_runtime_context_projection(None)

    assert router._active_case_name is None
    assert projection.status == "ok"
    assert projection.component_count == 0
    assert first.projection_calls == 0
    assert second.projection_calls == 0


def test_solver_runtime_audit_preserves_recursive_leaf_field_writer() -> None:
    leaf = _ProjectionHealthAdapter(
        RuntimeContextProjection(
            fields={"leaf_metric": 7},
            field_sources={"leaf_metric": "adapter.actual_leaf"},
        ),
        name="leaf",
    )
    nested = CompositeAdapter([CompositeAdapter([leaf])])
    solver = _ProjectionSolver(nested)

    projection = collect_runtime_context_projection(solver)
    audit = projection[KEY_RUNTIME_PROJECTION_AUDIT]

    assert projection["leaf_metric"] == 7
    assert audit["field_sources_current"] is True
    assert audit["field_source_count"] == 1
    assert audit["field_source_samples"] == [
        {"key": "leaf_metric", "source": "adapter.actual_leaf"}
    ]
    assert len(audit["field_source_digest"]) == 64


def test_runtime_field_writer_evidence_has_a_hard_audit_budget() -> None:
    class Adapter:
        def get_runtime_context_projection(self, solver):
            del solver
            return {f"metric_{index}": index for index in range(100)}

        def get_runtime_context_projection_sources(self, solver):
            del solver
            return {
                f"metric_{index}": "adapter." + ("very-long-source-" * 100)
                for index in range(100)
            }

    solver = _ProjectionSolver(Adapter())
    projection = collect_runtime_context_projection(solver)
    audit = projection[KEY_RUNTIME_PROJECTION_AUDIT]

    assert audit["field_source_count"] == 100
    assert len(audit["field_source_samples"]) <= 16
    assert audit["field_source_samples"]
    assert all(
        item.get("source_truncated") is True
        for item in audit["field_source_samples"]
    )
    assert audit["audit_truncated"] is True
    assert len(audit["field_source_digest"]) == 64
    assert len(json.dumps(audit, ensure_ascii=False).encode("utf-8")) <= 4_096


def test_multi_strategy_only_projects_enabled_units() -> None:
    enabled = _ProjectionHealthAdapter(
        _failed_projection("enabled-unit-grandchild"),
        name="enabled-unit",
    )
    disabled = _ProjectionHealthAdapter(
        _failed_projection("disabled-unit-grandchild"),
        name="disabled-unit",
    )
    controller = StrategyRouterAdapter(
        strategies=(
            StrategySpec(adapter=enabled, name="enabled", enabled=True),
            StrategySpec(adapter=disabled, name="disabled", enabled=False),
        )
    )
    controller.units = controller._build_units()

    projection = controller.get_runtime_context_projection(None)

    assert projection.component_count == 1
    assert projection.status == "error"
    assert enabled.projection_calls == 1
    assert disabled.projection_calls == 0


def test_outer_runtime_projection_audit_has_final_hard_budget() -> None:
    class BrokenAdapter:
        def get_runtime_context_projection(self, solver):
            del solver
            raise RuntimeError("child projection failed: " + ("x" * 10_000))

    controller = StrategyRouterAdapter(
        strategies=tuple(
            StrategySpec(adapter=BrokenAdapter(), name=f"broken-{index}")
            for index in range(16)
        )
    )
    controller.units = controller._build_units()
    controller._runtime_meta_projection = {
        f"oversized_{index}": "y" * 1_000 for index in range(16)
    }
    solver = _ProjectionSolver(controller)
    solver.runtime_context_projection_field_max_bytes = 8
    solver.runtime_context_projection_total_max_bytes = 64

    projection = collect_runtime_context_projection(solver)
    audit = projection[KEY_RUNTIME_PROJECTION_AUDIT]
    encoded = json.dumps(audit, ensure_ascii=False).encode("utf-8")

    assert audit["status"] == "error"
    assert audit["current"] is False
    assert audit["audit_max_bytes"] == 4_096
    assert len(encoded) <= audit["audit_max_bytes"]
    assert audit["omitted_field_count"] == 16
    assert audit["component_audit"]["issue_count"] == 16
    assert len(audit["component_audit"]["audit_digest"]) == 64
    assert audit["audit_truncated"] is True


def test_audit_isolation_failure_atomically_replaces_old_evidence() -> None:
    solver = _ProjectionSolver(object())
    solver._runtime_projection_audit = {
        "status": "ok",
        "current": True,
        "marker": "stale",
    }

    recorded, error = control_plane_helpers._record_runtime_projection_audit(
        solver,
        {
            "status": "ok",
            "current": True,
            "signature": "a" * 64,
            "component_audit": {"unsafe": object()},
        },
    )

    assert isinstance(error, TypeError)
    assert recorded["status"] == "error"
    assert recorded["current"] is False
    assert recorded["projection_error"]["type"] == "TypeError"
    assert "marker" not in recorded
    assert solver._runtime_projection_audit == recorded
    assert "marker" not in solver._runtime_projection_audit


def test_nsga2_and_de_publish_adapter_namespaced_best_fields() -> None:
    population = np.asarray(
        [
            [0.0, 0.0],
            [1.0, 1.0],
            [2.0, 2.0],
            [3.0, 3.0],
        ],
        dtype=float,
    )
    objectives = np.asarray(
        [
            [4.0, 1.0],
            [3.0, 1.0],
            [2.0, 1.0],
            [1.0, 1.0],
        ],
        dtype=float,
    )
    violations = np.zeros(4, dtype=float)
    adapters = (
        NSGA2Adapter(NSGA2Config(population_size=4, offspring_size=2)),
        DifferentialEvolutionAdapter(DEConfig(population_size=4, batch_size=2)),
    )

    for adapter in adapters:
        assert adapter.set_population_snapshot(population, objectives, violations) is True
        projection = adapter.get_runtime_context_projection(None)
        assert KEY_ADAPTER_BEST_X in projection
        assert KEY_ADAPTER_BEST_OBJECTIVES in projection
        assert KEY_ADAPTER_BEST_SCORE in projection
        assert np.asarray(projection[KEY_ADAPTER_BEST_OBJECTIVES]).shape == (2,)
        assert isinstance(projection[KEY_ADAPTER_BEST_SCORE], float)
        assert KEY_BEST_X not in projection
        assert KEY_BEST_OBJECTIVE not in projection
        assert KEY_GENERATION not in projection
        assert set(adapter.context_provides).issuperset(
            {
                KEY_ADAPTER_BEST_X,
                KEY_ADAPTER_BEST_OBJECTIVES,
                KEY_ADAPTER_BEST_SCORE,
            }
        )


def test_adapter_contract_card_uses_namespaced_best_semantics() -> None:
    card = (
        Path(__file__).parents[1]
        / "docs"
        / "architecture"
        / "ADAPTER_CONTRACT_CARDS.md"
    ).read_text(encoding="utf-8")

    assert "DifferentialEvolutionAdapter | L2 | generation | strategy_id, adapter_best_x, adapter_best_objectives, adapter_best_score" in card
    assert "NSGA2Adapter | L2 | - | adapter_best_x, adapter_best_objectives, adapter_best_score" in card
    assert "NSGA3Adapter | L2 | - | adapter_best_x, adapter_best_objectives, adapter_best_score, mo_weights" in card


def test_runtime_projection_docs_describe_composite_five_state_contract() -> None:
    root = Path(__file__).parents[1]
    guide = (root / "docs" / "guides" / "DECOUPLING_ADAPTER.md").read_text(
        encoding="utf-8"
    )
    field_rules = (
        root / "docs" / "user_guide" / "CONTEXT_FIELD_RULES.md"
    ).read_text(encoding="utf-8")

    for document in (guide, field_rules):
        assert "完整外层状态机" in document
        assert "degraded" in document
        assert "ok / degraded / error" in document
        assert "current=True" in document
