"""Independent repair operations with an explicit joint acceptance boundary."""
from dataclasses import dataclass
from typing import Protocol, Any, Mapping, runtime_checkable
import inspect

from blackbase.types import CandidateBatch, UnknownState


@runtime_checkable
class ProblemRepair(Protocol):
    """Repair a numeric proposal; validate its final semantic candidate.

    validate must be read-only and return bool. It is a declared pre-evaluation
    feasibility check, not an implicit call to Problem.evaluate or a Provider.
    """
    def repair(self, candidate: Any, context: Mapping[str, Any]) -> Any: ...
    def validate(self, candidate: UnknownState, context: Mapping[str, Any]) -> bool: ...


@runtime_checkable
class UnitRepair(Protocol):
    """Modify a detached Unit draft and return an identity-preserving batch.

    The owner reconciles its other pending state after joint validation. A Unit
    repair must respect algorithm parameters (e.g. radius); it cannot silently
    redefine their meaning to make a validation pass.

    Optional project_admission(baseline, draft, evidence, disposition, context)
    runs AFTER Adapter disposition has compacted draft's pending coordinates.
    baseline is the full pre-repair Unit; evidence/disposition use original
    proposal indices. Preserve the already admitted coordinates in draft.
    Missing projection fails closed on partial admission. Zero admission
    restores participant baselines before ordinary disposition notification.
    """
    def repair(self, unit: Any, evidence: Any, context: Mapping[str, Any]) -> CandidateBatch: ...
    def validate(self, unit: Any, evidence: Any, context: Mapping[str, Any]) -> bool: ...


@dataclass(frozen=True)
class JointRepairPolicy:
    max_rounds: int = 1
    on_rejection: str = "stop"

    def __post_init__(self):
        if type(self.max_rounds) is not int or self.max_rounds < 1:
            raise ValueError("joint repair max_rounds must be a positive integer")
        if self.on_rejection not in {"stop", "retry", "advance"}:
            raise ValueError("joint repair on_rejection must be stop, retry, or advance")


class JointRepairRejected(ValueError):
    """Expected incompatibility; report goes to the Adapter after rollback."""
    def __init__(self, report):
        self.report = dict(report)
        super().__init__(f"joint repair rejected: {report['reason']}")


def validate_repair_component(component, *, unit=False):
    args = (object(), object(), {}) if unit else (object(), {})
    for operation in ("repair", "validate"):
        method = getattr(component, operation, None)
        if not callable(method):
            raise TypeError(f"{'UnitRepair' if unit else 'ProblemRepair'} requires {operation}()")
        try:
            inspect.signature(method).bind(*args)
        except (TypeError, ValueError) as exc:
            raise TypeError(f"invalid {'UnitRepair' if unit else 'ProblemRepair'}.{operation} signature") from exc
    if unit and hasattr(component, "project_admission"):
        method = component.project_admission
        if not callable(method):
            raise TypeError("UnitRepair.project_admission must be callable")
        try:
            inspect.signature(method).bind(object(), object(), object(), object(), {})
        except (TypeError, ValueError) as exc:
            raise TypeError("invalid UnitRepair.project_admission signature") from exc


def validate_admission_fields(owner):
    names = getattr(owner, "admission_unit_fields", ())
    if (not isinstance(names, (tuple, list)) or any(not isinstance(name, str) for name in names)
            or len(set(names)) != len(names)):
        raise TypeError("admission_unit_fields must name unique fields of the owned Unit")
    unit = owner.algorithm_unit
    if unit is None:
        # Inspect declared data fields without calling a builder or codec.
        from dataclasses import fields, is_dataclass
        binding = getattr(owner, "unit_binding", None)
        unit_type = getattr(getattr(binding, "builder", None), "unit_type", None)
        declared = ({field.name for field in fields(unit_type)} if is_dataclass(unit_type)
                    else set(getattr(getattr(binding, "schema", None), "required_fields", ())))
        missing = any(name not in declared for name in names)
    else:
        missing = any(not hasattr(unit, name) for name in names)
    if missing:
        raise TypeError("admission_unit_fields must name unique fields of the owned Unit")


__all__ = ["ProblemRepair", "UnitRepair", "JointRepairPolicy", "JointRepairRejected"]
