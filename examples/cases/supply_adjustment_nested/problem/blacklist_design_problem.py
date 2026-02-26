from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.solver import BlackBoxSolverNSGAII

from evaluation import ProductionInnerEvalConfig, ProductionInnerEvaluationModel
from problem.supply_event_shift_problem import SupplyEventShiftProblem


@dataclass
class BlacklistEvalConfig:
    outer_pop_size: int = 16
    outer_generations: int = 3
    inner_mode: str = "full"
    inner_trials: int = 1
    hybrid_top_quantile: float = 0.85
    hybrid_explore_prob: float = 0.02
    hybrid_random_refine_ratio: float = 0.05
    hybrid_warmup: int = 5
    hybrid_refine_pop_size: int = 8
    hybrid_refine_generations: int = 1
    quality_gap_soft_limit: float = 0.08
    max_moved_events: int | None = 200
    parallel: bool = False
    parallel_backend: str = "thread"
    parallel_workers: int = 1
    parallel_chunk_size: int | None = None
    parallel_strict: bool = False
    parallel_thread_bias_isolation: str = "off"


class BlacklistDesignProblem(BlackBoxProblem):
    """L0 problem: optimize material blacklist for L1/L2 runtime-quality tradeoff."""

    context_requires = ()
    context_provides = ("blacklist_eval_metrics",)
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "L0 optimize blacklist mask; evaluate with reduced-budget L1/L2 nested run.",
    )

    def __init__(
        self,
        *,
        base_supply: np.ndarray,
        bom_matrix: np.ndarray,
        material_ids: np.ndarray,
        production_case_dir: Path,
        baseline_schedule: np.ndarray | None,
        strict_blacklist_ids: list[int],
        candidate_material_ids: list[int],
        eval_cfg: BlacklistEvalConfig,
        seed: int = 42,
        decision_sink: Callable[..., None] | None = None,
    ) -> None:
        self.base_supply = np.asarray(base_supply, dtype=float)
        self.bom_matrix = np.asarray(bom_matrix, dtype=float)
        self.material_ids = np.asarray(material_ids)
        self.production_case_dir = Path(production_case_dir).resolve()
        self.baseline_schedule = None if baseline_schedule is None else np.asarray(baseline_schedule, dtype=float)
        self.eval_cfg = eval_cfg
        self.rng = np.random.default_rng(int(seed))
        self.decision_sink = decision_sink

        self.strict_blacklist_ids = sorted({int(x) for x in strict_blacklist_ids})
        strict_set = set(self.strict_blacklist_ids)
        self.candidate_ids = [int(x) for x in candidate_material_ids if int(x) not in strict_set]
        self._strict_mask = np.zeros(self.base_supply.shape[0], dtype=bool)
        for mid in self.strict_blacklist_ids:
            if 1 <= mid <= self._strict_mask.size:
                self._strict_mask[mid - 1] = True

        self._candidate_set = set(self.candidate_ids)
        self._relation = self._build_relation_graph(np.asarray(self.bom_matrix > 0.0, dtype=bool))

        bounds = {f"x{i}": [0.0, 1.0] for i in range(len(self.candidate_ids))}
        super().__init__(
            name="BlacklistDesignProblem",
            dimension=len(self.candidate_ids),
            bounds=bounds,
            objectives=["min_runtime", "min_quality_gap", "min_blacklist_size"],
        )

        self._cache: dict[tuple[int, ...], tuple[np.ndarray, dict]] = {}
        self._baseline_output: float = self._compute_baseline_output()

    @staticmethod
    def _build_relation_graph(bom_bool: np.ndarray) -> list[set[int]]:
        machines, materials = bom_bool.shape
        adj: list[set[int]] = [set() for _ in range(materials)]
        for j in range(machines):
            req = np.where(bom_bool[j])[0]
            if req.size <= 1:
                continue
            # Undirected clique per machine requirement set (small scale: 156 materials).
            for a in req:
                for b in req:
                    if int(a) != int(b):
                        adj[int(a)].add(int(b))
        return adj

    def _emit(self, **kwargs):
        sink = self.decision_sink
        if not callable(sink):
            return
        try:
            sink(**kwargs)
        except Exception:
            return

    def _decode_blacklist_ids(self, x: np.ndarray) -> list[int]:
        total_m = self.base_supply.shape[0]
        blacklist_mask = np.ones(total_m, dtype=bool)  # default: all blacklisted
        if self.dimension == 0:
            for mid in self.strict_blacklist_ids:
                if 1 <= mid <= total_m:
                    blacklist_mask[mid - 1] = True
            return (np.where(blacklist_mask)[0] + 1).astype(int).tolist()

        vec = np.asarray(x, dtype=float).reshape(self.dimension)
        selected_black = {self.candidate_ids[i] for i, v in enumerate(vec) if float(v) >= 0.5}
        whitelist = {mid for mid in self.candidate_ids if mid not in selected_black}

        # One-hop closure only (non-chain):
        # If material a is selected as active (not blacklisted), then its direct
        # relation materials are also active, but this rule does not recurse.
        anchor_whitelist = set(whitelist)
        for mid in anchor_whitelist:
            m0 = mid - 1
            neighbors = self._relation[m0]
            for n in neighbors:
                nid = n + 1
                if nid in self._candidate_set:
                    whitelist.add(nid)

        # Apply whitelist on candidate domain.
        for mid in whitelist:
            if 1 <= mid <= total_m:
                blacklist_mask[mid - 1] = False
        # Strict mask hard override (always black).
        blacklist_mask[self._strict_mask] = True
        return (np.where(blacklist_mask)[0] + 1).astype(int).tolist()

    def _build_inner_model(self) -> ProductionInnerEvaluationModel:
        cfg = ProductionInnerEvalConfig(
            mode=str(self.eval_cfg.inner_mode),
            inner_trials=int(self.eval_cfg.inner_trials),
            hybrid_top_quantile=float(self.eval_cfg.hybrid_top_quantile),
            hybrid_explore_prob=float(self.eval_cfg.hybrid_explore_prob),
            hybrid_random_refine_ratio=float(self.eval_cfg.hybrid_random_refine_ratio),
            hybrid_warmup=int(self.eval_cfg.hybrid_warmup),
            hybrid_refine_pop_size=int(self.eval_cfg.hybrid_refine_pop_size),
            hybrid_refine_generations=int(self.eval_cfg.hybrid_refine_generations),
            parallel=bool(self.eval_cfg.parallel),
            parallel_backend=str(self.eval_cfg.parallel_backend),
            parallel_workers=int(self.eval_cfg.parallel_workers),
            parallel_chunk_size=self.eval_cfg.parallel_chunk_size,
            parallel_strict=bool(self.eval_cfg.parallel_strict),
            parallel_thread_bias_isolation=str(self.eval_cfg.parallel_thread_bias_isolation),
        )
        return ProductionInnerEvaluationModel(
            bom_matrix=self.bom_matrix,
            base_supply=self.base_supply,
            production_case_dir=self.production_case_dir,
            baseline_schedule=self.baseline_schedule,
            cfg=cfg,
        )

    def _run_l1(self, blacklist_ids: list[int]) -> tuple[float, float]:
        t0 = time.perf_counter()
        inner = self._build_inner_model()
        problem = SupplyEventShiftProblem(
            base_supply=self.base_supply,
            inner_model=inner,
            material_ids=self.material_ids,
            material_blacklist=blacklist_ids,
            max_moved_events=self.eval_cfg.max_moved_events,
        )
        solver = BlackBoxSolverNSGAII(
            problem,
            pop_size=int(self.eval_cfg.outer_pop_size),
            max_generations=int(self.eval_cfg.outer_generations),
        )
        solver.run()
        best = getattr(solver, "best_objective", None)
        if best is None:
            best = np.inf
        runtime = float(max(0.0, time.perf_counter() - t0))
        best_output = float(-best) if np.isfinite(best) else 0.0
        return runtime, best_output

    def _compute_baseline_output(self) -> float:
        print("[l0] baseline_run start (strict blacklist only)")
        runtime, output = self._run_l1(self.strict_blacklist_ids)
        print(f"[l0] baseline_run done runtime={runtime:.2f}s best_output={output:.2f}")
        self._emit(
            event_type="blacklist_l0",
            component="outer.blacklist",
            decision="baseline_eval",
            reason_code="strict_only",
            inputs={"strict_blacklist_count": len(self.strict_blacklist_ids)},
            outcome={"runtime_sec": float(runtime), "best_output": float(output)},
        )
        return float(max(output, 1e-9))

    def evaluate(self, x: np.ndarray) -> np.ndarray:
        blacklist = self._decode_blacklist_ids(x)
        key = tuple(blacklist)
        hit = self._cache.get(key)
        if hit is not None:
            return np.array(hit[0], dtype=float)

        runtime, best_output = self._run_l1(blacklist)
        quality_gap = max(0.0, (self._baseline_output - best_output) / max(self._baseline_output, 1e-9))
        size_ratio = float(len(blacklist)) / max(1.0, float(self.base_supply.shape[0]))
        obj = np.array([runtime, quality_gap, size_ratio], dtype=float)
        self._cache[key] = (obj, {"runtime": runtime, "best_output": best_output, "quality_gap": quality_gap})

        self._emit(
            event_type="blacklist_l0",
            component="outer.blacklist",
            decision="evaluate_mask",
            reason_code="nested_l1l2",
            inputs={
                "blacklist_count": int(len(blacklist)),
                "candidate_dim": int(self.dimension),
            },
            thresholds={"quality_gap_soft_limit": float(self.eval_cfg.quality_gap_soft_limit)},
            outcome={
                "runtime_sec": float(runtime),
                "best_output": float(best_output),
                "quality_gap": float(quality_gap),
                "size_ratio": float(size_ratio),
            },
        )
        return obj

    def evaluate_constraints(self, x: np.ndarray) -> np.ndarray:
        blacklist = self._decode_blacklist_ids(x)
        key = tuple(blacklist)
        hit = self._cache.get(key)
        if hit is None:
            _ = self.evaluate(x)
            hit = self._cache.get(key)
        quality_gap = float(hit[1]["quality_gap"]) if hit is not None else 1.0
        v = quality_gap - float(self.eval_cfg.quality_gap_soft_limit)
        return np.array([v], dtype=float)

    def decode_mask(self, x: np.ndarray) -> np.ndarray:
        ids = set(self._decode_blacklist_ids(x))
        mask = np.zeros(self.base_supply.shape[0], dtype=bool)
        for mid in ids:
            if 1 <= mid <= mask.size:
                mask[mid - 1] = True
        return mask
