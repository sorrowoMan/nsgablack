from __future__ import annotations

from nsgablack.core.evaluation_runtime import EvaluationMediator, EvaluationMediatorConfig


def test_evaluation_policy_configuration_preserves_unspecified_fields() -> None:
    mediator = EvaluationMediator(
        EvaluationMediatorConfig(allow_approximate=False, strict_conflict=True)
    )

    mediator.configure_policy(allow_approximate=True)

    assert mediator.config.allow_approximate is True
    assert mediator.config.strict_conflict is True


def test_evaluation_policy_configuration_can_change_conflict_semantics() -> None:
    mediator = EvaluationMediator(
        EvaluationMediatorConfig(allow_approximate=True, strict_conflict=True)
    )

    mediator.configure_policy(strict_conflict=False)

    assert mediator.config.allow_approximate is True
    assert mediator.config.strict_conflict is False
