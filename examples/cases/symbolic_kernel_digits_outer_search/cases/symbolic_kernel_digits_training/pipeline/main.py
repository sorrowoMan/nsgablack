from __future__ import annotations

from typing import Any, Mapping

import numpy as np


def _conv_responses(X: np.ndarray, kernel: np.ndarray, bundle: Mapping[str, Any]) -> np.ndarray:
    shape = tuple(int(v) for v in bundle.get("image_shape", (8, 8)))
    images = np.asarray(X, dtype=float).reshape(-1, *shape)
    kr, kc = kernel.shape
    padding = str(bundle.get("padding", "same")).lower()
    if padding in {"same", "zero", "zeros"}:
        pads = (kr // 2, kr - 1 - kr // 2, kc // 2, kc - 1 - kc // 2)
        mode = "reflect" if padding == "same" else "constant"
        images = np.pad(images, ((0, 0), (pads[0], pads[1]), (pads[2], pads[3])), mode=mode)
    sr, sc = (int(v) for v in bundle.get("stride_shape", (1, 1)))
    patches = []
    for row in range(0, images.shape[1] - kr + 1, max(1, sr)):
        for col in range(0, images.shape[2] - kc + 1, max(1, sc)):
            patches.append(images[:, row : row + kr, col : col + kc])
    tensor = np.stack(patches, axis=1)
    return np.tensordot(tensor, kernel, axes=([2, 3], [0, 1]))


def build_features(X: np.ndarray, bundle: Mapping[str, Any]):
    shape = tuple(int(v) for v in bundle.get("kernel_shape", (3, 3)))
    kernel = np.asarray(bundle.get("coefficients", ()), dtype=float).reshape(shape)
    kernel /= max(float(np.linalg.norm(kernel)), 1.0e-12)
    responses = _conv_responses(X, kernel, bundle)
    output_mode = str(bundle.get("output_mode", "pooled")).lower()
    pooling = str(bundle.get("pooling", "stats")).lower()
    if output_mode == "flattened_features":
        features = responses
    elif pooling == "mean_max":
        features = np.column_stack([np.mean(responses, axis=1), np.max(responses, axis=1)])
    elif pooling == "mean":
        features = np.mean(responses, axis=1, keepdims=True)
    elif pooling == "max":
        features = np.max(responses, axis=1, keepdims=True)
    else:
        features = np.column_stack(
            [
                np.mean(responses, axis=1),
                np.max(responses, axis=1),
                np.std(responses, axis=1),
                np.min(responses, axis=1),
            ]
        )
    if bool(bundle.get("include_input", False)):
        features = np.column_stack([features, np.asarray(X, dtype=float)])
    return np.asarray(features, dtype=float), {
        "component_path": str(bundle.get("component_path", "pipeline.learnable_conv1d")),
        "kernel_shape": list(shape),
        "output_dim": int(features.shape[1]),
        "output_mode": output_mode,
        "pooling": pooling,
    }


def load_digits_data(config: Mapping[str, Any]) -> dict[str, Any]:
    if str(config.get("dataset_key", "digits")).lower() != "digits":
        raise ValueError("this self-contained Case supports dataset_key='digits'")
    from sklearn.datasets import load_digits

    dataset = load_digits()
    X = np.asarray(dataset.data, dtype=float) / 16.0
    y = np.asarray(dataset.target, dtype=int)
    rng = np.random.default_rng(int(config.get("seed", 42)))
    indices = rng.permutation(X.shape[0])[: max(64, min(int(config.get("max_rows", 320)), X.shape[0]))]
    X = X[indices]
    y = y[indices]
    split = min(
        max(int(round(float(config.get("train_ratio", 0.75)) * X.shape[0])), 32),
        X.shape[0] - 16,
    )
    return {
        "X_train": X[:split],
        "y_train": y[:split],
        "X_test": X[split:],
        "y_test": y[split:],
        "classes": np.arange(10, dtype=int),
        "metadata": {
            "protocol": "sklearn_digits_classification_v2",
            "dataset_key": "digits",
            "image_shape": [8, 8],
            "input_dim": 64,
            "n_classes": 10,
            "train_rows": split,
            "test_rows": int(X.shape[0] - split),
        },
    }


__all__ = ["build_features", "load_digits_data"]
