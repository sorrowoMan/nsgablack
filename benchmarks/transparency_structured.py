"""结构算法的独立数值参考，供正式透明性 Project/Case 导入。

本模块不建立 Solver 运行入口。bare 实现只依赖 NumPy、math 和 heapq，
不调用 Adapter、Unit、GP/CMA 框架组件。工厂与状态观察用于配对的框架侧。
这些小型实验检验数值流和结构状态透明性，不证明算法最优性。
"""
from __future__ import annotations

from copy import deepcopy
import heapq
import math

import numpy as np


ALGORITHMS = ("astar", "moa_star", "bayesian_optimization", "cmaes", "map_elites", "fixed_candidate",
              "gradient_optimizer_sgd", "gradient_optimizer_adam", "gradient_optimizer_adamw")
BO_GRID = np.linspace(0., 1., 17)[:, None]
MAP_POINTS = np.asarray(((.1, .1), (.8, .1), (.1, .8), (.8, .8), (.2, .2), (.6, .1),
                         (.1, .6), (.6, .6), (.2, .2), (1., 1.), (.5, .5), (.3, .3)))
INITIAL = {"astar": np.asarray([0.]), "moa_star": np.asarray([0.]),
           "bayesian_optimization": np.asarray([0.]), "cmaes": np.asarray([1., -.5]),
           "map_elites": MAP_POINTS[0].copy(), "fixed_candidate": np.asarray([.3, -.4])}
INITIAL.update({name: np.asarray([1., -.5]) for name in ALGORITHMS if name.startswith("gradient_optimizer_")})


def numeric(value):
    """Convert observations to detached JSON values, never constructing a Unit."""
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(k): numeric(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [numeric(v) for v in value]
    return value


def objective(name, x):
    x = np.asarray(x, dtype=float).reshape(-1)
    if name == "bayesian_optimization":
        return np.asarray([(x[0] - .25) ** 2])
    if name in {"astar", "moa_star"}:
        f = np.asarray([(x[0] - 4.) ** 2, (x[0] - 6.) ** 2])
        return f if name == "moa_star" else f[:1]
    return np.asarray([float(x @ x)])


def neighbors(x, context=None):
    """Small converging DAG, including distinct paths to the same state."""
    graph = {0: (1, 2), 1: (3, 4), 2: (4, 5), 3: (6,), 4: (6,), 5: (6,),
             6: (7,), 7: (8,), 8: (9,), 9: (10,)}
    return tuple(np.asarray([float(n)]) for n in graph.get(int(np.asarray(x)[0]), ()))


def edge_cost(parent, child, context=None):
    return 1. + .1 * (int(np.asarray(child)[0]) % 3)


def vector_edge_cost(parent, child, context=None):
    p, c = int(np.asarray(parent)[0]), int(np.asarray(child)[0])
    return np.asarray([1. + (c % 2), 1. + ((p + c) % 3)])


def metadata(name):
    if name not in ALGORITHMS:
        raise KeyError(name)
    dimension = len(INITIAL[name])
    return {"name": name, "dimension": dimension, "num_objectives": 2 if name == "moa_star" else 1,
            "initial": INITIAL[name].tolist(), "bounds": [(0., 1.)] * dimension if name in {
                "bayesian_optimization", "map_elites"} else [(-100., 100.)] * dimension,
            "reference_kind": "independent_numpy_formula", "shared_algorithm_components": [],
            "scope": ({"astar": "new evaluated root; edge plus weighted objective; frontier/closed/best",
                      "moa_star": "new evaluated root; vector edge labels; strict dominance and Pareto labels",
                      "bayesian_optimization": "fixed exact RBF GP; LCB; grid argmin; all direct observations",
                      "cmaes": "positive weighted full covariance; complete cohorts; evolution paths and incumbent",
                      "map_elites": "finite emitter; identity descriptor; 2x2 cells; raw scalar champions",
                      "fixed_candidate": "same representation candidate evaluated each step"}.get(name,
                          "inline analytic gradient; clipping; weight decay; optimizer moments and evaluated result")),
            "steps": 6, "budget": "full proposals; no partial admission; no repair changes",
            "kernel_source": "independent formulas in benchmarks/transparency_structured.py",
            "provider_transition": "not exercised; inline Feedback.gradients only" if name.startswith("gradient_optimizer_") else None,
            "gradient_source": ("analytic 2*x once per bare step; no extra F call; Problem Feedback also computes 2*x"
                if name.startswith("gradient_optimizer_") else None),
            "configuration": {"astar": "new_root, edge, objective_weight=.03; no heuristic",
                "moa_star": "new_root, edge, objective_weight=0; no heuristic; sum priority",
                "bayesian_optimization": "default RBF/LCB; 17-point acquisition grid",
                "cmaes": "default positive parameters lambda=4, mu=2; sigma=.35, 2D mean=(1,-.5)",
                "map_elites": "default grid/descriptor/competition; finite 12-point emitter, batch_size=2",
                "fixed_candidate": "constant numeric pipeline seed (.3,-.4)"}.get(name,
                    "lr=.07, decay=.03, max_gradient_norm=1.5; default Adam beta/epsilon")}


def make_adapter(name, seed=13):
    """Only the measured framework side imports or instantiates Adapters."""
    if name == "astar":
        from nsgablack.adapters.astar import AStarAdapter, AStarConfig
        return AStarAdapter(neighbors=neighbors, edge_cost=edge_cost, start_state=INITIAL[name].copy(),
            config=AStarConfig(pool_start_policy="new_root", objective_weight=.03))
    if name == "moa_star":
        from nsgablack.adapters.moa_star import MOAStarAdapter, MOAStarConfig
        return MOAStarAdapter(neighbors=neighbors, edge_cost=vector_edge_cost, start_state=INITIAL[name].copy(),
            config=MOAStarConfig(pool_start_policy="new_root", path_cost_mode="edge", objective_weight=0.))
    if name == "bayesian_optimization":
        from nsgablack.adapters.bayesian_optimization import BayesianOptimizationAdapter, GridAcquisitionOptimizer
        return BayesianOptimizationAdapter(optimizer=GridAcquisitionOptimizer(BO_GRID))
    if name == "cmaes":
        from nsgablack.adapters.cmaes import CMAESAdapter
        return CMAESAdapter(INITIAL[name].copy(), sigma=.35, seed=int(seed))
    if name == "map_elites":
        from nsgablack.adapters.map_elites import MapElitesAdapter, MapElitesConfig, SequenceEmitter
        return MapElitesAdapter(MapElitesConfig(batch_size=2, random_seed=int(seed)), emitter=SequenceEmitter(MAP_POINTS))
    if name == "fixed_candidate":
        from nsgablack.adapters.fixed_candidate import FixedCandidateAdapter
        return FixedCandidateAdapter()
    if name.startswith("gradient_optimizer_"):
        from nsgablack.adapters.gradient_optimizer import GradientOptimizerAdapter
        return GradientOptimizerAdapter(optimizer=name.rsplit("_", 1)[1], learning_rate=.07,
            weight_decay=.03, max_gradient_norm=1.5)
    raise KeyError(name)


def _bo_posterior(x, y):
    """Independent RBF/Cholesky equations with declared default hyperparameters."""
    x = np.asarray(x, dtype=float)
    def kernel(a, b):
        delta = a[:, None, :] - b[None, :, :]
        return np.exp(-.5 * np.sum(delta * delta, axis=2) / .25 ** 2)
    covariance = kernel(x, x) + 1e-8 * np.eye(len(x))
    factor = np.linalg.cholesky(covariance)
    cross = kernel(BO_GRID, x)
    alpha = np.linalg.solve(factor.T, np.linalg.solve(factor, np.asarray(y)))
    mean = cross @ alpha
    projected = np.linalg.solve(factor, cross.T)
    std = np.sqrt(np.maximum(0., 1. - np.sum(projected ** 2, axis=0)))
    values = mean - 2. * std
    index = int(np.argmin(values))
    return BO_GRID[index:index + 1].copy(), {"grid": BO_GRID.tolist(), "mean": mean.tolist(),
        "std": std.tolist(), "acquisition": values.tolist(), "selected_index": index}


def _bare_bo(steps, evaluate):
    batches, states, observations, report = [], [], [], {}
    for step in range(steps):
        if step == 0:
            batch = np.asarray([[0.], [1.]])
        else:
            batch, report = _bo_posterior([r[0] for r in observations], [r[1] for r in observations])
        y = [float(evaluate(row)[0][0]) for row in batch]
        observations.extend((row.tolist(), value) for row, value in zip(batch, y))
        batches.append(batch.tolist())
        states.append({"observations_x": [row[0] for row in observations],
            "observations_y": [row[1] for row in observations], "model_revision": step + 1,
            "accepted_values": batch.tolist(), "last_acquisition": deepcopy(report)})
    return batches, states


def _bare_cma(seed, steps, evaluate):
    """Independent positive-weight CMA equations; no framework updater/sampler."""
    rng = np.random.default_rng(seed)
    mean, covariance, sigma = INITIAL["cmaes"].copy(), np.eye(2), .35
    path_c, path_sigma = np.zeros(2), np.zeros(2)
    n, mu, batches, states, best = 2, 2, [], [], {}
    weights = np.log(mu + .5) - np.log(np.arange(1, mu + 1))
    weights /= weights.sum()
    effective = float(1 / (weights @ weights))
    cc = (4 + effective / n) / (n + 4 + 2 * effective / n)
    cs = (effective + 2) / (n + effective + 5)
    c1 = 2 / ((n + 1.3) ** 2 + effective)
    cmu = min(1 - c1, 2 * (effective - 2 + 1 / effective) / ((n + 2) ** 2 + effective))
    damping = 1 + 2 * max(0., math.sqrt((effective - 1) / (n + 1)) - 1) + cs
    chi = math.sqrt(2) * math.exp(math.lgamma((n + 1) / 2) - math.lgamma(n / 2))
    for iteration in range(steps):
        z = rng.standard_normal((4, n))
        eigenvalues, basis = np.linalg.eigh(covariance)
        offsets = z @ ((basis * np.sqrt(eigenvalues)) @ basis.T).T
        x = mean[None, :] + sigma * offsets
        y = np.asarray([evaluate(row)[0][0] for row in x])
        order = np.argsort(y, kind="stable")
        chosen = offsets[order[:mu]]
        weighted = np.sum(weights[:, None] * chosen, axis=0)
        invsqrt = (basis * (1 / np.sqrt(eigenvalues))) @ basis.T
        path_sigma = (1 - cs) * path_sigma + math.sqrt(cs * (2 - cs) * effective) * (invsqrt @ weighted)
        h = int(np.linalg.norm(path_sigma) / math.sqrt(1 - (1 - cs) ** (2 * (iteration + 1))) / chi
                < 1.4 + 2 / (n + 1))
        path_c = (1 - cc) * path_c + h * math.sqrt(cc * (2 - cc) * effective) * weighted
        rank_mu = np.einsum("i,ij,ik->jk", weights, chosen, chosen)
        covariance = ((1 - c1 - cmu) * covariance + c1 * (np.outer(path_c, path_c)
            + (1 - h) * cc * (2 - cc) * covariance) + cmu * rank_mu)
        covariance = (covariance + covariance.T) / 2
        mean = mean + sigma * weighted
        sigma *= math.exp(cs / damping * (np.linalg.norm(path_sigma) / chi - 1))
        if not best or float(y[order[0]]) < best["objective"]:
            best = {"candidate": x[order[0]].tolist(), "objective": float(y[order[0]])}
        batches.append(x.tolist())
        states.append(numeric({"mean": mean, "covariance": covariance, "sigma": sigma,
            "path_c": path_c, "path_sigma": path_sigma, "iteration": iteration + 1,
            "last_candidates": x, "last_z": z, "last_offsets": offsets, "last_ranking": order,
            "last_selected_indices": order[:mu], "last_raw_objectives": y[:, None],
            "last_h_sigma": h, "pending_count": 0, "best": deepcopy(best)}))
    return batches, states


def _bare_map(steps, evaluate):
    batches, states, archive, replacements = [], [], {}, 0
    for step in range(steps):
        x = MAP_POINTS[step * 2:step * 2 + 2]
        if not len(x):
            break
        for row in x:
            cell = tuple(np.minimum(np.floor(row * 2).astype(int), 1))
            f, violation = evaluate(row)
            if violation != 0:
                raise ValueError("structured MAP fixture is unconstrained")
            quality = float(f[0])
            if cell not in archive or quality < archive[cell]["quality"]:
                archive[cell] = {"cell": list(cell), "descriptor": row.tolist(), "candidate": row.tolist(),
                    "objectives": [quality], "violation": 0., "quality": quality}
                replacements += 1
        batches.append(x.tolist())
        states.append({"entries": [deepcopy(archive[k]) for k in sorted(archive)], "evaluations": (step + 1) * 2,
            "replacements": replacements, "emitter_cursor": (step + 1) * 2, "pending_count": 0})
    return batches, states


def _dominates(left, right):
    return bool(np.all(left <= right) and np.any(left < right))


def _bare_astar(steps, evaluate):
    frontier, closed, batches, states, counter, best = [], {}, [], [], 0, None
    for step in range(steps):
        if step == 0:
            pending = [(np.asarray([0.]), None, 0.)]
        else:
            pending = []
            while frontier:
                _, order, state, g, parent = heapq.heappop(frontier)
                if state in closed:
                    continue
                closed[state] = g
                for child in neighbors([state]):
                    if int(child[0]) not in closed:
                        pending.append((child, state, g + edge_cost([state], child)))
                break
        if not pending:
            break
        batch = [row[0].tolist() for row in pending]
        for row, parent, base in pending:
            state = int(row[0])
            value = float(evaluate(row)[0][0])
            g = 0. if step == 0 else base + .03 * value
            counter += 1
            heapq.heappush(frontier, (g, counter, state, g, parent))
            if best is None or value < best["score"]:
                best = {"state": row.tolist(), "score": value}
        batches.append(batch)
        states.append({"open": [{"state": [float(state)], "g": g, "h": 0., "f": priority,
            "order": order, "parent": None if parent is None else [float(parent)]}
            for priority, order, state, g, parent in sorted(frontier)],
            "closed": [{"state": [float(k)], "g": closed[k]} for k in sorted(closed)],
            "counter": counter, "best_state": best["state"], "best_score": best["score"],
            "root_initialized": True, "pending_count": 0})
    return batches, states


def _bare_moa(steps, evaluate):
    frontier, labels, state_labels, batches, states = [], {}, {}, [], []
    counter, pareto = 0, []
    for step in range(steps):
        if step == 0:
            pending = [(np.asarray([0.]), None, np.zeros(2))]
        else:
            pending = []
            while frontier:
                _, label_id = heapq.heappop(frontier)
                if label_id not in labels:
                    continue
                parent = labels[label_id]
                for child in neighbors(parent["state"]):
                    pending.append((child, int(parent["state"][0]),
                        np.asarray(parent["g"]) + vector_edge_cost(parent["state"], child)))
                break
        if not pending:
            break
        batches.append([row[0].tolist() for row in pending])
        for row, parent, g in pending:
            evaluate(row)  # Raw objectives are observed but do not replace vector path g.
            state = int(row[0])
            current = [i for i in state_labels.get(state, ()) if i in labels]
            if not any(_dominates(np.asarray(labels[i]["g"]), g) for i in current):
                removed = [i for i in current if _dominates(g, np.asarray(labels[i]["g"]))]
                for i in removed:
                    del labels[i]
                counter += 1
                labels[counter] = {"id": counter, "state": row.tolist(), "g": g.tolist(),
                    "h": [0., 0.], "f": g.tolist(), "parent": None if parent is None else [float(parent)]}
                state_labels[state] = [i for i in current if i not in removed] + [counter]
                heapq.heappush(frontier, (float(g.sum()), counter))
            if step and not any(_dominates(np.asarray(p["g"]), g) for p in pareto):
                pareto = [p for p in pareto if not _dominates(g, np.asarray(p["g"]))]
                pareto.append({"state": row.tolist(), "g": g.tolist()})
        states.append({"labels": [deepcopy(labels[k]) for k in sorted(labels)],
            "open": [[priority, i] for priority, i in sorted(frontier)],
            "counter": counter, "pareto": deepcopy(pareto), "pending_count": 0, "root_initialized": True})
    return batches, states


def _bare_gradient(name, steps, evaluate):
    method = name.rsplit("_", 1)[1]
    x, m, v = INITIAL[name].copy(), None, None
    batches, states, best, best_x = [], [], math.inf, None
    for step in range(steps):
        candidate = x.copy()
        f, violation = evaluate(candidate)
        if violation != 0:
            raise ValueError("structured gradient fixture is unconstrained")
        score = float(f[0])
        if score < best:
            best, best_x = score, candidate.copy()
        gradient = 2. * candidate  # Analytic derivative; no second objective evaluation.
        norm = float(np.linalg.norm(gradient))
        if norm > 1.5:
            gradient *= 1.5 / norm
        norm = float(np.linalg.norm(gradient))
        effective = gradient + .03 * candidate if method in {"sgd", "adam"} else gradient
        if method == "sgd":
            delta = .07 * effective
        else:
            if m is None:
                m, v = np.zeros_like(candidate), np.zeros_like(candidate)
            m = .9 * m + (1 - .9) * effective
            v = .999 * v + (1 - .999) * effective ** 2
            delta = .07 * (m / (1 - .9 ** (step + 1))) / (np.sqrt(v / (1 - .999 ** (step + 1))) + 1e-8)
            if method == "adamw":
                delta += .07 * .03 * candidate
        x = candidate - delta
        batches.append([candidate.tolist()])
        states.append(numeric({"current_x": x, "first_moment": m, "second_moment": v,
            "step_index": step + 1, "current_score": None, "best_score": best,
            "last_gradient_norm": norm, "evaluated_current": candidate, "evaluated_best": best_x,
            "pending": False}))
    return batches, states


def run_bare(name, seed=13, steps=4, evaluate=None):
    """Run an independent tiny reference; no Solver or Adapter invocation occurs."""
    if type(steps) is not int or not 1 <= steps <= 6:
        raise ValueError("structured references require 1..6 committed steps")
    observations = []
    evaluate_raw = evaluate or (lambda x: (objective(name, x), 0.))
    def measured(x):
        f, v = evaluate_raw(np.array(x, dtype=float, copy=True))
        f = np.asarray(f, dtype=float).reshape(-1)
        observations.append({"x": numeric(np.asarray(x)), "f": f.tolist(), "v": float(v)})
        return f, float(v)
    if name == "bayesian_optimization":
        batches, states = _bare_bo(steps, measured)
    elif name == "cmaes":
        batches, states = _bare_cma(int(seed), steps, measured)
    elif name == "map_elites":
        batches, states = _bare_map(steps, measured)
    elif name == "astar":
        batches, states = _bare_astar(steps, measured)
    elif name == "moa_star":
        batches, states = _bare_moa(steps, measured)
    elif name == "fixed_candidate":
        batches = [[INITIAL[name].tolist()] for _ in range(steps)]
        states = [{"candidate": INITIAL[name].tolist(), "counter": step + 1} for step in range(steps)]
        for batch in batches:
            measured(batch[0])
    elif name.startswith("gradient_optimizer_"):
        batches, states = _bare_gradient(name, steps, measured)
    else:
        raise KeyError(name)
    states = numeric(states)
    return {"batches": batches, "observations": observations, "trace": [{"state": state} for state in states],
            "states": states, "state": states[-1], "evaluations": sum(map(len, batches)), "steps": len(batches),
            "analytic_gradient_calls": len(observations) if name.startswith("gradient_optimizer_") else 0,
            "reference_kind": "independent_numpy_formula", "shared_algorithm_components": []}


def extract_state(name, adapter, solver=None):
    """Observe only already-created runtime state on the framework side."""
    if name == "fixed_candidate":
        unit = adapter.current_unit
        candidate = None if unit is None else unit.to_candidate()
        return {"candidate": None if candidate is None else numeric(np.asarray(getattr(candidate, "values", candidate), dtype=float)),
                "counter": adapter._unit_counter}
    if name == "astar":
        return numeric({"open": [{"state": node.state, "g": node.g, "h": node.h, "f": node.f,
            "order": order, "parent": node.parent_key} for _, order, node in sorted(adapter._open)],
            "closed": [{"state": key, "g": adapter._closed[key]} for key in sorted(adapter._closed)],
            "counter": adapter._counter, "best_state": adapter.best_state, "best_score": adapter.best_score,
            "root_initialized": adapter._root_initialized, "pending_count": len(adapter._pending)})
    if name == "moa_star":
        return numeric({"labels": [{"id": key, "state": node.state, "g": node.g, "h": node.h,
            "f": node.f, "parent": node.parent_key} for key, node in sorted(adapter._labels.items())],
            "open": [[priority, label_id] for priority, _, label_id in sorted(adapter._open)],
            "counter": adapter._counter, "pareto": [{"state": state, "g": cost} for state, cost in
                zip(adapter.pareto_states, adapter.pareto_costs)],
            "pending_count": len(adapter._pending), "root_initialized": adapter._root_initialized})
    if name.startswith("gradient_optimizer_"):
        def evaluated(selection):
            if selection is None:
                return None
            return solver.solution_pool.read((selection.ref,), allow_pending=True).numeric_matrix[0]
        return numeric({"current_x": adapter.current_x, "first_moment": adapter._first_moment,
            "second_moment": adapter._second_moment, "step_index": adapter.step_index,
            "current_score": adapter.current_score, "best_score": adapter.best_score,
            "last_gradient_norm": adapter.last_gradient_norm, "evaluated_current": evaluated(adapter._pool_results.current),
            "evaluated_best": evaluated(adapter._pool_results.best), "pending": adapter._proposal_pending})
    unit = adapter.algorithm_unit
    if unit is None:
        return None
    if name == "bayesian_optimization":
        return numeric({"observations_x": [row["x"] for row in unit.observations],
            "observations_y": [row["y"] for row in unit.observations], "model_revision": unit.model_revision,
            "accepted_values": unit.accepted_values, "last_acquisition": unit.last_acquisition})
    if name == "cmaes":
        cohort = unit.last_cohort
        return numeric({"mean": unit.mean, "covariance": unit.covariance, "sigma": unit.sigma,
            "path_c": unit.path_c, "path_sigma": unit.path_sigma, "iteration": unit.iteration,
            "last_candidates": cohort["candidates"], "last_z": cohort["z"], "last_offsets": cohort["offsets"],
            "last_ranking": cohort["ranking"], "last_selected_indices": cohort["selected_indices"],
            "last_raw_objectives": cohort["raw_objectives"], "last_h_sigma": cohort["h_sigma"],
            "pending_count": len(unit.pending), "best": {k: v for k, v in unit.best.items() if k != "ref"}})
    if name == "map_elites":
        return numeric({"entries": [{k: v for k, v in entry.items() if k != "solution_ref"} for entry in unit.entries],
            "evaluations": unit.evaluations, "replacements": unit.replacements,
            "emitter_cursor": adapter.emitter.cursor, "pending_count": adapter._pending})
    raise KeyError(name)


def make_problem(name):
    """Formal Problem surface; gradient objectives and derivatives are one evaluation."""
    from nsgablack.core import BlackBoxProblem
    from blackbase.types import Feedback
    settings = metadata(name)
    class StructuredProblem(BlackBoxProblem):
        def __init__(self):
            super().__init__(name="transparency_" + name, dimension=settings["dimension"],
                objectives=["min"] * settings["num_objectives"], bounds=settings["bounds"])
            self.gradient_calls = 0

        def evaluate(self, candidate):
            x = np.asarray(candidate, dtype=float)
            f = objective(name, x)
            if name.startswith("gradient_optimizer_"):
                self.gradient_calls += 1
                return Feedback(objectives=f, gradients=2. * x)
            return f
    return StructuredProblem()


def make_pipeline(name, seed=13):
    from nsgablack.representation import RepresentationPipeline
    from blackbase.representation import RepresentationCapabilities
    class ConstantInitializer:
        representation_capabilities = RepresentationCapabilities(frozenset({"init"}))
        def initialize(self, problem, context=None):
            return INITIAL[name].copy()
    return RepresentationPipeline(initializer=ConstantInitializer(), random_seed=int(seed))


def specs():
    """PairSpecs imported by the standard transparency Project registry."""
    from benchmarks.transparency_core import PairSpec
    return [PairSpec(name=name, make_problem=lambda name=name: make_problem(name),
        make_adapter=lambda seed, name=name: make_adapter(name, seed),
        make_pipeline=lambda seed, name=name: make_pipeline(name, seed),
        reference=lambda seed, steps, evaluate, name=name: run_bare(name, seed, steps, evaluate),
        project=lambda solver, name=name: extract_state(name, solver.adapter, solver),
        steps=6, metadata=metadata(name)) for name in ALGORITHMS]


__all__ = ["ALGORITHMS", "metadata", "make_adapter", "make_problem", "make_pipeline", "objective", "run_bare", "extract_state", "specs"]
