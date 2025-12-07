"""模型管理器：训练、保存、续训、加载

设计目标：
- 每个问题（由 problem.name 与维度标识）对应一个持久化模型文件。
- 训练后保存训练样本（限额），每次运行若发现已有模型则在其历史样本上合并新样本并继续训练。
- 文件采用 `joblib` 存储字典：{'clf', 'scaler', 'X_hist', 'y_hist', 'meta'}。
"""
from __future__ import annotations

import os
import time
import joblib
import numpy as np
from typing import Tuple, Optional, Any, Dict
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler


class ModelManager:
    def __init__(self, model_dir: str = None, max_history: int = 5000):
        self.model_dir = model_dir or os.path.join(os.getcwd(), 'ml_models')
        os.makedirs(self.model_dir, exist_ok=True)
        self.max_history = int(max_history)

    def _model_id(self, problem_name: str, dimension: int, extra: str = '') -> str:
        safe_name = problem_name.replace(' ', '_')
        base = f"{safe_name}_d{int(dimension)}"
        if extra:
            return f"{base}_{extra}"
        return base

    def _model_path(self, model_id: str) -> str:
        return os.path.join(self.model_dir, model_id + '.joblib')

    def load(self, model_id: str) -> Optional[Dict[str, Any]]:
        path = self._model_path(model_id)
        if not os.path.exists(path):
            return None
        try:
            return joblib.load(path)
        except Exception:
            return None

    def save(self, model_id: str, payload: Dict[str, Any]) -> None:
        path = self._model_path(model_id)
        joblib.dump(payload, path)

    def _label_bad(self, y_scores: np.ndarray, bad_frac: float) -> np.ndarray:
        n = len(y_scores)
        k = max(1, int(n * float(bad_frac)))
        order = np.argsort(y_scores)[::-1]
        labels = np.zeros(n, dtype=int)
        labels[order[:k]] = 1
        return labels

    def train_or_update(self, problem_name: str, dimension: int,
                        X_new: np.ndarray, y_scores_new: np.ndarray,
                        bad_frac: float = 0.3, model_tag: str = '', random_state: int = 42,
                        include_bad_frac_in_id: bool = True) -> Tuple[Any, StandardScaler, str]:
        """训练或在已有模型上继续训练。

        返回 (clf_wrapper, scaler, model_path)
        clf_wrapper 提供 predict / predict_proba
        """
        # 默认 model_id 若未指定 model_tag，则将 bad_frac 作为标识的一部分，便于复用与续训
        if not model_tag and include_bad_frac_in_id:
            model_tag = f"bad{int(float(bad_frac)*100)}"
        model_id = self._model_id(problem_name, dimension, extra=model_tag)
        path = self._model_path(model_id)

        labels_new = self._label_bad(y_scores_new, bad_frac)

        existing = self.load(model_id)
        if existing is None:
            # 新训练
            X_hist = X_new.copy()
            y_hist = labels_new.copy()
            scaler = StandardScaler()
            Xs = scaler.fit_transform(X_hist)
            clf = RandomForestClassifier(n_estimators=200, random_state=random_state)
            clf.fit(Xs, y_hist)
            meta = {
                'created_at': time.time(),
                'training_runs': 1,
                'bad_frac': float(bad_frac),
                'model_tag': model_tag,
                'version': 'v1'
            }
        else:
            # 续训：合并样本并重训练（简单可靠）
            X_hist = np.vstack([existing.get('X_hist', np.zeros((0, X_new.shape[1]))), X_new])
            y_hist = np.concatenate([existing.get('y_hist', np.zeros(0, dtype=int)), labels_new])
            # 限制历史长度
            if len(X_hist) > self.max_history:
                X_hist = X_hist[-self.max_history:]
                y_hist = y_hist[-self.max_history:]
            scaler = StandardScaler()
            Xs = scaler.fit_transform(X_hist)
            clf = RandomForestClassifier(n_estimators=200, random_state=random_state)
            clf.fit(Xs, y_hist)
            meta = existing.get('meta', {})
            meta['training_runs'] = meta.get('training_runs', 0) + 1
            meta['updated_at'] = time.time()
            # ensure bad_frac and model_tag preserved/updated
            meta.setdefault('bad_frac', float(bad_frac))
            meta.setdefault('model_tag', model_tag)
            meta.setdefault('version', meta.get('version', 'v1'))

        payload = {
            'clf': clf,
            'scaler': scaler,
            'X_hist': X_hist,
            'y_hist': y_hist,
            'meta': meta,
        }
        self.save(model_id, payload)

        # 返回一个 wrapper 对象（具有 predict/predict_proba）简化上层调用
        class PipelineWrapper:
            def __init__(self, clf, scaler):
                self.clf = clf
                self.scaler = scaler
                self.classes_ = clf.classes_

            def predict(self, X_in):
                Xs = self.scaler.transform(X_in)
                return self.clf.predict(Xs)

            def predict_proba(self, X_in):
                Xs = self.scaler.transform(X_in)
                return self.clf.predict_proba(Xs)

        return PipelineWrapper(clf, scaler), scaler, path

    def get_model_info(self, problem_name: str, dimension: int, model_tag: str = '') -> Optional[Dict[str, Any]]:
        model_id = self._model_id(problem_name, dimension, extra=model_tag)
        existing = self.load(model_id)
        if existing is None:
            return None
        return {
            'path': self._model_path(model_id),
            'meta': existing.get('meta', {}),
            'n_samples': int(existing.get('X_hist', np.zeros((0,))).shape[0])
        }

    def get_wrapper_if_exists(self, problem_name: str, dimension: int, model_tag: str = '') -> Optional[Any]:
        model_id = self._model_id(problem_name, dimension, extra=model_tag)
        existing = self.load(model_id)
        if existing is None:
            return None
        clf = existing['clf']
        scaler = existing['scaler']

        class PipelineWrapper:
            def __init__(self, clf, scaler):
                self.clf = clf
                self.scaler = scaler
                self.classes_ = clf.classes_

            def predict(self, X_in):
                Xs = self.scaler.transform(X_in)
                return self.clf.predict(Xs)

            def predict_proba(self, X_in):
                Xs = self.scaler.transform(X_in)
                return self.clf.predict_proba(Xs)

        return PipelineWrapper(clf, scaler)


__all__ = ['ModelManager']
