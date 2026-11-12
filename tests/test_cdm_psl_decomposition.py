"""Strict recorded outer-loop checks, not model/quality/runtime integration tests."""

from dataclasses import replace

import pytest

from .cdm_psl_replay_support import (
    Candidate, Feedback, HV_REFERENCE, Model, Observation, Prediction, Recording,
    ReplayCapabilities, ReplaySwitchPolicy,
    append_observations, decomposed_step, fit_gp, initialize, monolithic_step,
    repair_nonnegative, select_evaluation, validate_predictions,
)


def initial(mode="cdm"):
    return initialize((Observation(Candidate("seed-a", 0, (1.0,)), (1.0, 3.0)),
                       Observation(Candidate("seed-b", 0, (3.0,)), (3.0, 1.0))), mode=mode)


def recorded_round(unit, *, version=1, hv=12.0, raw=(20.0, 20.0), violation=5.0):
    """Hand-authored requests/answers, never derived by running either runner."""
    gp, diffusion = Model("gp", version), Model("diffusion", version)
    first = Candidate(f"proposal-a-{version}", 0, (2.0,))
    second = Candidate(f"proposal-b-{version}", 0, (4.0,))
    proposals = (first, second)
    predictions = (Prediction(first, gp, 1.0), Prediction(second, gp, 2.0))
    observation = Observation(first, raw, violation=violation)
    feedback = (Feedback(observation, (-999.0, -999.0)),)
    after = unit.history + (observation,)
    entries = [(("fit_gp", unit.history), gp),
               (("select_training", unit.history), (unit.history[0].candidate,))]
    if unit.generation_mode == "cdm":
        entries += [(("fit_diffusion", (unit.history[0],)), diffusion),
                    (("generate_diffusion", diffusion, gp, (0.5, 0.5)), proposals)]
    else:
        entries += [(("generate_ga", unit.history, (0.5, 0.5)), proposals)]
    entries += [(("predict", gp, proposals), predictions),
                (("batch_select", gp, unit.history, proposals, predictions, 1), (first,)),
                (("evaluate", (first,)), feedback), (("raw_hv", after, HV_REFERENCE), hv)]
    return entries, after


@pytest.mark.parametrize("mode", ["cdm", "ga"])
def test_independent_runners_match_handwritten_trace(mode):
    unit = initial(mode)
    entries, after = recorded_round(unit)
    reference, split = Recording(entries), Recording(entries)
    expected = replace(unit, history=after, gp=Model("gp", 1),
        diffusion=Model("diffusion", 1) if mode == "cdm" else None, hv_history=(12.0,))
    assert monolithic_step(unit, reference) == expected
    assert decomposed_step(unit, split) == expected
    assert reference.trace == split.trace == [request for request, _ in entries]
    branch = ["fit_diffusion", "generate_diffusion"] if mode == "cdm" else ["generate_ga"]
    assert [request[0] for request in split.trace] == [
        "fit_gp", "select_training", *branch, "predict", "batch_select", "evaluate", "raw_hv"]


def test_dominated_raw_observation_survives_and_trains_next_gp():
    unit = initial()
    entries, after = recorded_round(unit)
    result = decomposed_step(unit, Recording(entries))
    assert result.history == after
    assert result.history[-1].raw == (20.0, 20.0)
    assert result.history[-1].violation == 5.0
    assert all(not hasattr(row, "selection_view") for row in result.history)
    next_recording = Recording([(("fit_gp", after), Model("gp", 2))])
    assert fit_gp(next_recording, result.history) == Model("gp", 2)
    assert next_recording.trace == [("fit_gp", after)]


def test_equal_numeric_values_do_not_merge_distinct_identities_or_versions():
    a = Observation(Candidate("a", 0, (1.0,)), (2.0,))
    b = Observation(Candidate("b", 0, (1.0,)), (2.0,))
    a1 = Observation(Candidate("a", 1, (1.0,)), (2.0,))
    assert append_observations((a,), (b, a1, a)) == (a, b, a1)
    with pytest.raises(ValueError, match="conflicting"):
        append_observations((a,), (replace(a, raw=(9.0,)),))


def test_recordings_are_content_addressed_not_call_order_driven():
    a, b = Candidate("a", 0, (1.0,)), Candidate("b", 0, (2.0,))
    model = Model("gp", 1)
    recording = Recording([(("predict", model, (a,)), (Prediction(a, model, 1.0),)),
                           (("predict", model, (b,)), (Prediction(b, model, 2.0),))])
    assert recording.call("predict", model, (b,))[0].candidate == b
    assert recording.call("predict", model, (a,))[0].candidate == a
    for changed_model, changed_candidate in [
        (replace(model, version=2), a), (model, replace(a, version=1)),
        (model, replace(a, values=(8.0,))), (model, replace(a, identity="other")),
    ]:
        with pytest.raises(LookupError, match="unrecorded"):
            recording.call("predict", changed_model, (changed_candidate,))


def test_repair_requires_new_prediction_if_repaired_candidate_is_preselected():
    original, gp = Candidate("a", 0, (-1.0,)), Model("gp", 1)
    repaired = repair_nonnegative(original)
    assert repaired == Candidate("a", 1, (0.0,))
    assert original.values == (-1.0,)  # Pure repair does not overwrite old evidence.
    old_prediction = (Prediction(original, gp, -10.0),)
    with pytest.raises(ValueError, match="prediction"):
        select_evaluation(Recording([]), gp, (), (repaired,), 1, predictions=old_prediction)
    new_prediction = (Prediction(repaired, gp, 10.0),)
    recording = Recording([(("predict", gp, (repaired,)), new_prediction),
        (("batch_select", gp, (), (repaired,), new_prediction, 1), (repaired,))])
    assert select_evaluation(recording, gp, (), (repaired,), 1) == (repaired,)


def test_preselect_then_repair_is_legal_when_only_real_feedback_is_used_afterward():
    original, gp = Candidate("a", 0, (-1.0,)), Model("gp", 1)
    prediction = (Prediction(original, gp, -10.0),)
    repaired = repair_nonnegative(original)
    feedback = (Feedback(Observation(repaired, (10.0,)), (10.0,)),)
    recording = Recording([
        (("batch_select", gp, (), (original,), prediction, 1), (original,)),
        (("evaluate", (repaired,)), feedback)])
    chosen = select_evaluation(recording, gp, (), (original,), 1, predictions=prediction)
    assessed = recording.call("evaluate", tuple(repair_nonnegative(c) for c in chosen))
    assert assessed[0].observation.candidate == repaired
    assert assessed[0].observation.raw == (10.0,)  # Never the old predicted -10.
    with pytest.raises(ValueError, match="prediction"):
        select_evaluation(recording, gp, (), (repaired,), 1, predictions=prediction)


@pytest.mark.parametrize("history, expected", [
    ((), "cdm"), ((10.0, 10.0), "cdm"),
    ((10.0, 10.5, 11.0), "ga"), ((10.0, 10.5, 11.25), "cdm"),
])
def test_named_experimental_hv_window_boundary(history, expected):
    assert ReplaySwitchPolicy(window=2, tolerance=1.0).next_mode("cdm", history) == expected


@pytest.mark.parametrize("runner", [monolithic_step, decomposed_step])
def test_switch_occurs_after_appending_real_observations_and_raw_hv(runner):
    unit = replace(initial(), hv_history=(12.0, 12.0))
    entries, after = recorded_round(unit)
    recording = Recording(entries)
    result = runner(unit, recording)
    assert result.history == after and result.hv_history == (12.0, 12.0, 12.0)
    assert result.generation_mode == "ga"
    assert "generate_diffusion" in [request[0] for request in recording.trace]
    assert recording.trace[-1] == ("raw_hv", after, HV_REFERENCE)


@pytest.mark.parametrize("runner", [monolithic_step, decomposed_step])
def test_continuous_cdm_to_ga_replay_carries_raw_history_and_model_state(runner):
    start = replace(initial(), hv_history=(12.0, 12.0))
    first_entries, first_history = recorded_round(start)
    expected_first = replace(start, history=first_history, gp=Model("gp", 1),
        diffusion=Model("diffusion", 1), generation_mode="ga", hv_history=(12.0, 12.0, 12.0))
    second_entries, second_history = recorded_round(expected_first, version=2, hv=16.0,
        raw=(1.0, 1.0), violation=0.0)
    expected_second = replace(expected_first, history=second_history, gp=Model("gp", 2),
        hv_history=(12.0, 12.0, 12.0, 16.0))
    recording = Recording(first_entries + second_entries)
    first = runner(start, recording)
    second = runner(first, recording)
    assert first == expected_first and second == expected_second
    assert recording.trace == [request for request, _ in first_entries + second_entries]
    second_trace = recording.trace[len(first_entries):]
    assert [request[0] for request in second_trace] == [
        "fit_gp", "select_training", "generate_ga", "predict", "batch_select", "evaluate", "raw_hv"]
    assert second_trace[0] == ("fit_gp", first_history)
    assert first_history[-1].raw == (20.0, 20.0) and first_history[-1].violation == 5.0
    assert second.diffusion == first.diffusion == Model("diffusion", 1)


def test_replace_only_evaluation_selector_preserves_training_and_generation():
    defaults = ReplayCapabilities()
    unit = defaults.initialize(initial().history)
    entries, _ = recorded_round(unit)
    baseline_recording = Recording(entries)
    baseline = decomposed_step(unit, baseline_recording, capabilities=defaults)

    def choose_second(recording, gp, history, candidates, count):
        assert count == 1
        predictions = recording.call("predict", gp, candidates)
        validate_predictions(gp, candidates, predictions)
        return (candidates[1],)

    selected = Candidate("proposal-b-1", 0, (4.0,))
    observation = Observation(selected, (1.0, 1.0))
    expected_history = unit.history + (observation,)
    prefix = [(request, result) for request, result in entries
              if request[0] not in {"batch_select", "evaluate", "raw_hv"}]
    recording = Recording(prefix + [(("evaluate", (selected,)), (Feedback(observation, (-99.0, -99.0)),)),
                                    (("raw_hv", expected_history, HV_REFERENCE), 16.0)])
    result = decomposed_step(unit, recording, capabilities=replace(defaults, eval_select=choose_second))
    assert recording.trace[:len(prefix)] == baseline_recording.trace[:len(prefix)]
    assert result.gp == baseline.gp and result.diffusion == baseline.diffusion
    assert result.history == expected_history and result.history[-1].candidate != baseline.history[-1].candidate
    assert recording.trace[-2:] == [("evaluate", (selected,)), ("raw_hv", expected_history, HV_REFERENCE)]
