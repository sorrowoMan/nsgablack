import os
import csv
import math
import numpy as np
from datetime import datetime
from scipy.spatial.distance import cdist
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.svm import SVC
from sklearn.cluster import DBSCAN


def _get_default_convergence_log_path():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    hist = os.path.join(root, 'history')
    os.makedirs(hist, exist_ok=True)
    return os.path.join(hist, 'all_converged_solutions.csv')


def _ensure_parent_dir(path: str):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)


def _append_converged_solution(file_path: str, x: np.ndarray, f: float):
    x = np.asarray(x, dtype=float)
    dim = x.shape[0]
    _ensure_parent_dir(file_path)
    file_exists = os.path.exists(file_path)
    with open(file_path, 'a', newline='', encoding='utf-8') as fobj:
        writer = csv.writer(fobj)
        if not file_exists:
            header = ['timestamp', 'dim', 'f'] + [f'x{i}' for i in range(dim)]
            writer.writerow(header)
        row = [datetime.now().isoformat(timespec='seconds'), dim, float(f)] + [float(v) for v in x]
        writer.writerow(row)


def _load_converged_solutions(file_path: str, dim: int):
    if not (file_path and os.path.exists(file_path)):
        return np.empty((0, dim), dtype=float), np.empty((0,), dtype=float)
    X, F = [], []
    with open(file_path, 'r', encoding='utf-8') as fobj:
        reader = csv.reader(fobj)
        header = next(reader, None)
        for row in reader:
            try:
                rdim = int(row[1])
                if rdim != dim:
                    continue
                val_f = float(row[2])
                vals = [float(v) for v in row[3:3+dim]]
                if len(vals) == dim:
                    X.append(vals)
                    F.append(val_f)
            except Exception:
                continue
    if not X:
        return np.empty((0, dim), dtype=float), np.empty((0,), dtype=float)
    return np.array(X, dtype=float), np.array(F, dtype=float)


def _scale_to_unit(X: np.ndarray, bounds):
    X = np.asarray(X, dtype=float)
    low = np.array([b[0] for b in bounds], dtype=float)
    high = np.array([b[1] for b in bounds], dtype=float)
    span = np.maximum(high - low, 1e-12)
    Z = (X - low) / span
    return np.clip(Z, 0.0, 1.0)


def _gen_negatives_outside_envelope(bounds, min_sol, max_sol, m: int, rng: np.random.Generator):
    dim = len(bounds)
    lows = np.array([b[0] for b in bounds], dtype=float)
    highs = np.array([b[1] for b in bounds], dtype=float)
    res = []
    attempts = 0
    while len(res) < m and attempts < m * 50:
        attempts += 1
        cand = rng.uniform(lows, highs)
        if np.any(cand < min_sol) or np.any(cand > max_sol):
            res.append(cand)
    if len(res) < m:
        extra = rng.uniform(lows, highs, size=(m - len(res), dim))
        res.extend(list(extra))
    return np.array(res, dtype=float)


def evaluate_convergence_svm(X_pos: np.ndarray, bounds, *, random_state: int = 42,
                             cv_splits: int = 5):
    n = X_pos.shape[0]
    if n < 5:
        return {"ready": False, "reason": "样本不足", "ok": False}
    rng = np.random.default_rng(random_state)
    min_sol = X_pos.min(axis=0)
    max_sol = X_pos.max(axis=0)
    m = max(n * n, 50)
    X_neg = _gen_negatives_outside_envelope(bounds, min_sol, max_sol, m, rng)
    Xp = _scale_to_unit(X_pos, bounds)
    Xn = _scale_to_unit(X_neg, bounds)
    X = np.vstack([Xp, Xn])
    y = np.hstack([np.ones(len(Xp), dtype=int), np.zeros(len(Xn), dtype=int)])
    clf = SVC(kernel='rbf', gamma='scale', class_weight='balanced')
    splits = min(cv_splits, np.bincount(y).min())
    splits = max(2, splits)
    cv = StratifiedKFold(n_splits=splits, shuffle=True, random_state=random_state)
    try:
        scores = cross_val_score(clf, X, y, scoring='roc_auc', cv=cv)
        auc = float(np.mean(scores))
    except Exception:
        scores = cross_val_score(clf, X, y, scoring='accuracy', cv=cv)
        auc = float(np.mean(scores))
    if len(Xp) > 1:
        d = cdist(Xp, Xp).astype(float)
        tri = d[np.triu_indices_from(d, k=1)]
        compact = float(np.mean(tri)) if tri.size > 0 else 0.0
    else:
        compact = 1.0
    ok = (auc >= 0.85) and (compact <= 0.35)
    return {"ready": True, "method": "svm", "auc": auc, "compact": compact, "ok": bool(ok),
            "n_pos": int(n), "n_neg": int(len(Xn))}


def evaluate_convergence_cluster(X_pos: np.ndarray, bounds, *, min_frac: float = 0.7):
    n = X_pos.shape[0]
    if n < 5:
        return {"ready": False, "reason": "样本不足", "ok": False}
    Xp = _scale_to_unit(X_pos, bounds)
    if n >= 5:
        D = cdist(Xp, Xp)
        np.fill_diagonal(D, np.inf)
        k = min(3, n - 1)
        knn = np.sort(D, axis=1)[:, k-1]
        eps = float(np.median(knn))
    else:
        eps = 0.2
    eps = max(1e-3, eps)
    min_samples = max(3, int(0.1 * n))
    labels = DBSCAN(eps=eps, min_samples=min_samples).fit_predict(Xp)
    unique, counts = np.unique(labels[labels >= 0], return_counts=True)
    if counts.size == 0:
        return {"ready": True, "method": "cluster", "ok": False, "reason": "未形成簇"}
    max_count = int(np.max(counts))
    frac = max_count / n
    major_label = unique[int(np.argmax(counts))]
    cluster_pts = Xp[labels == major_label]
    if len(cluster_pts) >= 2:
        diam = float(np.max(cdist(cluster_pts, cluster_pts)))
    else:
        diam = 0.0
    ok = (frac >= min_frac) and (diam <= 0.7)
    return {"ready": True, "method": "cluster", "ok": bool(ok), "major_frac": float(frac), "diameter": float(diam),
            "n_pos": int(n)}


def log_and_maybe_evaluate_convergence(best_x: np.ndarray, best_f: float, bounds, *,
                                       log_file: str | None,
                                       threshold: int = 30,
                                       method: str = 'svm'):
    file_path = log_file or _get_default_convergence_log_path()
    _append_converged_solution(file_path, np.asarray(best_x, dtype=float), float(best_f))
    dim = len(bounds)
    X, _ = _load_converged_solutions(file_path, dim)
    if len(X) < max(5, int(threshold)):
        return {"evaluated": False, "count": int(len(X)), "threshold": int(threshold), "file": file_path}
    result = {"evaluated": True, "file": file_path}
    if method == 'svm':
        r = evaluate_convergence_svm(X, bounds)
        result.update(r)
    elif method == 'cluster':
        r = evaluate_convergence_cluster(X, bounds)
        result.update(r)
    elif method == 'both':
        r1 = evaluate_convergence_svm(X, bounds)
        r2 = evaluate_convergence_cluster(X, bounds)
        result.update({"svm": r1, "cluster": r2, "ok": bool(r1.get('ok', False) and r2.get('ok', False))})
    else:
        result.update({"error": f"未知方法: {method}"})
    return result
