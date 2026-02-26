"""
Bias effectiveness analytics utilities.

This module is optional; plotting requires matplotlib.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import logging

import numpy as np
try:
    import pandas as pd
except Exception:  # optional dependency
    pd = None

try:
    import matplotlib.pyplot as plt
except Exception:  # optional dependency
    plt = None

from ..core.base import AlgorithmicBias, DomainBias


class MetricType(Enum):
    CONVERGENCE_SPEED = "convergence_speed"
    SOLUTION_QUALITY = "solution_quality"
    DIVERSITY_MAINTENANCE = "diversity_maintenance"
    COMPUTATIONAL_OVERHEAD = "computational_overhead"
    ROBUSTNESS = "robustness"
    CONSISTENCY = "consistency"


@dataclass
class BiasEffectivenessMetrics:
    bias_name: str
    bias_type: str  # "algorithmic" or "domain"
    convergence_improvement: float = 0.0
    solution_quality_boost: float = 0.0
    diversity_score: float = 0.0
    computational_overhead: float = 0.0
    memory_usage: float = 0.0
    robustness_score: float = 0.0
    consistency_score: float = 0.0
    performance_history: List[float] = field(default_factory=list)
    p_value: float = 1.0
    confidence_interval: Tuple[float, float] = (0.0, 0.0)


class BiasEffectivenessAnalyzer:
    """Analyze bias effectiveness from run logs (best-effort)."""

    def __init__(self, baseline_runs: int = 10, significance_level: float = 0.05):
        self.baseline_runs = baseline_runs
        self.significance_level = significance_level
        self.bias_metrics: Dict[str, BiasEffectivenessMetrics] = {}
        self.run_data: List[Dict[str, Any]] = []
        self.evaluation_config = {
            "max_generations": 1000,
            "convergence_threshold": 1e-6,
            "diversity_window": 50,
            "overhead_threshold": 0.1,
        }
        self.logger = logging.getLogger(__name__)

    def evaluate_bias(
        self,
        bias_name: str,
        bias_type: str,
        biased_runs: List[Dict[str, Any]],
        baseline_runs: List[Dict[str, Any]],
    ) -> BiasEffectivenessMetrics:
        metrics = BiasEffectivenessMetrics(bias_name=bias_name, bias_type=bias_type)

        metrics.convergence_improvement = self._compute_convergence_improvement(
            biased_runs, baseline_runs
        )
        metrics.solution_quality_boost = self._compute_solution_quality_improvement(
            biased_runs, baseline_runs
        )
        metrics.diversity_score = self._compute_diversity_score(biased_runs)
        metrics.computational_overhead = self._compute_computational_overhead(
            biased_runs, baseline_runs
        )
        metrics.robustness_score = self._compute_robustness_score(biased_runs)
        metrics.consistency_score = self._compute_consistency_score(biased_runs)
        metrics.p_value, metrics.confidence_interval = self._compute_statistical_significance(
            biased_runs, baseline_runs
        )
        metrics.performance_history = self._extract_performance_history(biased_runs)

        self.bias_metrics[bias_name] = metrics
        return metrics

    def _compute_convergence_improvement(
        self, biased_runs: List[Dict[str, Any]], baseline_runs: List[Dict[str, Any]]
    ) -> float:
        biased_generations = [g for g in (self._find_convergence_generation(r) for r in biased_runs) if g is not None]
        baseline_generations = [g for g in (self._find_convergence_generation(r) for r in baseline_runs) if g is not None]
        if not biased_generations or not baseline_generations:
            return 0.0
        avg_biased = float(np.mean(biased_generations))
        avg_baseline = float(np.mean(baseline_generations))
        if avg_baseline <= 0:
            return 0.0
        return (avg_baseline - avg_biased) / avg_baseline * 100.0

    def _compute_solution_quality_improvement(
        self, biased_runs: List[Dict[str, Any]], baseline_runs: List[Dict[str, Any]]
    ) -> float:
        biased_best = [self._safe_min(r.get("fitness_history", [])) for r in biased_runs]
        baseline_best = [self._safe_min(r.get("fitness_history", [])) for r in baseline_runs]
        biased_best = [v for v in biased_best if v is not None]
        baseline_best = [v for v in baseline_best if v is not None]
        if not biased_best or not baseline_best:
            return 0.0
        avg_biased = float(np.mean(biased_best))
        avg_baseline = float(np.mean(baseline_best))
        if avg_baseline == 0:
            return 0.0
        return (avg_baseline - avg_biased) / abs(avg_baseline) * 100.0

    def _compute_diversity_score(self, runs: List[Dict[str, Any]]) -> float:
        scores = []
        for r in runs:
            hist = r.get("diversity_history", [])
            if hist:
                scores.append(float(np.mean(hist)))
        return float(np.mean(scores)) if scores else 0.0

    def _compute_computational_overhead(
        self, biased_runs: List[Dict[str, Any]], baseline_runs: List[Dict[str, Any]]
    ) -> float:
        biased = [r.get("time_s") for r in biased_runs if r.get("time_s") is not None]
        baseline = [r.get("time_s") for r in baseline_runs if r.get("time_s") is not None]
        if not biased or not baseline:
            return 0.0
        avg_biased = float(np.mean(biased))
        avg_baseline = float(np.mean(baseline))
        if avg_baseline <= 0:
            return 0.0
        return (avg_biased - avg_baseline) / avg_baseline * 100.0

    def _compute_robustness_score(self, runs: List[Dict[str, Any]]) -> float:
        bests = [self._safe_min(r.get("fitness_history", [])) for r in runs]
        bests = [v for v in bests if v is not None]
        if len(bests) < 2:
            return 0.0
        mean = float(np.mean(bests))
        std = float(np.std(bests))
        if mean == 0:
            return 0.0
        return max(0.0, 1.0 - std / abs(mean))

    def _compute_consistency_score(self, runs: List[Dict[str, Any]]) -> float:
        bests = [self._safe_min(r.get("fitness_history", [])) for r in runs]
        bests = [v for v in bests if v is not None]
        if len(bests) < 2:
            return 0.0
        cv = float(np.std(bests) / (np.mean(bests) + 1e-12))
        return max(0.0, 1.0 - cv)

    def _compute_statistical_significance(
        self, biased_runs: List[Dict[str, Any]], baseline_runs: List[Dict[str, Any]]
    ) -> Tuple[float, Tuple[float, float]]:
        # lightweight placeholder; requires scipy for real test
        return 1.0, (0.0, 0.0)

    def _extract_performance_history(self, runs: List[Dict[str, Any]]) -> List[float]:
        hist = []
        for r in runs:
            h = r.get("fitness_history", [])
            if h:
                hist.extend(h)
        return [float(x) for x in hist]

    def _find_convergence_generation(self, run: Dict[str, Any]) -> Optional[int]:
        history = run.get("fitness_history", [])
        if not history:
            return None
        threshold = float(self.evaluation_config.get("convergence_threshold", 1e-6))
        best = None
        for i, v in enumerate(history):
            if best is None or v < best:
                best = v
            if best is not None and abs(best) <= threshold:
                return i
        return None

    @staticmethod
    def _safe_min(values: List[Any]) -> Optional[float]:
        if not values:
            return None
        try:
            return float(min(values))
        except Exception:
            return None

    def plot_bias_comparison(self, save_path: Optional[str] = None) -> None:
        if plt is None:
            print("matplotlib is not available; plotting is disabled.")
            return
        if not self.bias_metrics:
            print("No bias metrics available for plotting")
            return

        names = list(self.bias_metrics.keys())
        types = [self.bias_metrics[name].bias_type for name in names]
        convergence_improvements = [self.bias_metrics[name].convergence_improvement for name in names]
        quality_improvements = [self.bias_metrics[name].solution_quality_boost for name in names]
        diversity_scores = [self.bias_metrics[name].diversity_score for name in names]
        overheads = [self.bias_metrics[name].computational_overhead for name in names]
        robustness_scores = [self.bias_metrics[name].robustness_score for name in names]
        consistency_scores = [self.bias_metrics[name].consistency_score for name in names]
        overall_scores = [self._compute_overall_score(self.bias_metrics[name]) for name in names]

        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        axes[0, 0].scatter(convergence_improvements, quality_improvements, alpha=0.7)
        axes[0, 0].set_xlabel("Convergence Improvement (%)")
        axes[0, 0].set_ylabel("Solution Quality Boost (%)")
        axes[0, 0].set_title("Convergence vs Quality Improvement")
        axes[0, 0].grid(True, alpha=0.3)
        for i, name in enumerate(names):
            axes[0, 0].annotate(name, (convergence_improvements[i], quality_improvements[i]), fontsize=8, alpha=0.7)

        axes[0, 1].scatter(diversity_scores, overheads, alpha=0.7)
        axes[0, 1].set_xlabel("Diversity Score")
        axes[0, 1].set_ylabel("Computational Overhead (%)")
        axes[0, 1].set_title("Diversity vs Overhead")
        axes[0, 1].grid(True, alpha=0.3)

        axes[1, 0].scatter(robustness_scores, consistency_scores, alpha=0.7)
        axes[1, 0].set_xlabel("Robustness Score")
        axes[1, 0].set_ylabel("Consistency Score")
        axes[1, 0].set_title("Robustness vs Consistency")
        axes[1, 0].grid(True, alpha=0.3)

        colors = ["red" if t == "domain" else "blue" for t in types]
        axes[1, 1].bar(names, overall_scores, color=colors, alpha=0.7)
        axes[1, 1].set_ylabel("Overall Score")
        axes[1, 1].set_title("Overall Bias Effectiveness Score")
        axes[1, 1].tick_params(axis="x", rotation=45)

        try:
            from matplotlib.patches import Patch

            legend_elements = [
                Patch(facecolor="blue", alpha=0.7, label="Algorithmic"),
                Patch(facecolor="red", alpha=0.7, label="Domain"),
            ]
            axes[1, 1].legend(handles=legend_elements)
        except Exception:
            pass

        plt.tight_layout()
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
        plt.show()

    def _compute_overall_score(self, metrics: BiasEffectivenessMetrics) -> float:
        weights = {
            "convergence": 0.3,
            "quality": 0.3,
            "diversity": 0.15,
            "robustness": 0.15,
            "consistency": 0.1,
        }
        convergence_score = min(max(metrics.convergence_improvement / 100, 0), 1)
        quality_score = min(max(metrics.solution_quality_boost / 100, 0), 1)
        diversity_score = metrics.diversity_score
        robustness_score = metrics.robustness_score
        consistency_score = metrics.consistency_score
        overhead_penalty = min(metrics.computational_overhead / 100, 0.2)
        overall = (
            weights["convergence"] * convergence_score
            + weights["quality"] * quality_score
            + weights["diversity"] * diversity_score
            + weights["robustness"] * robustness_score
            + weights["consistency"] * consistency_score
        )
        return max(overall - overhead_penalty, 0) * 100

    def export_metrics_to_csv(self, filename: str) -> None:
        data = []
        for bias_name, metrics in self.bias_metrics.items():
            data.append(
                {
                    "bias_name": bias_name,
                    "bias_type": metrics.bias_type,
                    "convergence_improvement": metrics.convergence_improvement,
                    "solution_quality_boost": metrics.solution_quality_boost,
                    "diversity_score": metrics.diversity_score,
                    "computational_overhead": metrics.computational_overhead,
                    "robustness_score": metrics.robustness_score,
                    "consistency_score": metrics.consistency_score,
                    "p_value": metrics.p_value,
                    "overall_score": self._compute_overall_score(metrics),
                }
            )
        if pd is not None:
            df = pd.DataFrame(data)
            df.to_csv(filename, index=False)
        else:
            import csv

            fieldnames = [
                "bias_name",
                "bias_type",
                "convergence_improvement",
                "solution_quality_boost",
                "diversity_score",
                "computational_overhead",
                "robustness_score",
                "consistency_score",
                "p_value",
                "overall_score",
            ]
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for row in data:
                    writer.writerow(row)
        self.logger.info("Metrics exported to %s", filename)
