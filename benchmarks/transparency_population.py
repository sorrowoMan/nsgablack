"""人口算法的透明性配对内核，正式执行入口由标准 Project/Case 提供。

裸参考不构建或调用 Adapter、Unit、Solver、Pool。它只复用无状态的
FastNonDominatedSort 排序/拥挤距离算子；算法循环、变化与生存均独立实现。
NSGA-III 生存选择直接使用独立 pymoo 实现作参考；其余算法复现明确声明的数值变体。
HV/IGD 不在本模块实现，由公共 harness 使用 pymoo 官方指标计算。
"""

from __future__ import annotations

from copy import deepcopy
from functools import partial
from hashlib import sha256
from math import comb
import time
from typing import Callable

import numpy as np

from nsgablack.adapters.nsga2 import NSGA2Adapter
from nsgablack.adapters.nsga3 import NSGA3Adapter
from nsgablack.adapters.spea2 import SPEA2Adapter
from nsgablack.adapters.moead import MOEADAdapter
from nsgablack.adapters.differential_evolution import DifferentialEvolutionAdapter
from nsgablack.core import BlackBoxProblem
from nsgablack.representation import ClipRepair, GaussianMutation, RepresentationPipeline
from nsgablack.utils.performance.fast_non_dominated_sort import FastNonDominatedSort


POPULATION_SIZE = 10
DIMENSION = 8
MUTATION_SIGMA = 0.08


def initial_population(seed: int, size: int = POPULATION_SIZE) -> np.ndarray:
    """初值有独立 SeedSequence，不消耗搜索流或问题求值流。"""
    return np.random.default_rng(np.random.SeedSequence([int(seed), 7919])).uniform(
        0.0, 1.0, (int(size), DIMENSION))


class FixedPopulationInitializer:
    """正式直属 initializer：游标参与原 Adapter 的步骤与 checkpoint codec。"""

    stateless = False

    def __init__(self, values):
        self.values = np.array(values, dtype=float, copy=True)
        self.cursor = 0

    def checkpoint_identity(self):
        return {"schema": "transparency.fixed_population/v1", "shape": list(self.values.shape),
                "sha256": sha256(self.values.tobytes()).hexdigest()}

    def initialize(self, problem, context=None):
        if self.cursor >= len(self.values):
            raise ValueError("transparent population initializer exhausted")
        result = np.array(self.values[self.cursor], copy=True)
        self.cursor += 1
        return result

    def get_state(self):
        return {"cursor": self.cursor}

    def set_state(self, state):
        if (set(state) != {"cursor"} or type(state["cursor"]) is not int
                or not 0 <= state["cursor"] <= len(self.values)):
            raise ValueError("invalid fixed population initializer cursor")
        self.cursor = state["cursor"]


class OfficialPopulationProblem(BlackBoxProblem):
    """仅包装 pymoo 官方问题函数；不手写 ZDT/DTLZ 方程或参考前沿。"""

    def __init__(self, problem_name="zdt1"):
        from pymoo.problems import get_problem

        options = {"n_var": DIMENSION}
        if problem_name.startswith("dtlz"):
            options["n_obj"] = 3
        self.official = get_problem(problem_name, **options)
        self.problem_name = problem_name
        super().__init__(name=f"pymoo_{problem_name}", dimension=DIMENSION,
                         objectives=["min"] * self.official.n_obj,
                         bounds=list(zip(self.official.xl.tolist(), self.official.xu.tolist())))

    def evaluate(self, candidate):
        return np.asarray(self.official.evaluate(np.asarray(candidate), return_values_of=["F"]),
                          dtype=float).reshape(-1)


def make_population_adapter(seed: int, *, algorithm: str, population_size=POPULATION_SIZE):
    initializer = FixedPopulationInitializer(initial_population(seed, size=population_size))
    common = {"name": algorithm, "population_size": population_size, "initializer": initializer}
    if algorithm in {"nsga2", "nsga3", "spea2"}:
        common.update(offspring_size=population_size, crossover_rate=0.9,
                      mutator=GaussianMutation(sigma=MUTATION_SIGMA))
        if algorithm == "nsga3":
            return NSGA3Adapter(**common, divisions=3)
        if algorithm == "spea2":
            return SPEA2Adapter(**common, archive_size=population_size, k_nearest=1)
        return NSGA2Adapter(**common)
    if algorithm == "de":
        return DifferentialEvolutionAdapter(**common, batch_size=population_size,
            differential_weight=0.7, crossover_rate=0.9, strategy="rand1bin", objective_aggregation="sum")
    if algorithm == "moead":
        return MOEADAdapter(**common, batch_size=population_size, neighborhood_size=5,
            delta=0.9, nr=2, variation="de", de_F=0.5, de_CR=0.9, random_seed=int(seed))
    raise ValueError(f"unknown population algorithm: {algorithm}")


def make_population_pipeline(seed: int):
    del seed
    return RepresentationPipeline(repair=ClipRepair(0.0, 1.0))


def project_population(solver):
    """只读投影，state 与独立内核逐步同构，不用 get_state 冒充裸参考。"""
    adapter = solver.adapter
    x, f, v = adapter.get_population_snapshot()
    result = {"population": np.asarray(x).tolist(), "objectives": np.asarray(f).tolist(),
              "violations": np.asarray(v).tolist()}
    if isinstance(adapter, NSGA3Adapter):
        result["reference_points"] = np.asarray(adapter.reference_points).tolist()
        result["normalization"] = {k: np.asarray(v).tolist() for k, v in adapter.normalization.items()}
    if isinstance(adapter, MOEADAdapter):
        result.update(weights=np.asarray(adapter.weights).tolist(),
                      neighbors=np.asarray(adapter.neighbors).tolist(), ideal=np.asarray(adapter.ideal).tolist())
    return result


def _distances(a, b):
    aa = np.sum(a * a, axis=1, keepdims=True)
    bb = np.sum(b * b, axis=1, keepdims=True).T
    return np.sqrt(np.maximum(aa + bb - 2.0 * (a @ b.T), 0.0))


def _simplex(objectives, divisions, *, positive=False):
    rows = []

    def visit(prefix, left):
        if len(prefix) == objectives - 1:
            rows.append([*prefix, left])
        else:
            for value in range(left + 1):
                visit([*prefix, value], left - value)

    visit([], divisions)
    values = np.asarray(rows, dtype=float) / divisions
    if positive:
        values = np.clip(values, 1e-12, None)
        values /= np.sum(values, axis=1, keepdims=True)
    return values


class PopulationReferenceKernel:
    """独立裸数值内核；不借用 Adapter 的生命周期、方法或状态。"""

    def __init__(self, algorithm, seed, population_size=POPULATION_SIZE, *, initial_values=None,
                 mutation_sigma=MUTATION_SIGMA):
        if algorithm not in {"nsga2", "nsga3", "spea2", "de", "moead"}:
            raise ValueError(f"unknown population algorithm: {algorithm}")
        self.algorithm = algorithm
        self.population_size = int(population_size)
        self.initial = initial_population(seed, size=self.population_size)
        if initial_values is not None:
            self.initial = np.array(initial_values, dtype=float, copy=True)
        self.mutation_sigma = float(mutation_sigma)
        if algorithm == "moead":
            self.rng = np.random.default_rng(int(seed))
        else:
            # Single leaf is the first component to fork a Solver stream.
            root = np.random.default_rng(int(seed))
            self.rng = np.random.default_rng(int(root.integers(0, 2**63 - 1)))
        self.rng.integers(0, 2**32)  # Fixed initializer's binding seed (no local RNG).
        self.mutation_rng = None
        if algorithm in {"nsga2", "nsga3", "spea2"}:
            self.mutation_rng = np.random.default_rng(int(self.rng.integers(0, 2**32)))
        self.x = self.f = self.v = None
        self.reference_points = None
        self.weights = self.neighbors = self.ideal = None
        self.pending = None
        self.nsga3_survival = None

    def snapshot(self):
        """裸内核独立数据快照，测试自身恢复时无需任何框架 codec。"""
        return deepcopy({name: value for name, value in vars(self).items()
                         if name not in {"rng", "mutation_rng"}} | {
            "rng_state": self.rng.bit_generator.state,
            "mutation_rng_state": (None if self.mutation_rng is None
                                   else self.mutation_rng.bit_generator.state)})

    def restore(self, state):
        data = deepcopy(state)
        self.rng.bit_generator.state = data.pop("rng_state")
        mutation = data.pop("mutation_rng_state")
        if mutation is not None:
            self.mutation_rng.bit_generator.state = mutation
        for name, value in data.items():
            setattr(self, name, value)

    def project(self):
        result = {"population": self.x.tolist(), "objectives": self.f.tolist(), "violations": self.v.tolist()}
        if self.algorithm == "nsga3":
            result["reference_points"] = self.reference_points.tolist()
            norm = self.nsga3_survival.norm
            result["normalization"] = {k: np.asarray(v).tolist() for k,v in {
                "ideal":norm.ideal_point, "worst":norm.worst_point,
                "extremes":norm.extreme_points, "nadir":norm.nadir_point}.items()}
        if self.algorithm == "moead":
            result.update(weights=self.weights.tolist(), neighbors=self.neighbors.tolist(), ideal=self.ideal.tolist())
        return result

    def ask(self):
        if self.x is None:
            self.pending = {"initialization": True}
            return np.array(self.initial, copy=True)
        if self.algorithm == "de":
            targets = self.rng.integers(0, len(self.x), size=self.population_size).tolist()
            trials = []
            for index in targets:
                pool = [i for i in range(len(self.x)) if i != index]
                r1, r2, r3 = self.rng.choice(pool, 3, replace=False)
                mutant = self.x[r1] + 0.7 * (self.x[r2] - self.x[r3])
                trial = self.x[index].copy()
                forced = int(self.rng.integers(0, trial.size))
                for j in range(trial.size):
                    if self.rng.random() < 0.9 or j == forced:
                        trial[j] = mutant[j]
                trials.append(trial)
            self.pending = {"targets": targets,
                            "scores": (np.sum(self.f, axis=1) + 1e6 * self.v)[targets].copy()}
            return np.asarray(trials)
        if self.algorithm == "moead":
            modes, trials = [], []
            for index in range(len(self.x)):
                neighborhood = self.rng.random() < 0.9
                modes.append(neighborhood)
                pool = self.neighbors[index] if neighborhood else np.arange(len(self.x))
                r1, r2, r3 = self.rng.choice(pool, 3, replace=False)
                mutant = self.x[r1] + 0.5 * (self.x[r2] - self.x[r3])
                trial = self.x[index].copy()
                forced = int(self.rng.integers(0, trial.size))
                mask = self.rng.random(trial.size) < 0.9
                mask[forced] = True
                trial[mask] = mutant[mask]
                trials.append(trial)
            self.pending = {"modes": modes}
            return np.asarray(trials)
        fronts, rank = FastNonDominatedSort.sort(self.f, self.v)
        crowding = np.zeros(len(self.x))
        for front in fronts:
            crowding += FastNonDominatedSort.calculate_crowding_distance(self.f, list(front))

        def tournament():
            i, j = int(self.rng.integers(0, len(self.x))), int(self.rng.integers(0, len(self.x)))
            if self.algorithm == "nsga3":
                if (self.v[i] > 0 or self.v[j] > 0) and self.v[i] != self.v[j]:
                    return i if self.v[i] < self.v[j] else j
                return int(self.rng.choice((i,j)))
            if rank[i] < rank[j]:
                return i
            if rank[j] < rank[i]:
                return j
            return i if crowding[i] >= crowding[j] else j

        trials = []
        for _ in range(self.population_size):
            p1, p2 = self.x[tournament()], self.x[tournament()]
            if self.rng.random() > 0.9:
                child = p1.copy()
            else:
                alpha = self.rng.random(p1.size)
                child = alpha * p1 + (1.0 - alpha) * p2
            child += self.mutation_rng.normal(0.0, self.mutation_sigma, child.shape)
            trials.append(child)
        self.pending = {}
        return np.asarray(trials)

    def tell(self, candidates, objectives, violations):
        x, f, v = (np.asarray(value, dtype=float) for value in (candidates, objectives, violations))
        if self.x is None:
            self.x, self.f, self.v = x.copy(), f.copy(), v.copy()
            if self.algorithm == "nsga3":
                self.reference_points = _simplex(f.shape[1], 3)
                from pymoo.algorithms.moo.nsga3 import ReferenceDirectionSurvival
                from pymoo.util.nds.non_dominated_sorting import NonDominatedSorting
                self.nsga3_survival = ReferenceDirectionSurvival(self.reference_points)
                self.nsga3_survival.norm.update(f, nds=NonDominatedSorting().do(f, only_non_dominated_front=True))
            if self.algorithm == "moead":
                h = 1
                while comb(h + f.shape[1] - 1, f.shape[1] - 1) < len(x):
                    h += 1
                weights = _simplex(f.shape[1], h, positive=True)
                if len(weights) > len(x):
                    weights = weights[self.rng.choice(len(weights), len(x), replace=False)]
                self.weights = weights
                delta = weights[:, None, :] - weights[None, :, :]
                self.neighbors = np.argsort(np.sqrt(np.sum(delta * delta, axis=2)), axis=1)[:, :5]
                feasible = v <= 0.0
                self.ideal = np.min(f[feasible] if np.any(feasible) else f, axis=0)
            self.pending = None
            return
        if self.algorithm == "de":
            scores = np.sum(f, axis=1) + 1e6 * v
            for row, target in enumerate(self.pending["targets"]):
                if scores[row] <= self.pending["scores"][row]:
                    self.x[target], self.f[target], self.v[target] = x[row], f[row], v[row]
        elif self.algorithm == "moead":
            feasible = v <= 0.0
            if np.any(feasible):
                self.ideal = np.minimum(self.ideal, np.min(f[feasible], axis=0))
            for row, neighborhood in enumerate(self.pending["modes"]):
                indices = self.neighbors[row].copy() if neighborhood else np.arange(len(self.x))
                self.rng.shuffle(indices)
                chosen = []
                for index in indices:
                    if len(chosen) >= 2:
                        break
                    old_v = self.v[index]
                    better = ((v[row] <= 0.0 < old_v)
                              or (v[row] > 0.0 and old_v > 0.0 and v[row] < old_v))
                    if v[row] <= 0.0 and old_v <= 0.0:
                        weight = self.weights[index]
                        better = (np.max(weight * np.abs(f[row] - self.ideal))
                                  < np.max(weight * np.abs(self.f[index] - self.ideal)))
                    if better:
                        chosen.append(index)
                for index in chosen:
                    self.x[index], self.f[index], self.v[index] = x[row], f[row], v[row]
        else:
            merged_x, merged_f = np.vstack((self.x, x)), np.vstack((self.f, f))
            merged_v = np.concatenate((self.v, v))
            keep = self._survivors(merged_f, merged_v, self.population_size)
            self.x, self.f, self.v = merged_x[keep], merged_f[keep], merged_v[keep]
        self.pending = None

    def _survivors(self, f, v, count):
        if self.algorithm == "nsga3":
            from pymoo.core.population import Population
            from pymoo.core.problem import Problem
            population = Population.new("F", f, "CV", v[:,None], "bench_index", np.arange(len(f)))
            selected = self.nsga3_survival.do(Problem(n_var=self.initial.shape[1],n_obj=f.shape[1],n_ieq_constr=1),
                population, n_survive=count, random_state=self.rng)
            return selected.get("bench_index").astype(int)
        if self.algorithm == "spea2":
            return self._spea_survivors(f, v, count)
        fronts, _ = FastNonDominatedSort.sort(f, v)
        keep = []
        for front in fronts:
            if len(keep) + len(front) <= count:
                keep.extend(front)
                continue
            remaining = count - len(keep)
            distances = FastNonDominatedSort.calculate_crowding_distance(f, list(front))
            keep.extend(sorted(front, key=lambda i: float(distances[i]), reverse=True)[:remaining])
            break
        return np.asarray(keep, dtype=int)

    @staticmethod
    def _spea_survivors(f, v, count):
        dominance = np.zeros((len(f), len(f)), dtype=bool)
        for index, row in enumerate(f):
            dominance[index] = np.all(row <= f, axis=1) & np.any(row < f, axis=1)
            dominance[index, index] = False
        strength = np.sum(dominance, axis=1).astype(float)
        raw = np.zeros(len(f))
        for index in range(len(f)):
            raw[index] = np.sum(strength[np.where(dominance[:, index])[0]])
        distances = _distances(f, f)
        np.fill_diagonal(distances, np.inf)
        fitness = raw + 1.0 / (np.partition(distances, 0, axis=1)[:, 0] + 2.0) + 1e6 * np.maximum(v, 0.0)
        selected = np.where((fitness < 1.0) & (v <= 1e-10))[0].tolist()
        if len(selected) < count:
            remaining = [i for i in np.argsort(fitness).tolist() if i not in selected]
            return np.asarray(selected + remaining[:count - len(selected)], dtype=int)
        selected = np.asarray(selected, dtype=int)
        while len(selected) > count:
            distances = _distances(f[selected], f[selected])
            np.fill_diagonal(distances, np.inf)
            selected = np.delete(selected, int(np.argmin(np.min(distances, axis=1))))
        return selected


def run_population_reference(seed: int, steps: int, evaluate: Callable, *, algorithm: str,
                             population_size=POPULATION_SIZE):
    kernel, trace = PopulationReferenceKernel(algorithm, seed, population_size), []
    iteration_timings = []
    for _ in range(int(steps)):
        wall, cpu = time.perf_counter(), time.process_time()
        candidates = np.clip(kernel.ask(), 0.0, 1.0)
        feedback = [evaluate(row.copy()) for row in candidates]
        kernel.tell(candidates, np.asarray([row[0] for row in feedback]),
                    np.asarray([row[1] for row in feedback]))
        trace.append({"state": kernel.project()})
        iteration_timings.append({"wall_s": time.perf_counter() - wall,
                                  "cpu_s": time.process_time() - cpu})
    return {"state": kernel.project(), "trace": trace, "iteration_timings": iteration_timings}


def specs(*, population_size=POPULATION_SIZE, steps=6):
    from benchmarks.transparency_core import PairSpec

    if type(population_size) is not int or population_size < 5:
        raise ValueError("population_size must be an integer >=5 (DE/MOEAD need distinct parents)")
    if type(steps) is not int or steps < 2:
        raise ValueError("steps must be an integer >=2 to include normal iteration")
    result = []
    for algorithm in ("nsga2", "nsga3", "spea2", "moead", "de"):
        for problem_name in (("zdt1", "dtlz2") if algorithm == "nsga3" else ("zdt1",)):
            result.append(PairSpec(
                name=f"{algorithm}_{problem_name}",
                make_problem=partial(OfficialPopulationProblem, problem_name),
                make_adapter=partial(make_population_adapter, algorithm=algorithm, population_size=population_size),
                make_pipeline=make_population_pipeline,
                reference=partial(run_population_reference, algorithm=algorithm, population_size=population_size),
                project=project_population, steps=steps, population_size=population_size,
                metric_problem=problem_name,
                metadata={
                    "family": "population", "algorithm": algorithm, "dimension": DIMENSION,
                    "evaluation_budget": population_size * steps,
                    "population_size": population_size,
                    "reference_kind": "independent_pymoo_survival_with_numeric_variation" if algorithm == "nsga3" else "independent_numpy_kernel",
                    "shared_primitives": ["FastNonDominatedSort.sort", "FastNonDominatedSort.calculate_crowding_distance"],
                    "initialization": "SeedSequence([seed,7919]); explicit direct initializer; first committed step evaluates all seeds",
                    "rng_pairing": ("MOEAD config.random_seed=seed; consumes one initializer binding seed"
                        if algorithm == "moead" else
                        "first Solver fork from default_rng(seed); consumes initializer binding seed"
                        + (" then direct GaussianMutation binding seed" if algorithm in {"nsga2", "nsga3", "spea2"} else "")),
                    "variant": ({
                        "nsga2": "rank/crowding tournament; arithmetic crossover; Gaussian mutation",
                        "nsga3": "hyperplane normalization, perpendicular reference lines, occupied niches; independent pymoo survival reference",
                        "spea2": "strength+density k=1, nearest-neighbor truncation; NSGA2 mating; configured archive_size is not separate archive state",
                        "moead": "native DE variation; feasible-first Tchebycheff; neighborhood size5, nr2, batch10",
                        "de": "rand1bin; scalar sum of objectives plus violation penalty; proposal-time baseline including repeated targets",
                    }[algorithm]),
                }))
    return result
