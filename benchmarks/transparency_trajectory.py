"""轨迹算法透明性基准的独立数值内核与正式 Adapter 工厂。

本模块没有运行入口；由标准 Project/Case 的公共 harness 调用。裸参考只使用
NumPy 和（MAS 的真实模型分支）sklearn，不调用 Adapter、Unit、Solver 或框架
状态 codec。数值公式按当前算法实现独立表达；这些小样本证明装配透明性，
不构成算法质量排名或数学收敛性证明。
"""
from __future__ import annotations

from copy import deepcopy
import math
from typing import Any

import numpy as np


TRAJECTORY_NAMES = (
    "sa", "vns", "pattern_search", "gaussian_search", "gradient_descent",
    "single_trajectory_adaptive", "trust_region_dfo", "trust_region_nonsmooth",
    "trust_region_subspace", "trust_region_mo_dfo", "mas",
)
TRAJECTORY_START = (1.5, -1.0)
TRAJECTORY_BOUNDS = ((-10.0, 10.0), (-10.0, 10.0))
MO_WEIGHTS = np.asarray((0.4, 0.6))


def evaluate_trajectory(name: str, candidate: Any) -> np.ndarray:
    """共享测试问题的纯数学定义；不调用 Problem/Provider。"""
    x = np.asarray(candidate, dtype=float).reshape(-1)
    if name == "trust_region_mo_dfo":
        return np.asarray((np.sum(x * x), np.sum((x - 1.0) ** 2)))
    if name == "trust_region_nonsmooth":
        return np.asarray((np.sum(np.abs(x)),))
    return np.asarray((np.sum(x * x),))


def _scalar(name, objectives):
    obj = np.asarray(objectives, dtype=float)
    return obj @ MO_WEIGHTS if name == "trust_region_mo_dfo" else np.sum(obj, axis=-1)


class FixedTrajectoryInitializer:
    """显式无状态直属初始化角色；初值仍经过正式评估/接纳路径。"""
    stateless = True

    def checkpoint_identity(self):
        return {"kind": "transparency_trajectory_start", "values": list(TRAJECTORY_START)}

    def initialize(self, problem, context):
        return np.asarray(TRAJECTORY_START, dtype=float)


class NormalTrajectoryMutation:
    """直属局部 RNG 及其数据 codec，由 Adapter 原事务/checkpoint 持有。"""
    context_requires = ("mutation_sigma",)

    def __init__(self):
        self.rng = np.random.default_rng(0)

    def checkpoint_identity(self):
        return {"kind": "transparency_context_normal", "version": 1}

    def set_random_seed(self, seed):
        self.rng = np.random.default_rng(seed)

    def mutate(self, candidate, context):
        x = np.asarray(candidate, dtype=float)
        return x + self.rng.normal(0.0, float(context["mutation_sigma"]), size=x.shape)

    def get_state(self):
        return {"rng": deepcopy(self.rng.bit_generator.state)}

    def set_state(self, state):
        self.rng.bit_generator.state = deepcopy(state["rng"])


def make_trajectory_adapter(name: str, seed: int):
    """完整框架端真实算法；不由裸参考包装成 Adapter。"""
    if name not in TRAJECTORY_NAMES:
        raise ValueError(f"unknown trajectory algorithm: {name}")
    from nsgablack import adapters

    init = FixedTrajectoryInitializer()
    if name == "sa":
        return adapters.SimulatedAnnealingAdapter(initializer=init,
            mutator=NormalTrajectoryMutation(), batch_size=4, random_seed=seed,
            initial_temperature=0.7, cooling_rate=0.8, base_sigma=0.4)
    if name == "vns":
        return adapters.VNSAdapter(initializer=init, mutator=NormalTrajectoryMutation(),
            batch_size=4, base_sigma=0.4, k_max=3, restart_on_stagnation=False)
    if name == "pattern_search":
        return adapters.PatternSearchAdapter(initializer=init, step_size=0.4, max_directions=2)
    if name == "gaussian_search":
        return adapters.GaussianSearchAdapter(initializer=init, initialization="center",
            population_size=4, mutation_scale=0.4, random_seed=seed)
    if name == "gradient_descent":
        return adapters.GradientDescentAdapter(initializer=init, learning_rate=0.15,
            epsilon=0.01, max_directions=2)
    if name == "single_trajectory_adaptive":
        return adapters.SingleTrajectoryAdaptiveAdapter(initializer=init,
            mutator=NormalTrajectoryMutation(), batch_size=4, initial_sigma=0.4,
            restart_patience=100, accept_worse_prob=0.05)
    if name == "mas":
        return adapters.MASAdapter(initializer=init, batch_size=4, random_seed=seed,
            enable_surrogate=True, surrogate_model_type="rf", surrogate_min_train_samples=3)
    common = dict(initializer=init, batch_size=4, initial_radius=0.4, random_seed=seed)
    if name == "trust_region_dfo":
        return adapters.TrustRegionDFOAdapter(**common)
    if name == "trust_region_nonsmooth":
        return adapters.TrustRegionNonSmoothAdapter(**common)
    if name == "trust_region_subspace":
        return adapters.TrustRegionSubspaceAdapter(**common, subspace_dim=1, resample_every=2)
    return adapters.TrustRegionMODFOAdapter(**common, weight_method="fixed",
        fixed_weights=tuple(MO_WEIGHTS))


def trajectory_notes(name: str) -> dict[str, Any]:
    return {
        "reference": "independent NumPy state machine; MAS uses sklearn RandomForestRegressor directly",
        "shared_math": "only problem objective definitions and NumPy/sklearn numerical primitives",
        "seed_alignment": "independently reproduces top-level child seed and one seed slot per bound operator; no framework RNG calls",
        "scope": "two-dimensional unconstrained numeric candidates; all baseline/probe/trial evaluations counted",
        "not_covered": ["constraint admission", "semantic metadata repair", "nested pool-task routing",
                        "large-dimension performance", "statistical optimizer ranking"],
        "model": "200-tree RF, random_state=42, refit every accepted batch from >=3 samples" if name == "mas" else None,
        "comparison": "fixed weights (0.4,0.6), two sphere objectives" if name == "trust_region_mo_dfo" else "single-objective minimization",
    }


class TrajectoryReference:
    """独立裸算法；step 返回本轮真实送评序列及更新后语义状态。"""

    def __init__(self, name: str, seed: int, evaluate=None):
        if name not in TRAJECTORY_NAMES:
            raise ValueError(f"unknown trajectory algorithm: {name}")
        self.name, self.seed = name, int(seed)
        self.evaluate = evaluate
        # 显式复现装配种子协议，未复用 Solver.fork_rng。无显式算法种子的
        # 四个算法先从顶层 Generator 派生子种子。每个绑定角色均占一个种子槽。
        implicit = name in {"vns", "pattern_search", "gradient_descent", "single_trajectory_adaptive"}
        child_seed = int(np.random.default_rng(seed).integers(0, 2**63 - 1)) if implicit else seed
        self.rng = np.random.default_rng(child_seed)
        self.rng.integers(0, 2**32)  # initializer binding, even though stateless
        self.mutation_rng = None
        if name in {"sa", "vns", "single_trajectory_adaptive"}:
            self.mutation_rng = np.random.default_rng(int(self.rng.integers(0, 2**32)))
        self.current = None
        self.current_score = None
        self.best = None
        self.best_score = None
        self.temperature = 0.7
        self.sigma = 0.4
        self.step_size = 0.4
        self.learning_rate = 0.15
        self.radius = 0.4
        self.k = 0
        self.history = []
        self.no_improve = 0
        self.trial = None
        self.basis = None
        self.basis_steps = 0
        self.history_x, self.history_f = [], []
        self.model = None
        self.steps = 0

    def _draw(self):
        name = self.name
        if self.current is None:
            return np.asarray((TRAJECTORY_START,), dtype=float), "baseline"
        if name == "gradient_descent" and self.trial is not None:
            return np.asarray((self.trial.copy(),)), "trial"
        if name in {"sa", "vns", "single_trajectory_adaptive"}:
            sigma = (0.4 * (self.temperature / 0.7) if name == "sa" else
                     min(10.0, 0.4 * 1.6**self.k) if name == "vns" else self.sigma)
            return np.asarray([self.current + self.mutation_rng.normal(0.0, sigma, size=self.current.shape)
                               for _ in range(4)]), "neighbors"
        if name in {"pattern_search", "gradient_descent"}:
            dims = self.rng.choice(2, size=2, replace=False)
            delta = self.step_size if name == "pattern_search" else 0.01
            rows = []
            for dim in dims:
                for sign in (1, -1):
                    row = self.current.copy()
                    row[dim] += delta * sign
                    rows.append(row)
            return np.asarray(rows), ("poll", dims)
        if name == "gaussian_search":
            return np.asarray([self.current.copy(), *[self.current + self.rng.normal(0.0, 0.4, size=2)
                                                      for _ in range(3)]]), "neighbors"
        if name.startswith("trust_region_"):
            if name == "trust_region_subspace":
                if self.basis is None or self.basis_steps % 2 == 0:
                    self.basis = np.linalg.qr(self.rng.normal(size=(2, 1)))[0][:, :1]
                self.basis_steps += 1
            rows = [self.current.copy()]
            for _ in range(3):
                if name == "trust_region_subspace":
                    delta = self.basis @ self.rng.uniform(-1.0, 1.0, size=1)
                    ray = delta * self.radius
                    positive, negative = ray > 0, ray < 0
                    scale = 1.0
                    if np.any(positive):
                        scale = min(scale, float(np.min((10.0 - self.current[positive]) / ray[positive])))
                    if np.any(negative):
                        scale = min(scale, float(np.min((-10.0 - self.current[negative]) / ray[negative])))
                    row = self.current + max(0.0, scale) * ray
                else:
                    row = np.clip(self.current + self.radius * self.rng.uniform(-1.0, 1.0, size=2), -10.0, 10.0)
                rows.append(row)
            return np.asarray(rows), "neighbors"
        # MAS: two exploration points, then two points selected from six model
        # proposals when fitted. The reference directly owns the sklearn model.
        rows = [np.clip(self.current + self.rng.normal(size=2) * 0.5, -10.0, 10.0)
                for _ in range(2)]
        if self.model is not None:
            pool = np.asarray([self.current + self.rng.normal(size=2) * 0.5 for _ in range(6)])
            order = np.argsort(self.model.predict(pool))[:2]
            rows.extend(np.clip(pool[order], -10.0, 10.0))
        else:
            rows.extend(np.clip(self.current + self.rng.normal(size=2) * 0.5, -10.0, 10.0)
                        for _ in range(2))
        return np.asarray(rows), "neighbors"

    def step(self):
        rows, stage = self._draw()
        evaluated = ([self.evaluate(row.copy()) for row in rows] if self.evaluate is not None else
                     [(evaluate_trajectory(self.name, row), 0.0) for row in rows])
        objectives = np.asarray([np.asarray(value[0], dtype=float).reshape(-1) for value in evaluated])
        violations = np.asarray([float(value[1]) for value in evaluated])
        if np.any(violations != 0.0):
            raise ValueError("Trajectory transparency fixture requires unconstrained evaluations")
        scores = _scalar(self.name, objectives)
        best = int(np.argmin(scores))
        score = float(scores[best])
        if self.best_score is None or score < self.best_score:
            self.best, self.best_score = rows[best].copy(), score
        baseline = self.current_score is None
        if baseline:
            self.current, self.current_score = rows[0].copy(), float(scores[0])
        elif self.name == "sa":
            for i, candidate_score in enumerate(scores):
                delta = float(candidate_score) - self.current_score
                if delta <= 0 or self.rng.random() < math.exp(-max(0.0, delta) / max(self.temperature, 1e-6)):
                    self.current, self.current_score = rows[i].copy(), float(candidate_score)
                    break
            self.temperature = max(1e-6, self.temperature * 0.8)
        elif self.name == "gradient_descent":
            if stage == "trial":
                improved = score < self.current_score
                if improved:
                    self.current, self.current_score = rows[0].copy(), score
                self.learning_rate = max(1e-5, self.learning_rate * (1.05 if improved else 0.7))
                self.trial = None
            else:
                gradient = np.zeros(2)
                for i, dim in enumerate(stage[1]):
                    width = (rows[2*i] - self.current)[dim] - (rows[2*i+1] - self.current)[dim]
                    if abs(width) > 1e-12:
                        gradient[dim] = (scores[2*i] - scores[2*i+1]) / width
                self.trial = self.current - self.learning_rate * gradient
        elif self.name == "single_trajectory_adaptive":
            improved = score < self.current_score
            if improved or self.rng.random() < 0.05:
                self.current, self.current_score = rows[best].copy(), score
            self.no_improve = 0 if improved else self.no_improve + 1
            self.history.append(int(improved))
            self.history = self.history[-25:]
            self.sigma = float(np.clip(self.sigma * np.exp(1.2 * (0.25 - float(np.mean(self.history)))), 0.02, 2.0))
        elif self.name == "mas":
            self.current, self.current_score = rows[best].copy(), score
        else:
            improved = score < self.current_score
            if self.name.startswith("trust_region_"):
                tolerance = 1e-6 if self.name == "trust_region_nonsmooth" else 1e-8
                improved = self.current_score - score > tolerance
            if improved:
                self.current, self.current_score = rows[best].copy(), score
            if self.name == "vns":
                self.k = 0 if improved else min(3, self.k + 1)
            elif self.name == "pattern_search":
                self.step_size = max(1e-4, self.step_size * (1.2 if improved else 0.6))
            elif self.name.startswith("trust_region_"):
                expand = 1.3 if self.name == "trust_region_nonsmooth" else 1.5
                self.radius = min(2.0, self.radius * expand) if improved else max(1e-6, self.radius * 0.7)
        if self.name == "mas":
            self.history_x.extend(row.copy() for row in rows)
            self.history_f.extend(objectives[:, 0].tolist())
            if len(self.history_x) >= 3:
                from sklearn.ensemble import RandomForestRegressor
                self.model = RandomForestRegressor(n_estimators=200, random_state=42)
                self.model.fit(np.asarray(self.history_x), np.asarray(self.history_f))
        self.steps += 1
        return {"candidates": rows.tolist(), "objectives": objectives.tolist(),
                "violations": violations.tolist(), "state": self.state()}

    def state(self):
        state = {"current": None if self.current is None else self.current.tolist(),
                 "current_score": self.current_score,
                 "best": None if self.best is None else self.best.tolist(), "best_score": self.best_score}
        state.update(self._control())
        return state

    def _control(self):
        name = self.name
        if name == "sa":
            return {"temperature": self.temperature}
        if name == "vns":
            return {"k": self.k}
        if name == "pattern_search":
            return {"step_size": self.step_size}
        if name == "gradient_descent":
            return {"learning_rate": self.learning_rate, "trial": None if self.trial is None else self.trial.tolist()}
        if name == "single_trajectory_adaptive":
            return {"sigma": self.sigma, "success_history": list(self.history), "no_improve_steps": self.no_improve}
        if name.startswith("trust_region_"):
            result = {"radius": self.radius}
            if name == "trust_region_subspace":
                result.update(basis=None if self.basis is None else self.basis.tolist(), basis_steps=self.basis_steps)
            if name == "trust_region_mo_dfo":
                result["weights"] = MO_WEIGHTS.tolist() if self.steps else None
            return result
        if name == "mas":
            return {"history_count": len(self.history_x), "model_fitted": self.model is not None}
        return {}

    def checkpoint(self):
        """裸参考自有数据状态；不使用 Adapter.get_state/Unit codec。"""
        state = deepcopy({key: value for key, value in self.__dict__.items()
                          if key not in {"model", "evaluate", "rng", "mutation_rng"}})
        state["rng_state"] = deepcopy(self.rng.bit_generator.state)
        state["mutation_rng_state"] = (None if self.mutation_rng is None else
                                       deepcopy(self.mutation_rng.bit_generator.state))
        return state

    @classmethod
    def restore(cls, checkpoint, evaluate=None):
        result = cls(checkpoint["name"], checkpoint["seed"], evaluate=evaluate)
        result.__dict__.update(deepcopy({key: value for key, value in checkpoint.items()
                                       if key not in {"rng_state", "mutation_rng_state"}}))
        result.rng.bit_generator.state = deepcopy(checkpoint["rng_state"])
        if checkpoint["mutation_rng_state"] is not None:
            result.mutation_rng.bit_generator.state = deepcopy(checkpoint["mutation_rng_state"])
        if result.name == "mas" and len(result.history_x) >= 3:
            from sklearn.ensemble import RandomForestRegressor
            result.model = RandomForestRegressor(n_estimators=200, random_state=42)
            result.model.fit(np.asarray(result.history_x), np.asarray(result.history_f))
        return result


def trajectory_state(name: str, adapter, solver) -> dict[str, Any]:
    """只读采集真实算法的搜索状态及其正式交付的已评估最好引用。"""
    if name == "gaussian_search":
        current, current_score = adapter.best_x, adapter.best_score
    elif name.startswith("trust_region_"):
        current, current_score = adapter._center, adapter._best_score
    elif name == "mas":
        current = adapter._center
        selected = adapter._pool_results.current
        current_score = None if selected is None else selected.score
    else:
        current, current_score = adapter.current_x, adapter.current_score
    refs = adapter.get_pool_refinement_results(solver)
    best = None if not refs else solver.read_solutions(refs[:1]).numeric_matrix[0]
    state = {"current": None if current is None else np.asarray(current).tolist(),
             "current_score": current_score,
             "best": None if best is None else best.tolist(),
             "best_score": None if best is None else float(_scalar(name, evaluate_trajectory(name, best)))}
    if name == "sa":
        state["temperature"] = adapter.temperature
    elif name == "vns":
        state["k"] = adapter.k
    elif name == "pattern_search":
        state["step_size"] = adapter.step_size
    elif name == "gradient_descent":
        state.update(learning_rate=adapter.learning_rate,
                     trial=None if adapter._trial_values is None else adapter._trial_values.tolist())
    elif name == "single_trajectory_adaptive":
        state.update(sigma=adapter.sigma, success_history=list(adapter.success_history),
                     no_improve_steps=adapter.no_improve_steps)
    elif name.startswith("trust_region_"):
        state["radius"] = adapter._radius
        if name == "trust_region_subspace":
            state.update(basis=None if adapter._basis is None else adapter._basis.tolist(), basis_steps=adapter._steps)
        if name == "trust_region_mo_dfo":
            state["weights"] = None if adapter._weights is None else adapter._weights.tolist()
    elif name == "mas":
        state.update(history_count=len(adapter._X), model_fitted=adapter._surrogate_is_fitted())
    return state


def make_trajectory_problem(name):
    from nsgablack.core import BlackBoxProblem

    class TrajectoryProblem(BlackBoxProblem):
        def __init__(self):
            super().__init__(dimension=2,
                objectives=["minimize"] * (2 if name == "trust_region_mo_dfo" else 1),
                bounds=list(TRAJECTORY_BOUNDS))

        def evaluate(self, candidate):
            return evaluate_trajectory(name, candidate)

    return TrajectoryProblem()


def trajectory_reference(name, seed, steps, evaluate):
    reference = TrajectoryReference(name, seed, evaluate=evaluate)
    trace = [reference.step() for _ in range(steps)]
    return {"state": reference.state(), "trace": trace}


def specs():
    """父 Project/Case 的统一登记；本模块不另设 CLI 或私有 runner。"""
    from functools import partial
    from benchmarks.transparency_core import PairSpec

    return [PairSpec(name=name,
        make_problem=partial(make_trajectory_problem, name),
        make_adapter=partial(make_trajectory_adapter, name),
        make_pipeline=None,
        reference=partial(trajectory_reference, name),
        project=partial(_project, name),
        steps=6,
        population_size=None,
        metric_problem=None,
        metadata=trajectory_notes(name)) for name in TRAJECTORY_NAMES]


def _project(name, solver):
    return trajectory_state(name, solver.adapter, solver)
