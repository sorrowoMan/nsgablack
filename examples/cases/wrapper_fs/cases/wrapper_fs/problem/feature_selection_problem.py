"""Wrapper feature selection: nsgablack searches feature masks."""
import numpy as np
from nsgablack.core.base import BlackBoxProblem

class FeatureSelectionProblem(BlackBoxProblem):
    def __init__(self, X, y, estimator, *, cv=3, scoring="neg_mean_squared_error"):
        self._X = np.asarray(X, dtype=float); self._y = np.asarray(y, dtype=float)
        self._estimator = estimator; self._cv = int(cv); self._scoring = str(scoring)
        self.n_features = self._X.shape[1]
        super().__init__(dimension=self.n_features, objectives=["minimize"],
                         bounds=[(0.0, 1.0)] * self.n_features, name="feature_selection")
    def evaluate(self, candidate):
        mask = np.asarray(candidate, dtype=float) > 0.5
        if mask.sum() < 2: return 1e10
        from sklearn.model_selection import cross_val_score
        try:
            scores = cross_val_score(self._estimator, self._X[:, mask], self._y, cv=self._cv, scoring=self._scoring)
            return float(-scores.mean())
        except Exception: return 1e10
