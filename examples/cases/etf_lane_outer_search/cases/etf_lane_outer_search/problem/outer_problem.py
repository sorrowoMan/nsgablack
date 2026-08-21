from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from blackbase.project import CaseRunRequest
from nsgablack.core.base import BlackBoxProblem

try:
    from ..config import EtfLaneOuterSearchConfig
except ImportError:
    from config import EtfLaneOuterSearchConfig


def _clip_int(value: float, low: int, high: int) -> int:
    return int(np.clip(np.round(float(value)), int(low), int(high)))


def _clip_float(value: float, low: float, high: float) -> float:
    return float(np.clip(float(value), float(low), float(high)))


def _toggle(value: float) -> bool:
    return float(value) >= 0.5


class EtfLaneOuterSearchProblem(BlackBoxProblem):
    def __init__(self, cfg: EtfLaneOuterSearchConfig, *, output_dir: str | Path) -> None:
        self.cfg = cfg
        self.output_dir = Path(output_dir).expanduser().resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.evaluation_records: list[dict[str, Any]] = []
        self._cache: dict[str, dict[str, Any]] = {}
        self.best_result: dict[str, Any] | None = None
        self.best_score: float | None = None
        self._case_runtime: Any | None = None
        # [base_alpha, active_alpha, feedback_alpha, max_feedback_weight, rounds,
        #  active_top_k, feedback_top_k, active_min_score, dead_score,
        #  base_blend, active_blend, feedback_blend,
        #  base_rf, active_mlp, active_rf, feedback_mlp, feedback_rf]
        bounds = {
            "x0": [0.2, 2.5],
            "x1": [0.2, 2.5],
            "x2": [0.2, 2.5],
            "x3": [0.10, 0.60],
            "x4": [1.0, 5.0],
            "x5": [8.0, 32.0],
            "x6": [4.0, 24.0],
            "x7": [0.0, 0.05],
            "x8": [0.0, 0.03],
            "x9": [0.0, 1.0],
            "x10": [0.0, 1.0],
            "x11": [0.0, 1.0],
            "x12": [0.0, 1.0],
            "x13": [0.0, 1.0],
            "x14": [0.0, 1.0],
            "x15": [0.0, 1.0],
            "x16": [0.0, 1.0],
        }
        super().__init__(
            name="EtfLaneOuterSearchProblem",
            dimension=17,
            bounds=bounds,
            objectives=(
                "weighted_neg_net_sharpe",
                "weighted_max_drawdown_abs",
                "weighted_turnover_proxy",
                "weighted_neg_rank_ic_mean",
                "weighted_rank_ic_std",
            ),
        )

    def set_case_runtime(self, runtime: Any) -> None:
        self._case_runtime = runtime

    def decode_lane_bundle(self, x: np.ndarray) -> dict[str, Any]:
        arr = np.asarray(x, dtype=float).reshape(self.dimension)
        base_models = ["ridge"]
        if _toggle(arr[12]):
            base_models.append("random_forest")
        active_models = ["ridge"]
        if _toggle(arr[13]):
            active_models.append("mlp_sklearn")
        if _toggle(arr[14]):
            active_models.append("random_forest")
        feedback_models = ["ridge"]
        if _toggle(arr[15]):
            feedback_models.append("mlp_sklearn")
        if _toggle(arr[16]):
            feedback_models.append("random_forest")
        blend = lambda v: "inverse_rmse" if _toggle(v) else "uniform"
        return {
            "active_top_k": _clip_int(arr[5], 8, 32),
            "feedback_top_k": _clip_int(arr[6], 4, 24),
            "active_min_score": _clip_float(arr[7], 0.0, 0.05),
            "dead_score": _clip_float(arr[8], 0.0, 0.03),
            "max_feedback_weight": _clip_float(arr[3], 0.10, 0.60),
            "max_rounds": _clip_int(arr[4], 1, 5),
            "min_round_improvement": 0.0005,
            "min_regime_rows": 12,
            "lanes": (
                {
                    "role": "base",
                    "lane_model": "ridge",
                    "lane_models": tuple(base_models),
                    "blend": blend(arr[9]),
                    "alpha": _clip_float(arr[0], 0.2, 2.5),
                    "enabled": True,
                },
                {
                    "role": "active",
                    "lane_model": "ridge",
                    "lane_models": tuple(active_models),
                    "blend": blend(arr[10]),
                    "alpha": _clip_float(arr[1], 0.2, 2.5),
                    "enabled": True,
                },
                {
                    "role": "feedback",
                    "lane_model": "ridge",
                    "lane_models": tuple(feedback_models),
                    "blend": blend(arr[11]),
                    "alpha": _clip_float(arr[2], 0.2, 2.5),
                    "enabled": True,
                },
            ),
        }

    def evaluate(self, candidate: np.ndarray) -> np.ndarray:
        if self._case_runtime is None:
            raise RuntimeError(
                "etf_lane_outer_search requires an injected Case runtime; "
                "run it through its standard Project entry"
            )
        lane_bundle = self.decode_lane_bundle(candidate)
        bundle_key = hashlib.sha1(json.dumps(lane_bundle, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:12]
        cached = self._cache.get(bundle_key)
        if cached is not None:
            return np.asarray(cached["objectives"], dtype=float)

        label = f"eval_{len(self.evaluation_records):04d}_{bundle_key}"
        eval_dir = self.output_dir / "evaluations" / label
        eval_dir.mkdir(parents=True, exist_ok=True)
        child = self._case_runtime.invoke(
            CaseRunRequest(
                project_name="etf_lane_outer_search",
                stage_name="lane_evaluation",
                case_name="etf_lane_evaluation",
                case_kind="trainer",
                resource_request={
                    "workers": 1,
                    "threads": 1,
                    "gpus": 0,
                    "backend": "local",
                    "device": "cpu",
                    "compute_backend": "auto",
                },
                component_overrides={
                    "config": {
                        "dataset_url": str(self.cfg.dataset_url),
                        "dataset_label": str(self.cfg.dataset_label),
                        "baseline_models": str(self.cfg.baseline_models),
                        "seeds": list(self.cfg.seeds),
                        "suite_id": label,
                        "output_dir": str(eval_dir),
                    },
                    "walkforward": {
                        "min_train_size": int(self.cfg.wf_min_train_size),
                        "test_size": int(self.cfg.wf_test_size),
                        "step_size": int(self.cfg.wf_step_size),
                        "mode": str(self.cfg.wf_mode),
                        "train_window_size": int(self.cfg.wf_train_window_size),
                        "max_folds": int(self.cfg.wf_max_folds),
                        "max_train_panel_rows": int(self.cfg.wf_max_train_panel_rows),
                        "max_test_panel_rows": int(self.cfg.wf_max_test_panel_rows),
                    },
                    "lane_bundle": lane_bundle,
                },
                metadata={"candidate_digest": bundle_key},
            )
        )
        child.raise_for_failure("ETF lane evaluation Case failed")
        payload = dict(child.output or {})
        if str(payload.get("protocol_type", "")) != "blackbase.trainer_result":
            raise TypeError("ETF lane evaluation Case did not return TrainerResult")
        summary = dict(dict(payload.get("report", {}) or {}).get("summary", {}) or {})
        agg = dict(summary.get("aggregate", {}) or {})
        raw_objectives = {
            "neg_net_sharpe": -float(agg.get("composite_net_sharpe_proxy_mean", 0.0)),
            "max_drawdown_abs": float(agg.get("composite_max_drawdown_abs_mean", 1.0)),
            "turnover_proxy": float(agg.get("composite_turnover_proxy_mean", 1.0)),
            "neg_rank_ic_mean": -float(agg.get("composite_rank_ic_mean", 0.0)),
            "rank_ic_std": float(agg.get("composite_rank_ic_std", 1.0)),
        }
        weights = {
            "neg_net_sharpe": float(self.cfg.objective_weight_neg_net_sharpe),
            "max_drawdown_abs": float(self.cfg.objective_weight_max_drawdown_abs),
            "turnover_proxy": float(self.cfg.objective_weight_turnover_proxy),
            "neg_rank_ic_mean": float(self.cfg.objective_weight_neg_rank_ic_mean),
            "rank_ic_std": float(self.cfg.objective_weight_rank_ic_std),
        }
        objectives = np.asarray(
            [weights[name] * raw_objectives[name] for name in weights],
            dtype=float,
        )
        record = {
            "label": label,
            "bundle_key": bundle_key,
            "lane_bundle": lane_bundle,
            "objectives": objectives.tolist(),
            "score": float(np.sum(objectives)),
            "raw_objectives": raw_objectives,
            "objective_weights": weights,
            "aggregate": agg,
            "fold_count": int(summary.get("fold_count", 0)),
            "output_dir": str(summary.get("output_dir", eval_dir)),
            "child_case_run": child.request.identity.as_dict(),
            "status": "ok",
        }
        self.evaluation_records.append(record)
        self._cache[bundle_key] = record
        score = float(record["score"])
        if self.best_score is None or score < float(self.best_score):
            self.best_score = score
            self.best_result = dict(record)
        return objectives

    def evaluate_constraints(self, candidate: np.ndarray) -> np.ndarray:
        lane_bundle = self.decode_lane_bundle(candidate)
        active_top = int(lane_bundle.get("active_top_k", 0))
        feedback_top = int(lane_bundle.get("feedback_top_k", 0))
        return np.asarray([max(0.0, float(feedback_top - active_top))], dtype=float)


__all__ = ["EtfLaneOuterSearchProblem"]
