from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EtfLaneOuterSearchConfig:
    dataset_url: str = r"C:\Users\hp\Desktop\mlblack\runs\etf_temporal_forecast\cache\multi_etf_returns_momodel_kaggle.parquet"
    dataset_label: str = "multi_etf_returns_momodel_kaggle"
    output_dir: str = "runs/etf_lane_outer_search"
    seed: int = 42
    pop_size: int = 4
    offspring_size: int = 4
    generations: int = 1
    mutation_sigma: float = 0.14
    crossover_rate: float = 0.9
    # Inner mlblack eval
    baseline_models: str = "ridge,hist_gradient_boosting"
    # Walk-forward + seeds
    seeds: tuple[int, ...] = (42, 52)
    wf_min_train_size: int = 1200
    wf_test_size: int = 200
    wf_step_size: int = 200
    wf_mode: str = "expanding"
    wf_train_window_size: int = 1440
    wf_max_folds: int = 2
    wf_max_train_panel_rows: int = 3000
    wf_max_test_panel_rows: int = 1000
    # Outer objective weights: trading utility + robustness
    objective_weight_neg_net_sharpe: float = 1.0
    objective_weight_max_drawdown_abs: float = 1.0
    objective_weight_turnover_proxy: float = 1.0
    objective_weight_neg_rank_ic_mean: float = 1.0
    objective_weight_rank_ic_std: float = 1.0


__all__ = ["EtfLaneOuterSearchConfig"]
