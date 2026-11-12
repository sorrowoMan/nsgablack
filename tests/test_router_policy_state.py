"""Router policy state follows its existing transaction and checkpoint owners."""
from __future__ import annotations

import copy
from dataclasses import dataclass, fields

import numpy as np
import pytest

from nsgablack.adapters import (
    AlgorithmAdapter, MultiStrategyConfig, MultiStrategyControlRule,
    RoleSpec, StrategyRouterAdapter, StrategySpec,
)
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.core.state.step_outcome import StepOutcome


class PointAdapter(AlgorithmAdapter):
    def __init__(self, name, point):
        super().__init__(name=name)
        self.point = point
        self.updates = 0
        self.restore_calls = 0

    def propose(self, control, context):
        del control
        count = int(context["task"]["budget"])
        return [np.array([self.point + index / 100.]) for index in range(count)]

    def update(self, control, candidates, feedback, context):
        del control, candidates, feedback, context
        self.updates += 1

    def get_state(self):
        return {"updates": self.updates}

    def set_state(self, state):
        self.restore_calls += 1
        self.updates = int(state["updates"])


class Sphere(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["min"], bounds=[(-10., 10.)])
        self.calls = 0

    def evaluate(self, candidate):
        self.calls += 1
        return [float(np.asarray(candidate) @ np.asarray(candidate))]


def build_group(*, roles=False, weights=(1., 1.), **config):
    children = [PointAdapter("low", 1.), PointAdapter("high", 3.)]
    if roles:
        specs = [RoleSpec(child.name, child, weight=weight)
                 for child, weight in zip(children, weights)]
        kwargs = {"roles": specs}
    else:
        specs = [StrategySpec(child, child.name, weight=weight)
                 for child, weight in zip(children, weights)]
        kwargs = {"strategies": specs}
    config = {"total_batch_size": 10, **config}
    group = StrategyRouterAdapter(config=MultiStrategyConfig(**config), **kwargs)
    solver = ComposableSolver(Sphere(), adapter=group)
    solver.set_random_seed(71)
    solver.setup()
    return solver, group, specs, children


def live_weights(specs):
    return {spec.name: spec.weight for spec in specs}


@pytest.mark.parametrize("roles", [False, True], ids=["strategies", "roles"])
def test_failed_step_restores_live_weights_and_next_allocation(roles, monkeypatch):
    solver, group, specs, children = build_group(roles=roles)
    before_weights = live_weights(specs)
    before_allocation = group._allocate_role_budgets()
    changed_weights = []
    original_update = group.update

    def fail_after_policy_update(*args, **kwargs):
        original_update(*args, **kwargs)
        changed_weights.append(live_weights(specs))
        raise RuntimeError("later semantic update failed")

    monkeypatch.setattr(group, "update", fail_after_policy_update)
    with pytest.raises(RuntimeError, match="later semantic update failed"):
        solver.step()

    assert changed_weights and changed_weights[0] != before_weights
    assert live_weights(specs) == before_weights
    assert group._allocate_role_budgets() == before_allocation
    assert all(child.updates == 0 for child in children)
    assert solver.generation == 0
    assert solver.evaluation_count == solver.problem.calls == 10

    monkeypatch.setattr(group, "update", original_update)
    assert solver.step().committed
    assert live_weights(specs) != before_weights
    assert all(child.updates == 1 for child in children)


@pytest.mark.parametrize("roles", [False, True], ids=["strategies", "roles"])
def test_checkpoint_restores_dynamic_policy_without_copying_owners(roles):
    solver, group, specs, _ = build_group(roles=roles, weights=(2., 1.))
    initial_identity = group.get_state()["policy_identity"]
    assert solver.step().committed
    saved = group.get_state()
    assert saved["policy_identity"] == initial_identity
    assert saved["policy_weights"] == live_weights(specs) != {"low": 2., "high": 1.}
    expected_allocation = group._allocate_role_budgets()

    _, restored, target_specs, target_children = build_group(roles=roles, weights=(2., 1.))
    restored.set_state(copy.deepcopy(saved))

    assert live_weights(target_specs) == live_weights(specs)
    assert restored._allocate_role_budgets() == expected_allocation
    assert (restored.roles if roles else restored.strategies)[0] is target_specs[0]
    assert restored.units[0].adapter is target_children[0]
    assert restored.units[0].adapter is not group.units[0].adapter
    assert [child.updates for child in target_children] == [1, 1]


@pytest.mark.parametrize("roles", [False, True], ids=["strategies", "roles"])
def test_fresh_setup_uses_immutable_initial_weights_then_restore_applies_runtime(roles):
    solver, group, specs, _ = build_group(roles=roles, weights=(2., 1.))
    assert solver.step().committed
    saved = group.get_state()
    assert live_weights(specs) != {"low": 2., "high": 1.}

    group.setup(solver)
    assert live_weights(specs) == {"low": 2., "high": 1.}
    group.set_state(saved)
    assert live_weights(specs) == saved["policy_weights"]


@pytest.mark.parametrize("changed", [
    {"total_batch_size": 11}, {"adapt_momentum": .6},
    {"phase_schedule": (("only", -1),)}, {"n_regions": 4},
    {"seeds_source": "best"},
    {"phase_weight_multipliers": {"explore": {"low": 3.}}},
])
def test_checkpoint_config_mismatch_rejected_before_child_restore(changed):
    solver, group, _, _ = build_group()
    assert solver.step().committed
    _, target, target_specs, children = build_group(**changed)
    initial_weights = live_weights(target_specs)
    with pytest.raises(ValueError, match="configuration mismatch"):
        target.set_state(group.get_state())
    assert all(child.restore_calls == 0 for child in children)
    assert live_weights(target_specs) == initial_weights
    assert target._step == 0


def test_initial_weights_are_identity_but_runtime_weight_changes_are_not():
    _, source, specs, _ = build_group(weights=(2., 1.))
    identity = source.get_state()["policy_identity"]
    specs[0].weight = 7.
    assert source.get_state()["policy_identity"] == identity
    _, target, _, children = build_group(weights=(1., 1.))
    with pytest.raises(ValueError, match="configuration mismatch"):
        target.set_state(source.get_state())
    assert all(child.restore_calls == 0 for child in children)


def test_assembly_configuration_is_detached_and_cannot_drift_silently():
    roles_by_phase = {"explore": ["low", "high"]}
    _, group, _, _ = build_group(phase_roles=roles_by_phase)
    initial = group.get_state()["policy_identity"]
    initial["owners"][0]["weight"] = 99.
    assert group.get_state()["policy_identity"]["owners"][0]["weight"] == 1.
    roles_by_phase["explore"].remove("high")
    with pytest.raises(ValueError, match="configuration changed after assembly"):
        group.get_state()


def test_final_assembly_can_adjust_configuration_before_first_setup():
    first = StrategySpec(PointAdapter("low", 1.), "low", weight=1.)
    second = StrategySpec(PointAdapter("high", 3.), "high", weight=1.)
    group = StrategyRouterAdapter(strategies=[first, second])
    group.cfg.total_batch_size = 4
    first.weight = 3.
    solver = ComposableSolver(Sphere(), adapter=group)
    solver.setup()
    identity = group.get_state()["policy_identity"]
    assert identity["config"]["fields"]["total_batch_size"] == 4
    assert identity["owners"][0]["weight"] == first.weight == 3.
    first.weight = 9.
    group.setup(solver)
    assert first.weight == 3.
    group.cfg.total_batch_size = 6
    with pytest.raises(ValueError, match="configuration changed after assembly"):
        group.get_state()


def phase_policy():
    return lambda context: ("explore", int(context.get("step", 0)))


def alternate_phase_policy():
    return lambda context: ("exploit", int(context.get("step", 0)))


def test_existing_lambda_policies_and_rules_remain_supported_for_restore():
    callback = phase_policy()
    rule = MultiStrategyControlRule(name="disabled", when=lambda context: False,
                                    then={"disable_roles": ["high"]})
    solver, source, _, _ = build_group(phase_policy=callback, control_rules=(rule,))
    assert solver.step().committed
    _, target, _, _ = build_group(phase_policy=phase_policy(), control_rules=(rule,))
    target.set_state(source.get_state())
    assert target._step == 1
    _, changed, _, _ = build_group(phase_policy=alternate_phase_policy(), control_rules=(rule,))
    with pytest.raises(ValueError, match="configuration mismatch"):
        changed.set_state(source.get_state())


@pytest.mark.parametrize("kind", ["checkpoint", "transaction"])
def test_dispatch_stop_restores_only_raw_step_outcome_fields(kind):
    _, group, specs, _ = build_group()
    stopped = StepOutcome(status="cancelled", proposals=2, reason="operator cancelled",
                          metadata={"owner": "low", "path": ["outer", "inner"]})
    group._dispatch_stop_outcome = stopped
    state = group.get_state() if kind == "checkpoint" else group.snapshot_step_state()
    assert set(state["dispatch_stop_outcome"]) == {field.name for field in fields(StepOutcome)}
    specs[0].weight = 9.
    group._dispatch_stop_outcome = None

    restore = group.set_state if kind == "checkpoint" else group.restore_step_state
    restore(state)
    assert live_weights(specs) == {"low": 1., "high": 1.}
    assert group._dispatch_stop_outcome == stopped
    group._dispatch_stop_outcome = None
    assert state["dispatch_stop_outcome"]["reason"] == "operator cancelled"


@pytest.mark.parametrize("kind", ["checkpoint", "transaction"])
@pytest.mark.parametrize("invalid", ["missing_owner", "nan_weight", "committed_stop", "derived_field"])
def test_invalid_policy_state_rejected_before_mutating_live_owners(kind, invalid):
    _, group, specs, children = build_group()
    group._dispatch_stop_outcome = StepOutcome(status="cancelled")
    state = group.get_state() if kind == "checkpoint" else group.snapshot_step_state()
    if invalid == "missing_owner":
        state["policy_weights"].pop("high")
    elif invalid == "nan_weight":
        state["policy_weights"]["low"] = float("nan")
    elif invalid == "committed_stop":
        state["dispatch_stop_outcome"]["status"] = "committed"
    else:
        state["dispatch_stop_outcome"]["terminal"] = True
    specs[0].weight = 9.
    restore = group.set_state if kind == "checkpoint" else group.restore_step_state
    with pytest.raises(ValueError):
        restore(state)
    assert specs[0].weight == 9.
    assert all(child.restore_calls == 0 for child in children)


@pytest.mark.parametrize("kind,legacy", [
    ("checkpoint", "nsgablack.strategy_router_state/v3"),
    ("transaction", "nsgablack.strategy_router_step_transaction/v2"),
])
def test_legacy_policy_state_requires_explicit_migration(kind, legacy):
    _, group, _, _ = build_group()
    state = group.get_state() if kind == "checkpoint" else group.snapshot_step_state()
    state["schema"] = legacy
    restore = group.set_state if kind == "checkpoint" else group.restore_step_state
    with pytest.raises(ValueError, match="legacy policy state requires explicit migration"):
        restore(state)


def captured_phase(phase):
    def policy(context):
        del context
        return phase
    return policy


def defaulted_phase(phase):
    def policy(context, selected=phase):
        del context
        return selected
    return policy


def keyword_phase(phase):
    def policy(context, *, selected=phase):
        del context
        return selected
    return policy


@pytest.mark.parametrize("factory", [captured_phase, defaulted_phase, keyword_phase])
def test_same_code_with_different_pure_callback_parameters_rejects_restore(factory):
    _, source, _, _ = build_group(phase_policy=factory("A"))
    _, equivalent, _, _ = build_group(phase_policy=factory("A"))
    equivalent.set_state(source.get_state())
    _, changed, _, children = build_group(phase_policy=factory("B"))
    with pytest.raises(ValueError, match="configuration mismatch"):
        changed.set_state(source.get_state())
    assert all(child.restore_calls == 0 for child in children)


@dataclass(frozen=True)
class PhaseSettings:
    phase: str
    limits: tuple


def structured_phase(settings):
    def policy(context):
        del context
        return settings.phase
    return policy


def test_pure_dataclass_and_nested_capture_values_bind_configuration():
    first = PhaseSettings("A", ({"thresholds": [1., 2.]},))
    second = PhaseSettings("A", ({"thresholds": [1., 3.]},))
    _, source, _, _ = build_group(phase_policy=structured_phase(first))
    _, changed, _, _ = build_group(phase_policy=structured_phase(second))
    with pytest.raises(ValueError, match="configuration mismatch"):
        changed.set_state(source.get_state())


class OpaqueSession:
    def __init__(self):
        self.ready = True

    def __deepcopy__(self, memo):
        raise AssertionError("runtime sessions must not be copied")


def live_session_phase(session):
    def policy(context):
        del context
        return "explore" if session.ready else "waiting"
    return policy


def test_live_session_capture_is_only_an_explicit_opaque_type_boundary():
    session = OpaqueSession()
    _, group, _, _ = build_group(phase_policy=live_session_phase(session))
    identity = group.get_state()["policy_identity"]
    capture = identity["config"]["fields"]["phase_policy"]["captures"]["session"]
    assert capture == {"opaque_type": f"{__name__}.OpaqueSession", "boundary": "runtime_value"}
    session.ready = False
    assert group.get_state()["policy_identity"] == identity


def recursive_phase():
    def policy(context):
        return "explore" if not context.get("nested") else policy({})
    return policy


def cyclic_capture_phase():
    history = []
    history.append(history)
    def policy(context):
        del context
        return "explore" if history else "waiting"
    return policy


@pytest.mark.parametrize("factory", [recursive_phase, cyclic_capture_phase])
def test_recursive_callback_and_cyclic_capture_have_finite_stable_identity(factory):
    _, source, _, _ = build_group(phase_policy=factory())
    _, equivalent, _, _ = build_group(phase_policy=factory())
    equivalent.set_state(source.get_state())
    assert equivalent.get_state()["policy_identity"] == source.get_state()["policy_identity"]


def test_cyclic_declaration_is_rejected_without_following_an_object_graph():
    declaration = {}
    declaration["self"] = declaration
    with pytest.raises(ValueError, match="contains a cycle"):
        StrategyRouterAdapter._policy_declaration(declaration)
