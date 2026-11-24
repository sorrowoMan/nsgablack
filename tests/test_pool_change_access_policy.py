"""Pool task donor declarations remain explicit through ordinary changes."""
from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from blackbase.types import CandidateBatch

from nsgablack.adapters import (
    MultiStrategyConfig, PoolTaskSpec, RoleSpec, StrategyRouterAdapter, VNSAdapter,
)
from nsgablack.adapters.change_access import (
    ChangeAccess, current_change_access, scoped_change_access,
)
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.core.state.solution_pool import SolutionRef
from nsgablack.representation import RepresentationPipeline, UniformInitializer


class Sphere(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["min"], bounds=[(-100., 100.)])

    def evaluate(self, candidate):
        return [float(candidate[0] ** 2)]


def seed_refs(control, context):
    return control.solution_pool.select(stage=None, source="seed")


def named_donor(request, *, rng):
    return request.pool.subpool("extra").random(1, rng=rng).values[0]


def mother_donor(request, *, rng):
    return request.pool.main(stage=None, source="donor").random(1, rng=rng).values[0]


def current_parent(request, *, rng):
    del rng
    return request.pool.read(request.source_refs).values[0] - .5


def build_task(*, change=named_donor, sources=(), allow_main=False):
    inner = VNSAdapter(change=change, batch_size=1, restart_on_stagnation=False)
    router = StrategyRouterAdapter(roles=[RoleSpec("local", inner,
        pool_task=PoolTaskSpec(seed_refs, steps=4, count=1, shuffle=False,
                               change_sources=sources, change_allow_main=allow_main))],
        config=MultiStrategyConfig(total_batch_size=1, adapt_weights=False))
    solver = ComposableSolver(Sphere(), adapter=router,
        representation_pipeline=RepresentationPipeline(initializer=UniformInitializer(low=9., high=9.)))
    solver.setup()
    refs = solver.store_solutions(CandidateBatch.from_candidates(
        [[4.]], candidate_tokens=("seed-token",)), source="seed")
    donor = solver.store_solutions(CandidateBatch.from_candidates(
        [[0.]], candidate_tokens=("donor-token",)), source="donor")
    solver.solution_pool.create_subpool("extra", donor)
    return solver, router.units[0].adapter, inner, refs


def test_default_task_declines_extra_named_donor_but_keeps_seed_baseline():
    solver, _, inner, _ = build_task()
    assert solver.step().committed
    assert inner.current_x[0] == 4.
    with pytest.raises(ValueError, match="outside this change task's declared inputs"):
        solver.step()
    assert inner.current_x[0] == 4.
    assert current_change_access() is None


def test_named_source_is_an_exact_public_name_without_task_namespace():
    solver, _, inner, _ = build_task(sources=("extra",))
    assert solver.step().committed and solver.step().committed
    assert inner.current_x[0] == 0.
    assert current_change_access() is None


@pytest.mark.parametrize("allowed", [False, True])
def test_mother_pool_donors_require_a_separate_explicit_declaration(allowed):
    solver, _, inner, _ = build_task(change=mother_donor, allow_main=allowed)
    assert solver.step().committed
    if allowed:
        assert solver.step().committed
        assert inner.current_x[0] == 0.
    else:
        with pytest.raises(ValueError, match="mother pool access is outside"):
            solver.step()


def test_owned_current_parent_remains_available_after_seed_version_changes():
    solver, _, inner, refs = build_task(change=current_parent)
    assert solver.step().committed
    current, = inner.get_pool_refinement_results(solver)
    assert current != refs[0]
    assert solver.step().committed and solver.step().committed
    assert inner.current_x[0] == 3.


def test_nested_task_scope_cannot_add_a_new_named_pool():
    solver, _, inner, _ = build_task(sources=("extra",))
    assert solver.step().committed
    with scoped_change_access((), subpools=("other",)):
        with pytest.raises(ValueError, match="outside this change task's declared inputs"):
            solver.step()
        assert current_change_access().subpools == ("other",)
    assert inner.current_x[0] == 4.
    with scoped_change_access((), subpools=("extra",)):
        assert solver.step().committed
    assert inner.current_x[0] == 0.


def test_nested_task_cannot_reenable_mother_pool_access():
    solver, _, _, _ = build_task(change=mother_donor, allow_main=True)
    assert solver.step().committed
    with scoped_change_access((), allow_main=False):
        with pytest.raises(ValueError, match="mother pool access is outside"):
            solver.step()
    assert current_change_access() is None


def test_scopes_are_immutable_intersect_donor_names_and_reset_after_exception():
    a = SolutionRef("pool", "record-a", 0, "a")
    b = SolutionRef("pool", "record-b", 0, "b")
    assert current_change_access() is None
    with scoped_change_access((a,), subpools=("shared", "outer"), allow_main=False) as outer:
        with pytest.raises(FrozenInstanceError):
            outer.allow_main = True
        with pytest.raises(RuntimeError, match="rollback"):
            with scoped_change_access((b,), subpools=("shared", "inner"), allow_main=True) as inner:
                assert inner.seed_refs == (a, b)
                assert inner.subpools == ("shared",)
                assert inner.allow_main is False
                raise RuntimeError("rollback")
        assert current_change_access() is outer
    assert current_change_access() is None


@pytest.mark.parametrize("options", [
    {"change_sources": ["extra"]}, {"change_sources": ("extra", "extra")},
    {"change_sources": ("",)}, {"change_sources": ("  ",)},
    {"change_sources": (4,)}, {"change_allow_main": 1},
])
def test_pool_task_strictly_validates_additional_donor_declarations(options):
    with pytest.raises((TypeError, ValueError)):
        PoolTaskSpec(**options)


@pytest.mark.parametrize("sources,allow_main", [(("extra",), False), ((), True)])
def test_checkpoint_rejects_changed_donor_configuration(sources, allow_main):
    _, original, _, _ = build_task()
    _, changed, _, _ = build_task(sources=sources, allow_main=allow_main)
    with pytest.raises(ValueError, match="checkpoint configuration mismatch"):
        changed.set_state(original.get_state())


def test_old_task_checkpoint_without_donor_identity_requires_explicit_migration():
    _, task, _, _ = build_task()
    state = task.get_state()
    state["pool_task_spec"].pop("change_sources")
    state["pool_task_spec"].pop("change_allow_main")
    with pytest.raises(ValueError, match="checkpoint configuration mismatch"):
        task.set_state(state)


def test_access_policy_rejects_mutable_names_and_non_boolean_main_flag():
    with pytest.raises(ValueError):
        ChangeAccess(subpools=["extra"])
    with pytest.raises(TypeError):
        ChangeAccess(allow_main=1)
