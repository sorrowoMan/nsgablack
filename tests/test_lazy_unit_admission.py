"""Disposition can reset an unaccepted draft without rebuilding its Unit."""
import hashlib
import pytest

from nsgablack.adapters import TrustRegionDFOAdapter
from nsgablack.representation import RegionUnitBuilder
from nsgablack.units import UnitBinding
from tests.test_joint_repair import Owner, UnitProjection, build
from tests.test_joint_repair_orchestration import Select
from tests.test_trust_region_pool_tasks import projected


def test_rejected_pool_seed_disposition_does_not_rebuild_the_unit():
    solver, adapter, _ = projected("dfo")
    builder = RegionUnitBuilder()
    calls = []

    def construct(request, context):
        calls.append(request)
        return builder.build(request, context)

    assert isinstance(adapter, TrustRegionDFOAdapter)
    adapter.set_unit_binding(UnitBinding(builder, runner=construct, name="lazy-admission-region"))
    assert calls == [] and adapter.algorithm_unit is None
    solver.set_evaluation_acceptance_policy(Select(()))
    outcome = solver.step()
    assert outcome.status == "rejected" and outcome.evaluations == 1
    assert adapter.algorithm_unit is None
    assert len(calls) == 1
    assert adapter.get_state()["algorithm_unit"] is None
    solver.set_evaluation_acceptance_policy(None)
    assert solver.step().committed
    assert len(calls) == 2


@pytest.mark.parametrize("fault", ("none", "identity"))
def test_accepted_disposition_cannot_discard_or_reidentify_the_unit(fault):
    class InvalidOwner(Owner):
        def on_proposal_disposition(self, control, disposition, context):
            super().on_proposal_disposition(control, disposition, context)
            self.reset_unit()
            if fault == "identity":
                self._unit_id = "another-unit"

    owner = InvalidOwner()
    owner.set_unit_repair(UnitProjection())
    solver, _, _ = build(owner)
    before = owner.get_state()
    with pytest.raises(ValueError, match="preserve Unit identity"):
        solver.step()
    assert owner.get_state() == before
    assert solver.evaluation_count == 1


@pytest.mark.parametrize("change_identity", (False, True))
def test_zero_admission_allows_absence_but_preserves_stable_identity(change_identity):
    class ResetOwner(Owner):
        def on_proposal_disposition(self, control, disposition, context):
            super().on_proposal_disposition(control, disposition, context)
            self.reset_unit()
            if change_identity:
                self._unit_id = "another-unit"

    owner = ResetOwner()
    owner.set_unit_repair(UnitProjection())
    solver, _, _ = build(owner)
    solver.set_evaluation_acceptance_policy(Select(()))
    before = owner.get_state()
    if change_identity:
        with pytest.raises(ValueError, match="preserve Unit identity"):
            solver.step()
        assert owner.get_state() == before
    else:
        outcome = solver.step()
        assert outcome.status == "rejected" and owner.algorithm_unit is None
        assert outcome.metadata["joint_repair"]["admission"][0]["unit_revision"] == hashlib.sha256(b"null").hexdigest()
