"""Opt-in population features. No evaluation, acceptance or scheduling here."""
import numpy as np

from .features import UnitFeature, FeatureContractError


def _population(inputs):
    value = inputs["population"]
    values = np.empty((0, 0)) if value is None else np.asarray(value, dtype=float)
    if values.ndim != 2 or not np.all(np.isfinite(values)):
        raise FeatureContractError("Population distances require a finite matrix")
    return values


def _distances(inputs):
    values = _population(inputs)
    # O(n²) output, O(n*d) working memory rather than an n*n*d temporary.
    result = np.empty((len(values), len(values)), dtype=float)
    for i, row in enumerate(values):
        result[i] = np.linalg.norm(values - row, axis=1)
    return result


def _update_distances(inputs, previous_inputs, previous):
    values, old = _population(inputs), _population(previous_inputs)
    if values.shape != old.shape:
        return _distances(inputs)
    changed = np.flatnonzero(np.any(values != old, axis=1))
    result = np.array(previous, copy=True)
    for i in changed:
        row = np.linalg.norm(values - values[i], axis=1)
        result[i, :] = row
        result[:, i] = row
    return result


POPULATION_DISTANCES = UnitFeature(
    "population.euclidean_distances", ("population",), _distances, update=_update_distances,
)


def _selection_ranking(inputs):
    from ..utils.performance.fast_non_dominated_sort import FastNonDominatedSort
    population, objectives, violations = (inputs[n] for n in ("population", "objectives", "violations"))
    count = 0 if population is None else len(population)
    if count == 0:
        return np.zeros(0, dtype=int), np.zeros(0)
    if objectives is None or violations is None:
        raise FeatureContractError("Selection ranking requires evaluated population feedback")
    objectives, violations = np.asarray(objectives), np.asarray(violations)
    if objectives.ndim != 2 or violations.shape != (count,) or len(objectives) != count:
        raise FeatureContractError("Selection ranking feedback must align with population")
    fronts, rank = FastNonDominatedSort.sort(objectives, violations)
    crowding = np.zeros(count)
    for front in fronts:
        crowding += FastNonDominatedSort.calculate_crowding_distance(objectives, list(front))
    return np.asarray(rank, dtype=int), crowding


SELECTION_RANKING = UnitFeature(
    "population.selection_rank_and_crowding", ("population", "objectives", "violations"),
    _selection_ranking, feedback_view="selection",
)
