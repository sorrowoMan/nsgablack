"""AutoML: DE searches model type + hyperparameters jointly."""
import numpy as np
from nsgablack.core.base import BlackBoxProblem

class AutoMLProblem(BlackBoxProblem):
    def __init__(self, X, y):
        self._X = np.asarray(X, dtype=float); self._y = np.asarray(y, dtype=float)
        super().__init__(dimension=4, objectives=["minimize"],
                         bounds=[(0, 2.99), (0.01, 1.0), (2, 20), (0, 1)], name="automl")
    def evaluate(self, candidate):
        m_idx = int(candidate[0]); p1, p2, preproc = candidate[1], int(candidate[2]), candidate[3] > 0.5
        from sklearn.linear_model import LogisticRegression
        from sklearn.tree import DecisionTreeClassifier
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.preprocessing import StandardScaler
        from sklearn.model_selection import cross_val_score
        try:
            Xp = StandardScaler().fit_transform(self._X) if preproc else self._X
            if m_idx == 0: m = LogisticRegression(C=p1, max_iter=500)
            elif m_idx == 1: m = DecisionTreeClassifier(max_depth=max(1,int(p2)), min_samples_split=max(2,int(p1*10)))
            else: m = RandomForestClassifier(n_estimators=max(10,int(p1*200)), max_depth=max(3,int(p2)))
            scores = cross_val_score(m, Xp, self._y, cv=3, scoring='accuracy')
            return float(1.0 - scores.mean())
        except (TypeError, ValueError, FloatingPointError): return 1.0
