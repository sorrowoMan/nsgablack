from __future__ import annotations

from typing import Any, Mapping

import numpy as np


def _basis_kernel(term: str, shape: tuple[int, int]) -> np.ndarray:
    rows, cols = shape
    rr = np.linspace(-1.0, 1.0, rows).reshape(rows, 1)
    cc = np.linspace(-1.0, 1.0, cols).reshape(1, cols)
    name = str(term).strip().lower()
    if name == "identity":
        raw = np.zeros(shape, dtype=float)
        raw[rows // 2, cols // 2] = 1.0
    elif name == "sobel_x":
        raw = np.repeat(cc, rows, axis=0) * np.exp(-2.0 * rr**2)
    elif name == "sobel_y":
        raw = np.repeat(rr, cols, axis=1) * np.exp(-2.0 * cc**2)
    elif name == "laplacian":
        radius = np.repeat(rr**2, cols, axis=1) + np.repeat(cc**2, rows, axis=0)
        raw = 1.0 - 2.5 * radius
        raw -= np.mean(raw)
    else:
        raise ValueError(f"unsupported symbolic kernel term: {term!r}")
    return raw / max(float(np.linalg.norm(raw)), 1.0e-12)


def _compiled_kernel(bundle: Mapping[str, Any]) -> np.ndarray:
    shape = tuple(int(v) for v in bundle.get("kernel_shape", (3, 3)))
    symbolic = dict(bundle.get("symbolic_kernel_object", {}) or {})
    if not symbolic:
        raw = np.asarray(bundle.get("coefficients", ()), dtype=float).reshape(shape)
        return raw / max(float(np.linalg.norm(raw)), 1.0e-12)
    terms = tuple(symbolic.get("basis_terms", ()) or ())
    weights = np.asarray(
        bundle.get("symbolic_kernel_weights", bundle.get("coefficients", ())),
        dtype=float,
    ).reshape(-1)
    kernel = np.zeros(shape, dtype=float)
    for index, term in enumerate(terms):
        weight = float(weights[index]) if index < weights.size else 0.0
        kernel += weight * _basis_kernel(str(term), shape)
    return kernel / max(float(np.linalg.norm(kernel)), 1.0e-12)


def _conv_responses(X: np.ndarray, kernel: np.ndarray, bundle: Mapping[str, Any]) -> np.ndarray:
    image_shape = tuple(int(v) for v in bundle.get("image_shape", (8, 8)))
    images = np.asarray(X, dtype=float).reshape(-1, *image_shape)
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
    responses = _conv_responses(X, _compiled_kernel(bundle), bundle)
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
    state = {
        "component_path": str(bundle.get("component_path", "pipeline.learnable_conv1d")),
        "kernel_shape": list(_compiled_kernel(bundle).shape),
        "output_dim": int(features.shape[1]),
        "output_mode": output_mode,
        "pooling": pooling,
    }
    return np.asarray(features, dtype=float), state


def load_dataset(config: Mapping[str, Any]) -> dict[str, Any]:
    seed = int(config.get("seed", 42))
    rng = np.random.default_rng(seed)
    n_samples = max(64, int(config.get("n_samples", 128)))
    shape = (
        max(4, int(config.get("image_height", 8))),
        max(4, int(config.get("image_width", 8))),
    )
    rr = np.linspace(-1.0, 1.0, shape[0]).reshape(-1, 1)
    cc = np.linspace(-1.0, 1.0, shape[1]).reshape(1, -1)
    images = []
    for _ in range(n_samples):
        blob = np.exp(
            -((rr - rng.uniform(-0.5, 0.5)) ** 2 + (cc - rng.uniform(-0.5, 0.5)) ** 2)
            / rng.uniform(0.18, 0.28)
        )
        image = (
            rng.normal() * np.sin(rng.uniform(1.5, 3.0) * np.pi * rr)
            + rng.normal() * np.cos(rng.uniform(1.5, 3.0) * np.pi * cc)
            + 0.9 * blob
            + rng.normal(scale=0.08, size=shape)
        )
        images.append(image)
    X = np.asarray(images, dtype=float).reshape(n_samples, -1)
    hidden = np.asarray(
        [-0.35, 0.10, 0.40, -0.80, 0.15, 0.75, -0.30, 0.25, 0.55],
        dtype=float,
    ).reshape(3, 3)
    hidden /= np.linalg.norm(hidden)
    hidden_bundle = {
        "image_shape": shape,
        "kernel_shape": (3, 3),
        "padding": "same",
        "stride_shape": (1, 1),
    }
    response = _conv_responses(X, hidden, hidden_bundle)
    y = (
        1.20 * np.mean(response, axis=1)
        + 0.95 * np.max(response, axis=1)
        - 0.50 * np.std(response, axis=1)
        + 0.25 * np.mean(X, axis=1)
        + float(config.get("noise_scale", 0.06)) * rng.normal(size=n_samples)
    )
    split = min(max(int(round(float(config.get("train_ratio", 0.75)) * n_samples)), 32), n_samples - 16)
    return {
        "X_train": X[:split],
        "y_train": y[:split],
        "X_test": X[split:],
        "y_test": y[split:],
        "metadata": {
            "protocol": "synthetic_learnable_conv_image2d_regression_v2",
            "n_samples": n_samples,
            "input_dim": int(X.shape[1]),
            "image_shape": list(shape),
            "hidden_kernel_shape": [3, 3],
            "hidden_kernel": hidden.reshape(-1).tolist(),
            "train_rows": split,
            "test_rows": n_samples - split,
        },
    }


__all__ = ["build_features", "load_dataset"]
