from __future__ import annotations

from typing import Any, Mapping

import numpy as np

from blackbase.resources import ResourceContext
from blackbase.types import Feedback, TrainerResult, UnknownState
from mlblack.integrations.etf_temporal_forecast import (
    DEFAULT_DATASET_URL,
    run_etf_walkforward_multi_seed,
)


class EtfLaneEvaluationCase:
    """Evaluate one lane bundle inside the ML semantic boundary."""

    def __init__(self, *, config, walkforward, lane_bundle, resource_context=None):
        self.config = dict(config)
        self.walkforward = dict(walkforward)
        self.lane_bundle = dict(lane_bundle)
        self.resource_context = ResourceContext.from_mapping(resource_context)

    def set_resource_context(self, resource_context) -> None:
        self.resource_context = ResourceContext.from_mapping(resource_context)

    def fit(self) -> TrainerResult:
        cfg = {
            "dataset_label": str(
                self.config.get("dataset_label", "multi_etf_returns_momodel_kaggle")
            ),
            "baseline_models": str(self.config.get("baseline_models", "ridge")),
        }
        dataset_url = str(self.config.get("dataset_url", "") or "").strip()
        cfg["dataset_url"] = dataset_url or str(DEFAULT_DATASET_URL)
        result = run_etf_walkforward_multi_seed(
            cfg=cfg,
            walkforward=self.walkforward,
            seeds=tuple(int(seed) for seed in self.config.get("seeds", (42,))),
            suite_id=str(self.config.get("suite_id", "etf_lane_evaluation")),
            output_dir=str(self.config.get("output_dir", "runs/etf_lane_evaluation")),
            potential_params_override=self.lane_bundle,
            resource_context=self.resource_context,
        )
        aggregate = dict(dict(result.summary).get("aggregate", {}) or {})
        objectives = np.asarray(
            [
                -float(aggregate.get("composite_net_sharpe_proxy_mean", 0.0)),
                float(aggregate.get("composite_max_drawdown_abs_mean", 1.0)),
                float(aggregate.get("composite_turnover_proxy_mean", 1.0)),
                -float(aggregate.get("composite_rank_ic_mean", 0.0)),
                float(aggregate.get("composite_rank_ic_std", 1.0)),
            ],
            dtype=float,
        )
        metrics = {
            "net_sharpe_proxy": -float(objectives[0]),
            "max_drawdown_abs": float(objectives[1]),
            "turnover_proxy": float(objectives[2]),
            "rank_ic_mean": -float(objectives[3]),
            "rank_ic_std": float(objectives[4]),
        }
        feedback = Feedback(
            objectives=objectives,
            loss=float(np.sum(objectives)),
            metrics=metrics,
        )
        return TrainerResult(
            best_model={
                "kind": "etf_lane_evaluation_procedure",
                "lane_bundle": self.lane_bundle,
            },
            best_state=UnknownState(
                values=np.zeros(1, dtype=float),
                metadata={"lane_bundle": self.lane_bundle},
            ),
            best_objectives=objectives,
            best_feedback=feedback,
            report={
                "summary": {
                    "aggregate": aggregate,
                    "fold_count": int(dict(result.summary).get("fold_count", 0)),
                    "output_dir": str(result.output_dir),
                    "resource_context": self.resource_context.as_dict(),
                }
            },
            metadata={"framework": "mlblack", "semantic_role": "etf_lane_evaluation"},
        )


__all__ = ["EtfLaneEvaluationCase"]
