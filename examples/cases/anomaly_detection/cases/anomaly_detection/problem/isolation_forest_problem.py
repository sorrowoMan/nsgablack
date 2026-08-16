"""Anomaly detection as black-box parameter optimization.

LOFProblem:  search (n_neighbors, contamination)
IsolationForestProblem: search (n_estimators, max_samples, max_features)

Each problem wraps sklearn, uses labeled ground truth to compute ROC-AUC,
and returns -ROC_AUC as the single minimization objective.
"""

from __future__ import annotations

import numpy as np
from nsgablack.core.base import BlackBoxProblem


class LOFProblem(BlackBoxProblem):
    def __init__(self, X, y_true):
        self._X = np.asarray(X, dtype=float)
        self._y_true = np.asarray(y_true, dtype=float)
        super().__init__(
            name="LOF_HyperParam_Tuning",
            dimension=2,
            bounds=[(5, 100), (0.01, 0.5)],
            objectives=["negative_roc_auc"],
        )

    def evaluate(self, candidate):
        k_neighbors = max(2, int(round(float(candidate[0]))))
        contamination = float(np.clip(candidate[1], 0.01, 0.5))
        try:
            from sklearn.neighbors import LocalOutlierFactor
            from sklearn.metrics import roc_auc_score

            model = LocalOutlierFactor(
                n_neighbors=k_neighbors,
                contamination=contamination,
                novelty=False,
            )
            labels = model.fit_predict(self._X)
            scores = -model.negative_outlier_factor_
            auc = roc_auc_score(self._y_true, scores)
            return np.array([-auc], dtype=float)
        except Exception:
            return np.array([1e10], dtype=float)


class IsolationForestProblem(BlackBoxProblem):
    def __init__(self, X, y_true):
        self._X = np.asarray(X, dtype=float)
        self._y_true = np.asarray(y_true, dtype=float)
        super().__init__(
            name="IsolationForest_HyperParam_Tuning",
            dimension=3,
            bounds=[(50, 500), (0.1, 1.0), (0.1, 1.0)],
            objectives=["negative_roc_auc"],
        )

    def evaluate(self, candidate):
        n_estimators = max(10, int(round(float(candidate[0]))))
        max_samples = float(np.clip(candidate[1], 0.1, 1.0))
        max_features = float(np.clip(candidate[2], 0.1, 1.0))
        try:
            from sklearn.ensemble import IsolationForest
            from sklearn.metrics import roc_auc_score

            model = IsolationForest(
                n_estimators=n_estimators,
                max_samples=max_samples,
                max_features=max_features,
                random_state=42,
            )
            scores = -model.fit(self._X).score_samples(self._X)
            auc = roc_auc_score(self._y_true, scores)
            return np.array([-auc], dtype=float)
        except Exception:
            return np.array([1e10], dtype=float)
