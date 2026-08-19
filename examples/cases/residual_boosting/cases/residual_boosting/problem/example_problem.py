# -*- coding: utf-8 -*-
"""Residual boosting case: nsgablack searches recipes, mlblack provides inner ML semantics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np

from mlblack.core import UnknownState
from mlblack.models import LinearPointModel, PredictionIOContract, PredictionIntegrationComponent
from mlblack.pipeline.data_views import NumericDataView, train_valid_split
from mlblack.pipeline.model_conditioning import ModelConditionedTargetComponent, ModelConditionedTargetConfig
from mlblack.problems import SupervisedRegressionProblem

from nsgablack.core.base import BlackBoxProblem


@dataclass(frozen=True)
class ResidualBoostingRecipe:
    base_l2: float
    residual_l2: float
    residual_weight: float
    residual_feature_mode: str


@dataclass(frozen=True)
class ResidualFeatureModel:
    model: LinearPointModel
    raw_feature_names: Sequence[str]
    mode: str

    def predict(self, X: np.ndarray) -> np.ndarray:
        matrix, _ = _residual_feature_matrix(X, self.raw_feature_names, self.mode)
        return self.model.predict(matrix)


@dataclass(frozen=True)
class ClosedFormLinearFit:
    """Semantic result of one analytical fit, without a private lifecycle."""

    model: LinearPointModel
    state: UnknownState
    feedback: Any
    report: Mapping[str, Any]


def _fit_closed_form_linear(
    *,
    data: NumericDataView,
    l2: float,
    stage: str,
    feature_mode: str = "raw",
    target_mode: str = "target",
    reference_model: Any | None = None,
) -> ClosedFormLinearFit:
    stage_data = _prepare_stage_data(
        data,
        feature_mode=feature_mode,
        target_mode=target_mode,
        reference_model=reference_model,
    )
    model = _fit_ridge_linear(stage_data, l2=float(l2), metadata={"stage": stage})
    problem = SupervisedRegressionProblem(stage_data, l2=float(l2), complexity_weight=0.0)
    state = _state_from_model(model)
    feedback = problem.evaluate(model, state, {})
    report = {
        "stage": str(stage),
        "target_mode": str(target_mode),
        "feature_mode": str(feature_mode),
        "valid_mse": float(feedback.metrics.get("valid.mse", feedback.objectives[0])),
        "n_features": int(stage_data.n_features),
    }
    return ClosedFormLinearFit(
        model=model,
        state=state,
        feedback=feedback,
        report=report,
    )


def _prepare_stage_data(
    data: NumericDataView,
    *,
    feature_mode: str,
    target_mode: str,
    reference_model: Any | None,
) -> NumericDataView:
    stage_data = data
    if str(target_mode) == "residual":
        if reference_model is None:
            raise ValueError("residual stage requires a reference model")
        stage_data = ModelConditionedTargetComponent(
            reference_model=reference_model,
            config=ModelConditionedTargetConfig(mode="residual", reference_name="base"),
        ).build(stage_data)
    if str(feature_mode) == "raw":
        return stage_data
    X_train, names = _residual_feature_matrix(
        stage_data.X_train,
        stage_data.effective_feature_names,
        str(feature_mode),
    )
    X_valid = (
        None
        if stage_data.X_valid is None
        else _residual_feature_matrix(
            stage_data.X_valid,
            stage_data.effective_feature_names,
            str(feature_mode),
        )[0]
    )
    return NumericDataView(
        X_train=X_train,
        y_train=stage_data.y_train,
        X_valid=X_valid,
        y_valid=stage_data.y_valid,
        feature_names=names,
        target_name=stage_data.target_name,
        metadata={**dict(stage_data.metadata), "residual_feature_mode": str(feature_mode)},
    )


class ResidualBoostingProblem(BlackBoxProblem):
    def __init__(self, n_samples: int = 160, valid_ratio: float = 0.25, seed: int = 7) -> None:
        self.data = _build_regression_data(n_samples=int(n_samples), valid_ratio=float(valid_ratio), seed=int(seed))
        self.last_report: dict[str, Any] = {}
        self._cache: dict[tuple[float, ...], np.ndarray] = {}
        self._report_cache: dict[tuple[float, ...], dict[str, Any]] = {}
        bounds = {
            "x0": [0.0, 0.8],
            "x1": [0.0, 0.8],
            "x2": [0.0, 1.5],
            "x3": [0.0, 1.0],
        }
        super().__init__(
            name="ResidualBoostingProblem",
            dimension=4,
            bounds=bounds,
            objectives=["valid_mse", "recipe_complexity"],
        )

    def decode_recipe(self, x: np.ndarray) -> ResidualBoostingRecipe:
        arr = np.asarray(x, dtype=float).reshape(-1)
        if arr.size != self.dimension:
            raise ValueError(f"expected {self.dimension} recipe values, got {arr.size}")
        feature_mode = "enriched" if float(arr[3]) >= 0.5 else "raw"
        return ResidualBoostingRecipe(
            base_l2=float(np.clip(arr[0], 0.0, 0.8)),
            residual_l2=float(np.clip(arr[1], 0.0, 0.8)),
            residual_weight=float(np.clip(arr[2], 0.0, 1.5)),
            residual_feature_mode=feature_mode,
        )

    def evaluate(self, candidate: np.ndarray) -> np.ndarray:
        key = tuple(np.round(np.asarray(candidate, dtype=float).reshape(-1), 6))
        cached = self._cache.get(key)
        if cached is not None:
            report = self._report_cache.get(key)
            if report is not None:
                self.last_report = dict(report)
            return cached.copy()
        recipe = self.decode_recipe(np.asarray(candidate, dtype=float))
        base_result = _fit_closed_form_linear(
            data=self.data,
            l2=recipe.base_l2,
            stage="base_linear",
        )
        base_model = base_result.model
        residual_result = _fit_closed_form_linear(
            data=self.data,
            l2=recipe.residual_l2,
            stage="residual_linear",
            feature_mode=recipe.residual_feature_mode,
            target_mode="residual",
            reference_model=base_model,
        )
        residual_model = ResidualFeatureModel(
            model=residual_result.model,
            raw_feature_names=self.data.effective_feature_names,
            mode=recipe.residual_feature_mode,
        )
        integrated = PredictionIntegrationComponent.additive(
            component_order=("base", "residual"),
            weights={"base": 1.0, "residual": recipe.residual_weight},
            io_contract=PredictionIOContract.shared_numeric(n_features=self.data.n_features),
            metadata={"owner": "mlblack", "pattern": "residual_boosting"},
        ).compose(
            {"base": base_model, "residual": residual_model},
            metadata={"outer_recipe": recipe.__dict__},
        )
        feedback = SupervisedRegressionProblem(self.data, complexity_weight=0.0).evaluate(
            integrated,
            UnknownState(values=np.asarray(candidate, dtype=float).reshape(-1), metadata={"recipe": recipe.__dict__}),
            {},
        )
        valid_mse = float(feedback.metrics.get("valid.mse", feedback.objectives[0]))
        complexity = _recipe_complexity(recipe, residual_model.model)
        objectives = np.asarray([valid_mse, complexity], dtype=float)
        report = {
            "recipe": recipe.__dict__,
            "valid_mse": valid_mse,
            "complexity": complexity,
            "component_stage_count": 2,
            "component_stages": ["base_linear", "residual_linear"],
            "component_reports": [dict(base_result.report), dict(residual_result.report)],
            "integrated_model": integrated.describe(),
        }
        self.last_report = report
        self._report_cache[key] = dict(report)
        self._cache[key] = objectives.copy()
        return objectives

    def evaluate_constraints(self, candidate: np.ndarray) -> np.ndarray:
        _ = candidate
        return np.zeros(0, dtype=float)


ExampleProblem = ResidualBoostingProblem


def _build_regression_data(*, n_samples: int, valid_ratio: float, seed: int) -> NumericDataView:
    rng = np.random.default_rng(int(seed))
    X = rng.uniform(-2.0, 2.0, size=(int(n_samples), 3))
    noise = rng.normal(0.0, 0.08, size=int(n_samples))
    y = 1.2 + 1.4 * X[:, 0] - 0.7 * X[:, 1] + 1.8 * X[:, 0] * X[:, 1] + 0.65 * (X[:, 2] ** 2) + noise
    return train_valid_split(
        X,
        y,
        valid_ratio=float(valid_ratio),
        seed=int(seed),
        feature_names=("x0", "x1", "x2"),
        target_name="synthetic_residual_target",
    )


def _fit_ridge_linear(data: NumericDataView, *, l2: float, metadata: Mapping[str, Any]) -> LinearPointModel:
    X = np.asarray(data.X_train, dtype=float)
    y = np.asarray(data.y_train, dtype=float).reshape(-1)
    design = np.column_stack([np.ones(X.shape[0]), X])
    penalty = np.eye(design.shape[1], dtype=float) * float(l2)
    penalty[0, 0] = 0.0
    lhs = design.T @ design + penalty
    rhs = design.T @ y
    try:
        beta = np.linalg.solve(lhs, rhs)
    except np.linalg.LinAlgError:
        beta = np.linalg.pinv(lhs) @ rhs
    return LinearPointModel(
        intercept=float(beta[0]),
        weights=np.asarray(beta[1:], dtype=float),
        feature_names=data.effective_feature_names,
        metadata=dict(metadata),
    )


def _residual_feature_matrix(
    X: np.ndarray,
    raw_feature_names: Sequence[str],
    mode: str,
) -> tuple[np.ndarray, tuple[str, ...]]:
    X_arr = np.asarray(X, dtype=float)
    names = tuple(str(name) for name in raw_feature_names)
    if str(mode) == "raw":
        return X_arr, names
    x0 = X_arr[:, 0]
    x1 = X_arr[:, 1]
    x2 = X_arr[:, 2]
    extra = np.column_stack([x0 * x1, x2 ** 2])
    return np.column_stack([X_arr, extra]), names + ("x0*x1", "x2^2")


def _state_from_model(model: LinearPointModel) -> UnknownState:
    return UnknownState(values=np.concatenate([[float(model.intercept)], np.asarray(model.weights, dtype=float).reshape(-1)]))


def _recipe_complexity(recipe: ResidualBoostingRecipe, residual_model: LinearPointModel) -> float:
    active = float(np.count_nonzero(np.abs(residual_model.weights) > 1e-8))
    feature_cost = 2.0 if recipe.residual_feature_mode == "enriched" else 0.5
    weight_cost = abs(float(recipe.residual_weight))
    return float(active + feature_cost + weight_cost)
