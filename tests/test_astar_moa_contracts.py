from __future__ import annotations

import numpy as np

from nsgablack.adapters import AStarAdapter, AStarConfig, MOAStarAdapter, MOAStarConfig
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.composable_solver import ComposableSolver


class _TwoObjectiveSphere(BlackBoxProblem):
    def __init__(self) -> None:
        super().__init__(dimension=2, objectives=["minimize", "minimize"], bounds=[(-5, 5)] * 2)

    def get_num_objectives(self):
        return 2

    def evaluate(self, x):
        x = np.asarray(x, dtype=float)
        return np.asarray([np.sum((x - 1.0) ** 2), np.sum((x + 1.0) ** 2)], dtype=float)


def _grid_neighbors(state, _context):
    x, y = np.asarray(state, dtype=float)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        yield np.asarray([x + dx, y + dy], dtype=float)


def _goal_near_zero(state, _context):
    return float(np.linalg.norm(np.asarray(state, dtype=float))) < 1e-6


def test_astar_adapter_smoke_run(sample_problem):
    adapter = AStarAdapter(
        neighbors=_grid_neighbors,
        heuristic=lambda s, _c: float(np.linalg.norm(np.asarray(s, dtype=float))),
        goal_test=_goal_near_zero,
        start_state=np.asarray([3.0, 3.0], dtype=float),
        config=AStarConfig(max_expand_per_step=4, max_candidates_per_step=32),
    )
    solver = ComposableSolver(problem=sample_problem, adapter=adapter)
    solver.set_max_steps(12)
    result = solver.run()
    assert result["status"] == "completed"
    assert solver.best_objective is not None


def test_astar_adapter_contract_propose_update_and_checkpoint_roundtrip(sample_problem):
    adapter = AStarAdapter(
        neighbors=_grid_neighbors,
        heuristic=lambda s, _c: float(np.linalg.norm(np.asarray(s, dtype=float))),
        goal_test=_goal_near_zero,
        start_state=np.asarray([2.0, 2.0], dtype=float),
        config=AStarConfig(max_expand_per_step=2, max_candidates_per_step=8),
    )
    solver = ComposableSolver(problem=sample_problem, adapter=adapter)
    adapter.setup(solver)
    context = {"generation": 0}
    candidates = adapter.propose(solver, context)
    assert candidates
    pop = np.asarray(candidates, dtype=float)
    objectives, violations = solver.evaluate_population(pop)
    adapter.update(solver, candidates, objectives, violations, context)

    state = adapter.get_state()
    clone = AStarAdapter(
        neighbors=_grid_neighbors,
        heuristic=lambda s, _c: float(np.linalg.norm(np.asarray(s, dtype=float))),
        goal_test=_goal_near_zero,
        start_state=np.asarray([2.0, 2.0], dtype=float),
        config=AStarConfig(max_expand_per_step=2, max_candidates_per_step=8),
    )
    clone.set_state(state)
    clone_state = clone.get_state()
    assert clone_state["found"] == state["found"]
    assert clone_state["best_score"] == state["best_score"]
    assert clone_state["best_state"] == state["best_state"]


def test_astar_adapter_tolerates_faulty_heuristic(sample_problem):
    def _bad_heuristic(_state, _context):
        raise RuntimeError("boom")

    adapter = AStarAdapter(
        neighbors=_grid_neighbors,
        heuristic=_bad_heuristic,
        goal_test=None,
        start_state=np.asarray([1.0, 1.0], dtype=float),
        config=AStarConfig(max_expand_per_step=1, max_candidates_per_step=4),
    )
    solver = ComposableSolver(problem=sample_problem, adapter=adapter)
    adapter.setup(solver)
    candidates = adapter.propose(solver, {"generation": 0})
    assert isinstance(candidates, list)


def test_moa_star_adapter_smoke_and_checkpoint_roundtrip():
    problem = _TwoObjectiveSphere()
    adapter = MOAStarAdapter(
        neighbors=_grid_neighbors,
        heuristic=lambda s, _c: np.asarray([np.linalg.norm(np.asarray(s, dtype=float)), 0.0], dtype=float),
        goal_test=_goal_near_zero,
        start_state=np.asarray([3.0, 3.0], dtype=float),
        config=MOAStarConfig(max_expand_per_step=2, max_candidates_per_step=16, stop_on_goal=False),
    )
    solver = ComposableSolver(problem=problem, adapter=adapter)
    solver.set_max_steps(8)
    result = solver.run()
    assert result["status"] == "completed"

    state = adapter.get_state()
    clone = MOAStarAdapter(
        neighbors=_grid_neighbors,
        heuristic=lambda s, _c: np.asarray([np.linalg.norm(np.asarray(s, dtype=float)), 0.0], dtype=float),
        goal_test=_goal_near_zero,
        start_state=np.asarray([3.0, 3.0], dtype=float),
        config=MOAStarConfig(max_expand_per_step=2, max_candidates_per_step=16, stop_on_goal=False),
    )
    clone.set_state(state)
    assert clone.get_state()["found"] == state["found"]
