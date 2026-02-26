from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Optional, Any

import numpy as np


@dataclass
class ProductionInnerEvalConfig:
    # integrated: residual decomposition (fast, constrained)
    # fast: lightweight proxy
    # hybrid: residual prefilter + selective full integrated refine
    # full: always run full integrated inner solver
    mode: str = "hybrid"

    max_active_machines_per_day: int = 8
    max_production_per_machine: float = 3000.0

    # residual budget
    inner_trials: int = 6

    # hybrid policy
    hybrid_top_quantile: float = 0.85
    hybrid_explore_prob: float = 0.05
    # Fixed random refine sample ratio for non-top candidates (anti-miss guard).
    hybrid_random_refine_ratio: float = 0.1
    hybrid_warmup: int = 20
    hybrid_refine_pop_size: int = 24
    hybrid_refine_generations: int = 3
    # Optional RF uncertainty gate for hybrid refine.
    hybrid_rf_enable: bool = True
    hybrid_rf_uncertainty_quantile: float = 0.90
    hybrid_rf_min_samples: int = 40
    hybrid_rf_retrain_interval: int = 10
    hybrid_rf_max_train_samples: int = 2000
    hybrid_rf_n_estimators: int = 96
    # Inner full-solver parallel options.
    parallel: bool = False
    parallel_backend: str = "thread"
    parallel_workers: int = 1
    parallel_chunk_size: int | None = None
    parallel_strict: bool = False
    parallel_thread_bias_isolation: str = "off"


class ProductionInnerEvaluationModel:
    """Inner evaluation model for adjusted supply tables.

    Integrated mode uses residual decomposition: P = B + A.
    Hybrid mode adds selective refinement with full production inner solver.
    """

    context_requires = ()
    context_provides = ("inner_metrics",)
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Inner evaluation supports integrated residual, fast proxy, and hybrid two-stage refine.",
    )

    def __init__(
        self,
        *,
        bom_matrix: np.ndarray,
        base_supply: np.ndarray,
        production_case_dir: Path,
        baseline_schedule: Optional[np.ndarray] = None,
        cfg: ProductionInnerEvalConfig | None = None,
    ) -> None:
        self.cfg = cfg or ProductionInnerEvalConfig()
        self.bom_matrix = np.asarray(bom_matrix, dtype=float)
        self.base_supply = np.asarray(base_supply, dtype=float)
        self.production_case_dir = Path(production_case_dir).resolve()

        self.machines, self.materials = self.bom_matrix.shape
        self.days = int(self.base_supply.shape[1])
        self.req_indices = [np.where(self.bom_matrix[m] > 0.0)[0] for m in range(self.machines)]

        if baseline_schedule is None:
            self.baseline_schedule = np.zeros((self.machines, self.days), dtype=float)
        else:
            b = np.asarray(baseline_schedule, dtype=float)
            if b.shape != (self.machines, self.days):
                raise ValueError(
                    f"baseline schedule shape mismatch: {b.shape}, expected ({self.machines}, {self.days})"
                )
            self.baseline_schedule = np.maximum(0.0, b)

        self.baseline_active = np.sum(self.baseline_schedule > 1e-9, axis=0)
        self.baseline_total_output = float(np.sum(self.baseline_schedule))
        self.base_stock_after = self._compute_stock_after_baseline()

        self._cache: Dict[str, Dict[str, float]] = {}
        self._refine_cache: Dict[str, Dict[str, float]] = {}
        self._residual_history: list[float] = []
        self._feature_history: list[np.ndarray] = []
        self._rf_uncertainty_history: list[float] = []
        self._rng = np.random.default_rng(42)
        self._eval_count: int = 0
        self._refine_count: int = 0
        self._rf_model = None
        self._rf_last_train_count: int = 0
        self._rf_enabled: bool = bool(getattr(self.cfg, "hybrid_rf_enable", True))
        self._logged_full_parallel_cfg: bool = False
        self.decision_sink: Optional[Callable[..., Any]] = None

    def evaluate_adjusted_supply(self, adjusted_supply: np.ndarray) -> Dict[str, float]:
        supply = np.asarray(adjusted_supply, dtype=float)
        if supply.ndim != 2:
            raise ValueError("adjusted_supply must be 2D (materials, days)")
        if supply.shape != (self.materials, self.days):
            raise ValueError(
                f"supply shape mismatch: got {supply.shape}, expected ({self.materials}, {self.days})"
            )

        key = self._hash_supply(supply)
        hit = self._cache.get(key)
        if hit is not None:
            return dict(hit)

        mode = str(self.cfg.mode or "hybrid").strip().lower()
        if mode == "full":
            metrics = self._evaluate_full_integrated(supply)
            metrics["inner_stage"] = "full"
        elif mode == "integrated":
            metrics = self._evaluate_integrated_residual(supply)
            metrics["inner_stage"] = "residual"
        elif mode == "fast":
            metrics = self._evaluate_fast_proxy(supply)
            metrics["inner_stage"] = "fast"
        else:
            metrics = self._evaluate_hybrid(supply, key)

        self._cache[key] = dict(metrics)
        return metrics

    def _evaluate_hybrid(self, supply: np.ndarray, key: str) -> Dict[str, float]:
        residual = self._evaluate_integrated_residual(supply)
        residual_score = float(residual.get("total_output", 0.0))
        feature = self._build_hybrid_feature(supply)

        self._eval_count += 1
        self._residual_history.append(residual_score)
        self._feature_history.append(feature)
        self._maybe_train_rf()
        rf_uncertainty = self._estimate_rf_uncertainty(feature)
        should_refine, reason, rf_threshold = self._should_refine(
            residual_score,
            key,
            rf_uncertainty=rf_uncertainty,
        )
        if rf_uncertainty is not None and np.isfinite(rf_uncertainty):
            self._rf_uncertainty_history.append(float(rf_uncertainty))
        if should_refine:
            self._refine_count += 1
            refined = self._refine_cache.get(key)
            if refined is None:
                refined = self._evaluate_full_integrated(supply)
                self._refine_cache[key] = dict(refined)
            merged = dict(refined)
            merged["inner_stage"] = "hybrid_refined"
            merged["inner_refine_reason"] = reason
            merged["residual_total_output"] = residual_score
            self._emit_decision(
                candidate_key=key,
                stage="hybrid_refined",
                reason=reason,
                residual_score=residual_score,
                output=float(merged.get("total_output", 0.0)),
                rf_uncertainty=rf_uncertainty,
                rf_threshold=rf_threshold,
            )
            return merged

        out = dict(residual)
        out["inner_stage"] = "hybrid_residual"
        out["inner_refine_reason"] = reason
        self._emit_decision(
            candidate_key=key,
            stage="hybrid_residual",
            reason=reason,
            residual_score=residual_score,
            output=float(out.get("total_output", 0.0)),
            rf_uncertainty=rf_uncertainty,
            rf_threshold=rf_threshold,
        )
        return out

    def _should_refine(
        self,
        residual_score: float,
        key: str,
        *,
        rf_uncertainty: Optional[float] = None,
    ) -> tuple[bool, str, Optional[float]]:
        n = len(self._residual_history)
        warmup = max(1, int(self.cfg.hybrid_warmup))

        if n <= warmup:
            return True, "warmup", None

        q = float(np.clip(self.cfg.hybrid_top_quantile, 0.0, 1.0))
        threshold = float(np.quantile(np.asarray(self._residual_history, dtype=float), q))
        if residual_score >= threshold:
            return True, f"top_quantile>={q:.2f}", None

        # Fixed-ratio guard for non-top candidates to reduce false negatives.
        ratio = float(np.clip(self.cfg.hybrid_random_refine_ratio, 0.0, 1.0))
        if ratio > 0.0 and self._ratio_sample_hit(key, ratio):
            return True, f"random_ratio<={ratio:.2f}", None

        # RF uncertainty gate: uncertain candidates get an extra refine chance.
        if (
            self._rf_enabled
            and rf_uncertainty is not None
            and np.isfinite(rf_uncertainty)
            and len(self._rf_uncertainty_history) >= max(10, int(self.cfg.hybrid_rf_min_samples // 2))
        ):
            uq = float(np.clip(self.cfg.hybrid_rf_uncertainty_quantile, 0.0, 1.0))
            u_threshold = float(np.quantile(np.asarray(self._rf_uncertainty_history, dtype=float), uq))
            if float(rf_uncertainty) >= float(u_threshold):
                return True, f"rf_uncertainty>={uq:.2f}", u_threshold

        # Optional stochastic exploration fallback.
        p = float(np.clip(self.cfg.hybrid_explore_prob, 0.0, 1.0))
        if self._rng.random() < p:
            return True, f"explore_prob<{p:.2f}", None

        return False, "residual_only", None

    @staticmethod
    def _ratio_sample_hit(key: str, ratio: float) -> bool:
        bucket = hash("ratio:" + key) % 100000
        score = float(bucket) / 100000.0
        return score < float(ratio)

    def _emit_decision(
        self,
        *,
        candidate_key: str,
        stage: str,
        reason: str,
        residual_score: float,
        output: float,
        rf_uncertainty: Optional[float] = None,
        rf_threshold: Optional[float] = None,
    ) -> None:
        sink = self.decision_sink
        if not callable(sink):
            return
        try:
            sink(
                event_type="inner_eval",
                component="inner.hybrid",
                decision=str(stage),
                reason_code=str(reason),
                inputs={
                    "candidate_key": str(candidate_key)[:16],
                    "eval_count": int(self._eval_count),
                    "refine_count": int(self._refine_count),
                },
                thresholds={
                    "top_quantile": float(self.cfg.hybrid_top_quantile),
                    "random_refine_ratio": float(self.cfg.hybrid_random_refine_ratio),
                    "rf_uncertainty_quantile": float(self.cfg.hybrid_rf_uncertainty_quantile),
                    "rf_uncertainty_threshold": (
                        float(rf_threshold) if rf_threshold is not None and np.isfinite(rf_threshold) else None
                    ),
                },
                evidence={
                    "residual_total_output": float(residual_score),
                    "rf_uncertainty": (
                        float(rf_uncertainty) if rf_uncertainty is not None and np.isfinite(rf_uncertainty) else None
                    ),
                },
                outcome={
                    "total_output": float(output),
                },
            )
        except Exception:
            return

    def _build_hybrid_feature(self, supply: np.ndarray) -> np.ndarray:
        base = self.base_supply
        delta = np.asarray(supply, dtype=float) - base
        abs_delta = np.abs(delta)
        lead_mass = float(np.sum(abs_delta))
        pos_mass = float(np.sum(np.maximum(delta, 0.0)))
        neg_mass = float(np.sum(np.maximum(-delta, 0.0)))
        changed = int(np.sum(abs_delta > 1e-9))
        by_day = np.sum(abs_delta, axis=0)
        by_mat = np.sum(abs_delta, axis=1)
        feature = np.array(
            [
                float(np.sum(supply)),
                float(np.mean(supply)),
                float(np.std(supply)),
                lead_mass,
                pos_mass,
                neg_mass,
                float(changed),
                float(np.max(by_day) if by_day.size else 0.0),
                float(np.mean(by_day) if by_day.size else 0.0),
                float(np.std(by_day) if by_day.size else 0.0),
                float(np.max(by_mat) if by_mat.size else 0.0),
                float(np.mean(by_mat) if by_mat.size else 0.0),
                float(np.std(by_mat) if by_mat.size else 0.0),
            ],
            dtype=float,
        )
        feature[~np.isfinite(feature)] = 0.0
        return feature

    def _maybe_train_rf(self) -> None:
        if not self._rf_enabled:
            return
        n = len(self._feature_history)
        min_samples = max(10, int(self.cfg.hybrid_rf_min_samples))
        if n < min_samples:
            return
        interval = max(1, int(self.cfg.hybrid_rf_retrain_interval))
        if self._rf_model is not None and (n - self._rf_last_train_count) < interval:
            return

        try:
            from sklearn.ensemble import RandomForestRegressor
        except Exception:
            self._rf_enabled = False
            return

        max_n = max(min_samples, int(self.cfg.hybrid_rf_max_train_samples))
        start = max(0, n - max_n)
        x = np.asarray(self._feature_history[start:n], dtype=float)
        y = np.asarray(self._residual_history[start:n], dtype=float)
        if x.ndim != 2 or y.ndim != 1 or x.shape[0] != y.shape[0] or x.shape[0] < min_samples:
            return

        try:
            rf = RandomForestRegressor(
                n_estimators=max(16, int(self.cfg.hybrid_rf_n_estimators)),
                random_state=42,
                n_jobs=1,
            )
            rf.fit(x, y)
            self._rf_model = rf
            self._rf_last_train_count = n
        except Exception:
            return

    def _estimate_rf_uncertainty(self, feature: np.ndarray) -> Optional[float]:
        rf = self._rf_model
        if rf is None:
            return None
        estimators = getattr(rf, "estimators_", None)
        if not estimators:
            return None
        x = np.asarray(feature, dtype=float).reshape(1, -1)
        preds = []
        for est in estimators:
            try:
                preds.append(float(est.predict(x)[0]))
            except Exception:
                continue
        if len(preds) < 2:
            return None
        std = float(np.std(np.asarray(preds, dtype=float)))
        if not np.isfinite(std):
            return None
        return std

    def _compute_stock_after_baseline(self) -> np.ndarray:
        stock = np.zeros(self.materials, dtype=float)
        after = np.zeros((self.materials, self.days), dtype=float)
        for d in range(self.days):
            stock += self.base_supply[:, d]
            consume = np.zeros(self.materials, dtype=float)
            for m in range(self.machines):
                q = float(self.baseline_schedule[m, d])
                if q <= 1e-9:
                    continue
                req = self.bom_matrix[m]
                consume += req * q
            stock = np.maximum(0.0, stock - consume)
            after[:, d] = stock
        return after

    def _evaluate_integrated_residual(self, adjusted_supply: np.ndarray) -> Dict[str, float]:
        delta_supply = np.asarray(adjusted_supply, dtype=float) - self.base_supply
        trials = max(1, int(self.cfg.inner_trials))

        residual_slots = np.maximum(0, int(self.cfg.max_active_machines_per_day) - self.baseline_active)
        residual_prod_cap = np.maximum(0.0, float(self.cfg.max_production_per_machine) - self.baseline_schedule)

        best_delta_output = -np.inf
        for t in range(trials):
            carry = np.zeros(self.materials, dtype=float)
            delta_output = 0.0

            for d in range(self.days):
                carry += delta_supply[:, d]
                available = np.maximum(0.0, self.base_stock_after[:, d] + carry)

                slot_budget = int(residual_slots[d])
                if slot_budget <= 0:
                    carry = available - self.base_stock_after[:, d]
                    continue

                candidates = []
                for m in range(self.machines):
                    cap = float(residual_prod_cap[m, d])
                    if cap <= 1e-9:
                        continue
                    req_idx = self.req_indices[m]
                    if req_idx.size == 0:
                        continue
                    feasible = float(np.min(available[req_idx]))
                    prod = min(feasible, cap)
                    if prod <= 1e-9:
                        continue
                    score = prod + (0.0 if t == 0 else float(self._rng.uniform(0.0, 1e-3)))
                    candidates.append((score, m, prod, req_idx))

                if not candidates:
                    carry = available - self.base_stock_after[:, d]
                    continue

                candidates.sort(key=lambda x: x[0], reverse=True)
                chosen = candidates[:slot_budget]

                day_consume = np.zeros(self.materials, dtype=float)
                for _score, _m, prod, req_idx in chosen:
                    day_consume[req_idx] += prod
                    delta_output += float(prod)

                available_after = np.maximum(0.0, available - day_consume)
                carry = available_after - self.base_stock_after[:, d]

            if delta_output > best_delta_output:
                best_delta_output = delta_output

        if not np.isfinite(best_delta_output):
            best_delta_output = 0.0
        return {
            "total_output": float(self.baseline_total_output + best_delta_output),
            "delta_output": float(best_delta_output),
        }

    def _evaluate_full_integrated(self, adjusted_supply: np.ndarray) -> Dict[str, float]:
        """Full inner solve using production scheduling multi-agent solver (small budget)."""
        import sys

        if str(self.production_case_dir) not in sys.path:
            sys.path.insert(0, str(self.production_case_dir))

        from refactor_data import ProductionData
        from refactor_problem import ProductionConstraints, ProductionSchedulingProblem
        from working_integrated_optimizer import build_multi_agent_solver

        data = ProductionData(
            machines=int(self.machines),
            materials=int(self.materials),
            days=int(self.days),
            bom_matrix=np.asarray(self.bom_matrix > 0.0, dtype=bool),
            supply_matrix=np.asarray(adjusted_supply, dtype=float),
            machine_weights=np.ones(int(self.machines), dtype=float),
            bom_path=None,
            supply_path=None,
        )

        constraints = ProductionConstraints(
            max_machines_per_day=int(self.cfg.max_active_machines_per_day),
            min_machines_per_day=5,
            min_production_per_machine=50,
            max_production_per_machine=int(self.cfg.max_production_per_machine),
            shortage_unit_penalty=1.0,
            include_penalty_objective=True,
            penalty_objective_scale=0.001,
        )
        problem = ProductionSchedulingProblem(data=data, constraints=constraints)

        class _Args:
            pass

        a = _Args()
        a.material_cap_ratio = 2.0
        a.daily_floor_ratio = 0.7
        a.donor_keep_ratio = 0.6
        a.daily_cap_ratio = 1.0
        a.reserve_ratio = 0.2
        a.coverage_bonus = 0.3
        a.budget_mode = "average"
        a.smooth_strength = 0.8
        a.smooth_passes = 1
        a.no_pipeline = False
        a.no_bias = False
        a.coverage_reward = 0.03
        a.smoothness_penalty = 0.01
        a.variance_penalty = 0.03
        a.pop_size = int(max(8, self.cfg.hybrid_refine_pop_size))
        a.explorer_adapter = "moead"
        a.exploiter_adapter = "vns"
        a.seed = 42
        a.moead_pop_size = int(max(16, self.cfg.hybrid_refine_pop_size))
        a.moead_neighborhood = 10
        a.moead_nr = 2
        a.moead_delta = 0.9
        a.vns_batch_size = int(max(8, self.cfg.hybrid_refine_pop_size // 2))
        a.vns_k_max = 3
        a.vns_base_sigma = 0.2
        a.adapt_interval = 8
        a.comm_interval = 5
        a.generations = int(max(1, self.cfg.hybrid_refine_generations))
        a.allow_infeasible_update = False
        a.parallel = bool(getattr(self.cfg, "parallel", False))
        a.parallel_backend = str(getattr(self.cfg, "parallel_backend", "thread"))
        a.parallel_workers = int(max(1, int(getattr(self.cfg, "parallel_workers", 1))))
        a.parallel_chunk_size = getattr(self.cfg, "parallel_chunk_size", None)
        a.parallel_verbose = False
        a.parallel_no_precheck = False
        a.parallel_strict = bool(getattr(self.cfg, "parallel_strict", False))
        a.parallel_thread_bias_isolation = str(getattr(self.cfg, "parallel_thread_bias_isolation", "off"))
        if not self._logged_full_parallel_cfg:
            print(
                "[l2] inner_full_parallel "
                f"enabled={a.parallel} backend={a.parallel_backend} workers={a.parallel_workers} "
                f"chunk_size={a.parallel_chunk_size} strict={a.parallel_strict} "
                f"thread_bias_isolation={a.parallel_thread_bias_isolation}"
            )
            self._logged_full_parallel_cfg = True
        a.no_run_logs = True
        a.no_bias_md = True
        a.no_profile = True
        a.no_decision_trace = True
        a.decision_trace_flush_every = 10
        a.log_every = 10
        a.run_dir = None
        a.run_id = None
        a.report_every = 100
        a.no_export = True
        a.pareto_export = 0
        a.pareto_export_mode = "crowding"
        a.bom = None
        a.supply = None
        a.machines = int(self.machines)
        a.materials = int(self.materials)
        a.days = int(self.days)
        a.max_machines = int(self.cfg.max_active_machines_per_day)
        a.min_machines = 5
        a.min_prod = 50
        a.max_prod = int(self.cfg.max_production_per_machine)
        a.shortage_unit_penalty = 1.0
        a.penalty_objective = True
        a.penalty_scale = 0.001

        solver = build_multi_agent_solver(problem, a)
        solver.set_max_steps(int(max(1, self.cfg.hybrid_refine_generations)))
        solver.run()

        x = getattr(solver, "best_x", None)
        if x is None:
            try:
                pop = np.asarray(getattr(solver, "population", None), dtype=float)
                obj = np.asarray(getattr(solver, "objectives", None), dtype=float)
                if pop.ndim == 2 and pop.shape[0] > 0:
                    if obj.ndim == 2 and obj.shape[0] == pop.shape[0]:
                        idx = int(np.argmin(np.sum(obj, axis=1)))
                    else:
                        idx = 0
                    x = pop[idx]
            except Exception:
                x = None

        if x is None:
            return {"total_output": 0.0, "refine_failed": 1.0}

        schedule = problem.decode_schedule(np.asarray(x, dtype=float))
        total_output = float(np.sum(schedule))
        return {"total_output": total_output, "refine_failed": 0.0}

    def _evaluate_fast_proxy(self, adjusted_supply: np.ndarray) -> Dict[str, float]:
        stock = np.zeros(self.materials, dtype=float)
        total_output = 0.0

        for day in range(adjusted_supply.shape[1]):
            stock += adjusted_supply[:, day]
            feasible_outputs = np.zeros(self.machines, dtype=float)
            for m in range(self.machines):
                req_idx = self.req_indices[m]
                if req_idx.size == 0:
                    continue
                feasible_outputs[m] = float(np.min(stock[req_idx]))

            order = np.argsort(-feasible_outputs)
            active = 0
            for m in order:
                if active >= int(self.cfg.max_active_machines_per_day):
                    break
                req_idx = self.req_indices[m]
                if req_idx.size == 0:
                    continue
                feasible = float(np.min(stock[req_idx]))
                if feasible <= 1e-9:
                    continue
                prod = min(feasible, float(self.cfg.max_production_per_machine))
                if prod <= 1e-9:
                    continue
                active += 1
                stock[req_idx] -= prod
                stock = np.maximum(stock, 0.0)
                total_output += float(prod)

        return {"total_output": float(total_output)}

    @staticmethod
    def _hash_supply(supply: np.ndarray) -> str:
        arr = np.asarray(supply, dtype=np.float32)
        return f"{arr.shape}:{hash(arr.tobytes())}"
