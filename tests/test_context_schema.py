import pytest

from nsgablack.utils.context.context_schema import build_minimal_context, validate_minimal_context


def test_build_and_validate_minimal_context():
    ctx = build_minimal_context(
        generation=3,
        individual_id=7,
        constraints=[0.0, 1.5],
        constraint_violation=1.5,
        seed=123,
        metadata={"tag": "x"},
        extra={"problem": "p"},
    )

    assert ctx["generation"] == 3
    assert ctx["individual_id"] == 7
    assert ctx["constraints"] == [0.0, 1.5]
    assert ctx["constraint_violation"] == 1.5
    assert ctx["seed"] == 123
    assert ctx["metadata"]["tag"] == "x"
    assert ctx["problem"] == "p"

    validate_minimal_context(ctx)


def test_validate_minimal_context_missing_required_key_raises():
    with pytest.raises(ValueError):
        validate_minimal_context({"constraints": [], "constraint_violation": 0.0})
