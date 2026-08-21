from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

import numpy as np


def _append(columns, names, families, values, name, family):
    column = np.asarray(values, dtype=float).reshape(-1)
    if column.size and float(np.std(column)) > 1.0e-12:
        columns.append(column)
        names.append(str(name))
        families.append(str(family))


def _lane_features(images: np.ndarray, lane: Mapping[str, Any]):
    family = str(lane.get("family", ""))
    columns: list[np.ndarray] = []
    names: list[str] = []
    families: list[str] = []
    total = np.sum(images, axis=(1, 2))
    if family == "mass":
        _append(columns, names, families, total, "total_ink", family)
    elif family == "row_projection":
        bands = {"top": range(0, 3), "middle": range(2, 6), "bottom": range(5, 8), "all": range(8)}
        for index in bands.get(str(lane.get("row_band", "all")), range(8)):
            _append(columns, names, families, np.sum(images[:, index, :], axis=1), f"row_{index}_ink", family)
    elif family == "col_projection":
        bands = {"left": range(0, 3), "middle": range(2, 6), "right": range(5, 8), "all": range(8)}
        for index in bands.get(str(lane.get("col_band", "all")), range(8)):
            _append(columns, names, families, np.sum(images[:, :, index], axis=1), f"col_{index}_ink", family)
    elif family == "moment":
        rr = np.arange(8, dtype=float).reshape(1, 8, 1)
        cc = np.arange(8, dtype=float).reshape(1, 1, 8)
        denom = np.maximum(total, 1.0e-8)
        row_center = np.sum(images * rr, axis=(1, 2)) / denom
        col_center = np.sum(images * cc, axis=(1, 2)) / denom
        stat = str(lane.get("moment_stat", "all"))
        axis = str(lane.get("moment_axis", "both"))
        if stat in {"center", "all"}:
            if axis in {"row", "both"}:
                _append(columns, names, families, row_center, "row_center", family)
            if axis in {"col", "both"}:
                _append(columns, names, families, col_center, "col_center", family)
        if stat in {"variance", "all"}:
            if axis in {"row", "both"}:
                value = np.sum(images * (rr - row_center.reshape(-1, 1, 1)) ** 2, axis=(1, 2)) / denom
                _append(columns, names, families, value, "row_variance", family)
            if axis in {"col", "both"}:
                value = np.sum(images * (cc - col_center.reshape(-1, 1, 1)) ** 2, axis=(1, 2)) / denom
                _append(columns, names, families, value, "col_variance", family)
    elif family == "symmetry":
        axis = str(lane.get("symmetry_axis", "all"))
        if axis in {"left_right", "all"}:
            value = np.sum(np.abs(images[:, :, :4] - images[:, :, 4:][:, :, ::-1]), axis=(1, 2))
            _append(columns, names, families, value, "left_right_symmetry_error", family)
        if axis in {"top_bottom", "all"}:
            value = np.sum(np.abs(images[:, :4, :] - images[:, 4:, :][:, ::-1, :]), axis=(1, 2))
            _append(columns, names, families, value, "top_bottom_symmetry_error", family)
    elif family == "region":
        mode = str(lane.get("region_mode", "all"))
        center = np.sum(images[:, 2:6, 2:6], axis=(1, 2))
        if mode in {"center", "all"}:
            _append(columns, names, families, center, "center_4x4_ink", family)
        if mode in {"outer_ring", "all"}:
            _append(columns, names, families, total - center, "outer_ring_ink", family)
    elif family == "edge":
        horizontal = np.diff(images, axis=2)
        vertical = np.diff(images, axis=1)
        operator = str(lane.get("edge_operator", "abs"))
        transform = (
            (lambda value: value**2)
            if operator == "squared"
            else (lambda value: value)
            if operator == "signed"
            else np.abs
        )
        direction = str(lane.get("edge_direction", "both"))
        if direction in {"horizontal", "both"}:
            _append(columns, names, families, np.sum(transform(horizontal), axis=(1, 2)), "horizontal_edge", family)
        if direction in {"vertical", "both"}:
            _append(columns, names, families, np.sum(transform(vertical), axis=(1, 2)), "vertical_edge", family)
    elif family in {"patch_pool", "patch_texture"}:
        size = max(2, int(lane.get("patch_size", 2)))
        raw_stride = lane.get("patch_stride", size)
        stride = size if str(raw_stride) == "all" else max(1, int(raw_stride))
        for row in range(0, 8 - size + 1, stride):
            for col in range(0, 8 - size + 1, stride):
                patch = images[:, row : row + size, col : col + size]
                if family == "patch_pool":
                    op = str(lane.get("patch_pooling", "mean"))
                    fn = np.max if op == "max" else np.sum if op == "sum" else np.mean
                else:
                    op = str(lane.get("texture_operator", "std"))
                    if op == "range":
                        value = np.max(patch, axis=(1, 2)) - np.min(patch, axis=(1, 2))
                        _append(columns, names, families, value, f"patch_{row}_{col}_{op}", family)
                        continue
                    fn = np.var if op == "var" else np.std
                _append(columns, names, families, fn(patch, axis=(1, 2)), f"patch_{row}_{col}_{op}", family)
    elif family == "orthogonal_frequency":
        band = str(lane.get("dct_band", "low"))
        coordinates = {
            "low": ((0, 1), (1, 0), (1, 1)),
            "mid": ((1, 2), (2, 1), (2, 2)),
            "high": ((3, 4), (4, 3), (4, 4)),
            "all": ((0, 1), (1, 0), (1, 1), (2, 2), (3, 3)),
        }[band]
        grid = np.arange(8, dtype=float)
        for u, v in coordinates:
            basis = np.cos((2 * grid[:, None] + 1) * u * np.pi / 16) * np.cos(
                (2 * grid[None, :] + 1) * v * np.pi / 16
            )
            _append(columns, names, families, np.sum(images * basis, axis=(1, 2)), f"dct_{u}_{v}", family)
    return columns, names, families


def _target_score(column: np.ndarray, y: np.ndarray) -> float:
    values = np.asarray(column, dtype=float)
    best = 0.0
    for cls in np.unique(y):
        target = (y == cls).astype(float)
        corr = np.corrcoef(values, target)[0, 1]
        if np.isfinite(corr):
            best = max(best, abs(float(corr)))
    return best


def evaluate_bundle(bundle: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
    if str(config.get("dataset_key", "digits")).lower() != "digits":
        raise ValueError("PhiBundle image evaluation supports dataset_key='digits'")
    from sklearn.datasets import load_digits
    from sklearn.model_selection import train_test_split

    raw = load_digits()
    X = np.asarray(raw.data, dtype=float) / 16.0
    y = np.asarray(raw.target, dtype=int)
    max_rows = max(80, min(int(config.get("max_rows", 320)), X.shape[0]))
    rng = np.random.default_rng(int(config.get("seed", 42)))
    chosen = rng.permutation(X.shape[0])[:max_rows]
    X = X[chosen]
    y = y[chosen]
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        train_size=float(config.get("train_ratio", 0.75)),
        random_state=int(config.get("seed", 42)),
        stratify=y,
    )
    all_images = np.vstack([X_train, X_test]).reshape(-1, 8, 8)
    columns: list[np.ndarray] = []
    names: list[str] = []
    families: list[str] = []
    for lane in tuple(bundle.get("lanes", ()) or ()):
        lane_columns, lane_names, lane_families = _lane_features(all_images, dict(lane))
        columns.extend(lane_columns)
        names.extend(lane_names)
        families.extend(lane_families)
    if not columns:
        columns = [np.sum(all_images, axis=(1, 2))]
        names = ["total_ink"]
        families = ["mass"]
    matrix = np.column_stack(columns)
    train_rows = X_train.shape[0]
    pool_train = matrix[:train_rows]
    pool_test = matrix[train_rows:]
    scores = np.asarray([_target_score(pool_train[:, i], y_train) for i in range(matrix.shape[1])])
    keep_top = min(int(bundle.get("representation_candidate_keep_top", 24)), matrix.shape[1])
    candidates = list(np.argsort(-scores)[:keep_top])
    max_selected = min(
        int(bundle.get("representation_max_features", 16)),
        int(bundle.get("max_sources", 8)),
    )
    corr_limit = float(bundle.get("representation_max_pair_abs_corr", 0.95))
    selected: list[int] = []
    for index in candidates:
        if len(selected) >= max_selected:
            break
        if selected:
            correlations = [abs(float(np.corrcoef(pool_train[:, index], pool_train[:, prior])[0, 1])) for prior in selected]
            if any(np.isfinite(value) and value > corr_limit for value in correlations):
                continue
        selected.append(int(index))
    if not selected:
        selected = [int(candidates[0])]
    train = pool_train[:, selected]
    test = pool_test[:, selected]
    mean = np.mean(train, axis=0)
    scale = np.std(train, axis=0)
    scale[scale < 1.0e-8] = 1.0
    train = (train - mean) / scale
    test = (test - mean) / scale
    targets = np.eye(10, dtype=float)[y_train]
    design = np.column_stack([np.ones(train.shape[0]), train])
    test_design = np.column_stack([np.ones(test.shape[0]), test])
    regularizer = np.eye(design.shape[1]) * 0.05
    regularizer[0, 0] = 0.0
    coefficients = np.linalg.pinv(design.T @ design + regularizer) @ design.T @ targets
    train_pred = np.argmax(design @ coefficients, axis=1)
    test_pred = np.argmax(test_design @ coefficients, axis=1)
    train_accuracy = float(np.mean(train_pred == y_train))
    test_accuracy = float(np.mean(test_pred == y_test))
    if len(selected) > 1:
        corr = np.abs(np.corrcoef(train, rowvar=False))
        redundancy = float(np.mean(corr[np.triu_indices_from(corr, k=1)]))
    else:
        redundancy = 0.0
    objectives = [
        1.0 - test_accuracy,
        redundancy,
        float(len(selected)) / float(max(1, int(bundle.get("representation_max_features", 16)))),
        abs(train_accuracy - test_accuracy),
        float(matrix.shape[1]) / 256.0,
    ]
    selected_names = [names[index] for index in selected]
    selected_families = [families[index] for index in selected]
    return {
        "objectives": objectives,
        "metrics": {
            "train_accuracy": train_accuracy,
            "test_accuracy": test_accuracy,
            "best_accuracy": test_accuracy,
            "generalization_gap": train_accuracy - test_accuracy,
        },
        "representation_report": {
            "pool_feature_count": int(matrix.shape[1]),
            "selected_feature_count": len(selected),
            "selected_feature_names": selected_names,
            "target_scores": [float(scores[index]) for index in selected],
        },
        "source_report": {
            "enabled_lane_count": len(tuple(bundle.get("lanes", ()) or ())),
            "selected_family_counts": dict(Counter(selected_families)),
        },
        "model": {
            "kind": "ridge_classifier",
            "selected_feature_names": selected_names,
            "feature_mean": mean.tolist(),
            "feature_scale": scale.tolist(),
            "coefficients": coefficients.tolist(),
        },
    }


__all__ = ["evaluate_bundle"]
