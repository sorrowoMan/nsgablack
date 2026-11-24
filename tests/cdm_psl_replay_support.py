"""Test-only CDM-PSL control/data replay, not a trained optimizer or Adapter.

The recorded topology follows the paper's outer loop; SDE, GP, diffusion,
GA, batch selection, evaluation and HV mathematics are deliberately not tested.
Initialization receives recorded real observations, not a claimed LHS replica.
ReplaySwitchPolicy is an explicit experimental rule, not a paper formula.
No simulated budgets or transactions are used to claim Solver integration.

Repair is an extra contract perturbation. Two legal orders are demonstrated:
repair -> predict -> preselect -> evaluate, or predict -> preselect -> repair
-> evaluate (discard the old prediction). Neither may score a repaired version
with its predecessor's prediction. Capability families are independent, not
four mandatory sequential stages or a general change(solver) operation.
"""

from dataclasses import dataclass, replace
from typing import Callable, Literal

HV_REFERENCE = (5.0, 5.0)  # Fixed minimization reference for the recorded examples.


@dataclass(frozen=True)
class Candidate:
    identity: str
    version: int
    values: tuple[float, ...]


@dataclass(frozen=True)
class Observation:
    candidate: Candidate
    raw: tuple[float, ...]
    violation: float = 0.0


@dataclass(frozen=True)
class Feedback:
    observation: Observation
    selection_view: tuple[float, ...]


@dataclass(frozen=True)
class Model:
    kind: Literal["gp", "diffusion"]
    version: int


@dataclass(frozen=True)
class Prediction:
    candidate: Candidate
    model: Model
    score: float


@dataclass(frozen=True)
class Unit:
    history: tuple[Observation, ...]
    gp: Model | None = None
    diffusion: Model | None = None
    generation_mode: Literal["cdm", "ga"] = "cdm"
    hv_history: tuple[float, ...] = ()


@dataclass(frozen=True)
class ReplaySwitchPolicy:
    """Toggle mode if raw HV gain over `window` intervals is <= tolerance."""

    window: int = 2
    tolerance: float = 1.0

    def next_mode(self, mode, hv):
        if self.window < 1 or self.tolerance < 0:
            raise ValueError("invalid experimental switch policy")
        stagnant = len(hv) > self.window and hv[-1] - hv[-1 - self.window] <= self.tolerance
        return ("ga" if mode == "cdm" else "cdm") if stagnant else mode


class Recording:
    """Strict lookup by operation and complete immutable input values."""

    def __init__(self, entries):
        self.outputs = dict(entries)
        if len(self.outputs) != len(entries):
            raise ValueError("duplicate recording request")
        self.trace = []

    def call(self, operation, *inputs):
        request = (operation, *inputs)
        self.trace.append(request)
        if request not in self.outputs:
            raise LookupError(f"unrecorded request: {request!r}")
        return self.outputs[request]


def initialize(observations: tuple[Observation, ...], *, mode="cdm") -> Unit:
    if mode not in {"cdm", "ga"} or not observations:
        raise ValueError("initialization needs observations and a known mode")
    return Unit(append_observations((), observations), generation_mode=mode)


def append_observations(history, incoming):
    """Identity/version, not numeric equality or dominance, identifies a record."""
    result = list(history)
    known = {(row.candidate.identity, row.candidate.version): row for row in result}
    for row in incoming:
        key = (row.candidate.identity, row.candidate.version)
        if key in known and known[key] != row:
            raise ValueError("conflicting observation for exact candidate version")
        if key not in known:
            result.append(row)
            known[key] = row
    return tuple(result)


def fit_gp(recording: Recording, history: tuple[Observation, ...]) -> Model:
    model = recording.call("fit_gp", history)
    if not isinstance(model, Model) or model.kind != "gp":
        raise TypeError("GP fitting must return a GP model version")
    return model


def select_training(recording: Recording, history: tuple[Observation, ...]) -> tuple[Observation, ...]:
    refs = recording.call("select_training", history)
    if len(set(refs)) != len(refs):
        raise ValueError("duplicate training reference")
    by_candidate = {row.candidate: row for row in history}
    return tuple(by_candidate[ref] for ref in refs)


def fit_diffusion(recording: Recording, training: tuple[Observation, ...]) -> Model:
    model = recording.call("fit_diffusion", training)
    if not isinstance(model, Model) or model.kind != "diffusion":
        raise TypeError("diffusion fitting must return a diffusion model version")
    return model


def generate_diffusion(recording: Recording, gp: Model, diffusion: Model,
                       conditions: tuple[float, ...]) -> tuple[Candidate, ...]:
    return recording.call("generate_diffusion", diffusion, gp, conditions)


def generate_ga(recording: Recording, history: tuple[Observation, ...],
                conditions: tuple[float, ...]) -> tuple[Candidate, ...]:
    return recording.call("generate_ga", history, conditions)


def validate_predictions(gp, candidates, predictions):
    if len(candidates) != len(predictions) or any(
        prediction.candidate != candidate or prediction.model != gp
        for candidate, prediction in zip(candidates, predictions)
    ):
        raise ValueError("prediction does not match candidate/model version")


def select_evaluation(recording: Recording, gp: Model, history: tuple[Observation, ...],
                      candidates: tuple[Candidate, ...], count: int = 1, *,
                      predictions: tuple[Prediction, ...] | None = None) -> tuple[Candidate, ...]:
    if predictions is None:
        predictions = recording.call("predict", gp, candidates)
    validate_predictions(gp, candidates, predictions)
    selected = recording.call("batch_select", gp, history, candidates, predictions, count)
    if len(selected) > count or len(set(selected)) != len(selected) or any(c not in candidates for c in selected):
        raise ValueError("batch selection must preserve exact proposal identities")
    return selected


def repair_nonnegative(candidate: Candidate) -> Candidate:
    """Pure example constraint repair, not claimed to be part of CDM-PSL."""
    values = tuple(max(0.0, value) for value in candidate.values)
    return candidate if values == candidate.values else replace(candidate, version=candidate.version + 1, values=values)


@dataclass(frozen=True)
class ReplayCapabilities:
    """Test assembly only: named IO, not an arbitrary Unit/Solver callback.

    Initialization is explicit before stepping. Fitting, generation and raw
    history append are bounded changes; train/eval selection are decisions.
    Optional pure repair precedes prediction here; no fifth public protocol.
    """

    initialize: Callable[[tuple[Observation, ...]], Unit] = initialize
    fit_gp: Callable[[Recording, tuple[Observation, ...]], Model] = fit_gp
    fit_diffusion: Callable[[Recording, tuple[Observation, ...]], Model] = fit_diffusion
    generate_diffusion: Callable[[Recording, Model, Model, tuple[float, ...]], tuple[Candidate, ...]] = generate_diffusion
    generate_ga: Callable[[Recording, tuple[Observation, ...], tuple[float, ...]], tuple[Candidate, ...]] = generate_ga
    train_select: Callable[[Recording, tuple[Observation, ...]], tuple[Observation, ...]] = select_training
    eval_select: Callable[[Recording, Model, tuple[Observation, ...], tuple[Candidate, ...], int], tuple[Candidate, ...]] = select_evaluation
    append: Callable[[tuple[Observation, ...], tuple[Observation, ...]], tuple[Observation, ...]] = append_observations
    repair: Callable[[Candidate], Candidate] | None = None


def decomposed_step(unit: Unit, recording: Recording, *, conditions=(0.5, 0.5), count=1,
                    policy=ReplaySwitchPolicy(), capabilities=ReplayCapabilities()) -> Unit:
    gp = capabilities.fit_gp(recording, unit.history)
    training = capabilities.train_select(recording, unit.history)
    diffusion = unit.diffusion
    if unit.generation_mode == "cdm":
        diffusion = capabilities.fit_diffusion(recording, training)
        candidates = capabilities.generate_diffusion(recording, gp, diffusion, conditions)
    else:
        candidates = capabilities.generate_ga(recording, unit.history, conditions)
    if capabilities.repair is not None:
        candidates = tuple(capabilities.repair(candidate) for candidate in candidates)
    selected = capabilities.eval_select(recording, gp, unit.history, candidates, count)
    feedback = recording.call("evaluate", selected)
    if tuple(item.observation.candidate for item in feedback) != selected:
        raise ValueError("evaluation feedback must preserve exact selected versions")
    history = capabilities.append(unit.history, tuple(item.observation for item in feedback))
    hv = unit.hv_history + (recording.call("raw_hv", history, HV_REFERENCE),)
    mode = policy.next_mode(unit.generation_mode, hv)
    return Unit(history, gp, diffusion, mode, hv)


def monolithic_step(unit: Unit, recording: Recording, *, conditions=(0.5, 0.5), count=1,
                    policy=ReplaySwitchPolicy()) -> Unit:
    """Independent orchestration; shares value records and pure validation only."""
    gp = recording.call("fit_gp", unit.history)
    training_refs = recording.call("select_training", unit.history)
    training = tuple(next(row for row in unit.history if row.candidate == ref) for ref in training_refs)
    diffusion = unit.diffusion
    if unit.generation_mode == "cdm":
        diffusion = recording.call("fit_diffusion", training)
        proposals = recording.call("generate_diffusion", diffusion, gp, conditions)
    else:
        proposals = recording.call("generate_ga", unit.history, conditions)
    predictions = recording.call("predict", gp, proposals)
    validate_predictions(gp, proposals, predictions)
    chosen = recording.call("batch_select", gp, unit.history, proposals, predictions, count)
    if len(chosen) > count or len(set(chosen)) != len(chosen) or any(c not in proposals for c in chosen):
        raise ValueError("invalid recorded selection")
    observations = recording.call("evaluate", chosen)
    if tuple(item.observation.candidate for item in observations) != chosen:
        raise ValueError("misaligned recorded evaluation")
    history = append_observations(unit.history, tuple(item.observation for item in observations))
    hv = (*unit.hv_history, recording.call("raw_hv", history, HV_REFERENCE))
    mode = policy.next_mode(unit.generation_mode, hv)
    return Unit(history, gp, diffusion, mode, hv)
