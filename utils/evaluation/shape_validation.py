# -*- coding: utf-8 -*-
"""Shape validation utilities for evaluation paths.

This module provides unified shape validation for:
- evaluate_individual: single candidate evaluation
- evaluate_population: batch evaluation
- plugin short-circuit returns
- snapshot roundtrip consistency
"""

from __future__ import annotations

from typing import Any, Optional, Tuple
import warnings

import numpy as np


class EvaluationShapeError(ValueError):
    """Raised when evaluation return shape is invalid."""
    pass


def validate_individual_evaluation_shape(
    objectives: np.ndarray,
    violation: float,
    num_objectives: int,
    context: str = "evaluate_individual",
    strict: bool = False,
) -> Tuple[np.ndarray, float]:
    """Validate and normalize individual evaluation return shape.
    
    Args:
        objectives: Objectives array from evaluation
        violation: Constraint violation scalar
        num_objectives: Expected number of objectives
        context: Context string for error messages
        strict: If True, raise on shape mismatch; if False, attempt repair
        
    Returns:
        (normalized_objectives, normalized_violation)
        
    Raises:
        EvaluationShapeError: If shape is invalid and strict=True
        
    Expected shapes:
        objectives: (num_objectives,) or (1, num_objectives)
        violation: scalar float
    """
    try:
        obj_arr = np.asarray(objectives, dtype=float)
    except (ValueError, TypeError) as exc:
        msg = f"{context}: objectives cannot be converted to float array: {exc}"
        if strict:
            raise EvaluationShapeError(msg) from exc
        warnings.warn(msg, RuntimeWarning, stacklevel=2)
        return np.full(num_objectives, np.inf), float("inf")
    
    # Validate shape
    if obj_arr.ndim == 0:
        # Scalar objective
        if num_objectives != 1:
            msg = (
                f"{context}: expected {num_objectives} objectives, "
                f"got scalar. Wrapping in array."
            )
            if strict:
                raise EvaluationShapeError(msg)
            warnings.warn(msg, RuntimeWarning, stacklevel=2)
        obj_arr = obj_arr.reshape(1)
    
    elif obj_arr.ndim == 1:
        # Correct shape: (M,)
        if obj_arr.shape[0] != num_objectives:
            msg = (
                f"{context}: expected {num_objectives} objectives, "
                f"got {obj_arr.shape[0]}"
            )
            if strict:
                raise EvaluationShapeError(msg)
            warnings.warn(msg, RuntimeWarning, stacklevel=2)
            # Pad or truncate
            if obj_arr.shape[0] < num_objectives:
                obj_arr = np.pad(obj_arr, (0, num_objectives - obj_arr.shape[0]), constant_values=np.inf)
            else:
                obj_arr = obj_arr[:num_objectives]
    
    elif obj_arr.ndim == 2:
        # Batch shape (1, M) - squeeze to (M,)
        if obj_arr.shape[0] != 1:
            msg = (
                f"{context}: expected single individual, "
                f"got batch of {obj_arr.shape[0]}"
            )
            if strict:
                raise EvaluationShapeError(msg)
            warnings.warn(msg, RuntimeWarning, stacklevel=2)
            obj_arr = obj_arr[0]
        else:
            obj_arr = obj_arr.reshape(-1)
        
        if obj_arr.shape[0] != num_objectives:
            msg = (
                f"{context}: expected {num_objectives} objectives, "
                f"got {obj_arr.shape[0]} after reshape"
            )
            if strict:
                raise EvaluationShapeError(msg)
            warnings.warn(msg, RuntimeWarning, stacklevel=2)
            if obj_arr.shape[0] < num_objectives:
                obj_arr = np.pad(obj_arr, (0, num_objectives - obj_arr.shape[0]), constant_values=np.inf)
            else:
                obj_arr = obj_arr[:num_objectives]
    
    else:
        msg = f"{context}: objectives has invalid ndim={obj_arr.ndim}, expected 1 or 2"
        if strict:
            raise EvaluationShapeError(msg)
        warnings.warn(msg, RuntimeWarning, stacklevel=2)
        return np.full(num_objectives, np.inf), float("inf")
    
    # Validate violation
    try:
        vio_scalar = float(violation)
    except (ValueError, TypeError) as exc:
        msg = f"{context}: violation cannot be converted to float: {exc}"
        if strict:
            raise EvaluationShapeError(msg) from exc
        warnings.warn(msg, RuntimeWarning, stacklevel=2)
        vio_scalar = float("inf")
    
    return obj_arr, vio_scalar


def validate_population_evaluation_shape(
    objectives: np.ndarray,
    violations: np.ndarray,
    population_size: int,
    num_objectives: int,
    context: str = "evaluate_population",
    strict: bool = False,
) -> Tuple[np.ndarray, np.ndarray]:
    """Validate and normalize population evaluation return shape.
    
    Args:
        objectives: Objectives array from evaluation
        violations: Constraint violations array
        population_size: Expected population size
        num_objectives: Expected number of objectives
        context: Context string for error messages
        strict: If True, raise on shape mismatch; if False, attempt repair
        
    Returns:
        (normalized_objectives, normalized_violations)
        
    Raises:
        EvaluationShapeError: If shape is invalid and strict=True
        
    Expected shapes:
        objectives: (N, M)
        violations: (N,)
    """
    try:
        obj_arr = np.asarray(objectives, dtype=float)
    except (ValueError, TypeError) as exc:
        msg = f"{context}: objectives cannot be converted to float array: {exc}"
        if strict:
            raise EvaluationShapeError(msg) from exc
        warnings.warn(msg, RuntimeWarning, stacklevel=2)
        return (
            np.full((population_size, num_objectives), np.inf),
            np.full(population_size, np.inf),
        )
    
    # Validate objectives shape
    if obj_arr.ndim == 0:
        msg = f"{context}: objectives is scalar, expected 2D array"
        if strict:
            raise EvaluationShapeError(msg)
        warnings.warn(msg, RuntimeWarning, stacklevel=2)
        return (
            np.full((population_size, num_objectives), np.inf),
            np.full(population_size, np.inf),
        )
    
    elif obj_arr.ndim == 1:
        # Single objective case: (N,) -> (N, 1)
        if num_objectives != 1:
            msg = (
                f"{context}: got 1D array but expected {num_objectives} objectives. "
                "Reshaping to (N, 1)."
            )
            if strict:
                raise EvaluationShapeError(msg)
            warnings.warn(msg, RuntimeWarning, stacklevel=2)
        obj_arr = obj_arr.reshape(-1, 1)
    
    if obj_arr.ndim != 2:
        msg = f"{context}: objectives has invalid ndim={obj_arr.ndim}, expected 2"
        if strict:
            raise EvaluationShapeError(msg)
        warnings.warn(msg, RuntimeWarning, stacklevel=2)
        return (
            np.full((population_size, num_objectives), np.inf),
            np.full(population_size, np.inf),
        )
    
    # Check dimensions
    actual_pop_size, actual_num_obj = obj_arr.shape
    
    if actual_pop_size != population_size:
        msg = (
            f"{context}: population size mismatch: "
            f"expected {population_size}, got {actual_pop_size}"
        )
        if strict:
            raise EvaluationShapeError(msg)
        warnings.warn(msg, RuntimeWarning, stacklevel=2)
        # Pad or truncate
        if actual_pop_size < population_size:
            pad_rows = population_size - actual_pop_size
            obj_arr = np.vstack([
                obj_arr,
                np.full((pad_rows, actual_num_obj), np.inf)
            ])
        else:
            obj_arr = obj_arr[:population_size]
    
    if actual_num_obj != num_objectives:
        msg = (
            f"{context}: number of objectives mismatch: "
            f"expected {num_objectives}, got {actual_num_obj}"
        )
        if strict:
            raise EvaluationShapeError(msg)
        warnings.warn(msg, RuntimeWarning, stacklevel=2)
        # Pad or truncate columns
        if actual_num_obj < num_objectives:
            pad_cols = num_objectives - actual_num_obj
            obj_arr = np.hstack([
                obj_arr,
                np.full((obj_arr.shape[0], pad_cols), np.inf)
            ])
        else:
            obj_arr = obj_arr[:, :num_objectives]
    
    # Validate violations shape
    try:
        vio_arr = np.asarray(violations, dtype=float).reshape(-1)
    except (ValueError, TypeError) as exc:
        msg = f"{context}: violations cannot be converted to float array: {exc}"
        if strict:
            raise EvaluationShapeError(msg) from exc
        warnings.warn(msg, RuntimeWarning, stacklevel=2)
        return obj_arr, np.full(population_size, np.inf)
    
    if vio_arr.shape[0] != population_size:
        msg = (
            f"{context}: violations size mismatch: "
            f"expected {population_size}, got {vio_arr.shape[0]}"
        )
        if strict:
            raise EvaluationShapeError(msg)
        warnings.warn(msg, RuntimeWarning, stacklevel=2)
        # Pad or truncate
        if vio_arr.shape[0] < population_size:
            vio_arr = np.pad(vio_arr, (0, population_size - vio_arr.shape[0]), constant_values=np.inf)
        else:
            vio_arr = vio_arr[:population_size]
    
    return obj_arr, vio_arr


def validate_plugin_short_circuit_return(
    result: Optional[Tuple[Any, Any]],
    expected_mode: str,  # "individual" or "population"
    population_size: Optional[int],
    num_objectives: int,
    context: str = "plugin_short_circuit",
    strict: bool = False,
) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    """Validate plugin short-circuit return shape.
    
    Args:
        result: Plugin return value (None or (objectives, violations))
        expected_mode: "individual" or "population"
        population_size: Expected population size (for population mode)
        num_objectives: Expected number of objectives
        context: Context string for error messages
        strict: If True, raise on shape mismatch
        
    Returns:
        None if result is None, otherwise normalized (objectives, violations)
        
    Raises:
        EvaluationShapeError: If shape is invalid and strict=True
    """
    if result is None:
        return None
    
    if not isinstance(result, (tuple, list)) or len(result) != 2:
        msg = f"{context}: expected (objectives, violations) tuple, got {type(result)}"
        if strict:
            raise EvaluationShapeError(msg)
        warnings.warn(msg, RuntimeWarning, stacklevel=2)
        return None
    
    objectives, violations = result
    
    if expected_mode == "individual":
        return validate_individual_evaluation_shape(
            objectives, violations, num_objectives, context, strict
        )
    elif expected_mode == "population":
        if population_size is None:
            msg = f"{context}: population_size required for population mode validation"
            if strict:
                raise EvaluationShapeError(msg)
            warnings.warn(msg, RuntimeWarning, stacklevel=2)
            return None
        return validate_population_evaluation_shape(
            objectives, violations, population_size, num_objectives, context, strict
        )
    else:
        raise ValueError(f"Invalid expected_mode: {expected_mode}")


__all__ = [
    "EvaluationShapeError",
    "validate_individual_evaluation_shape",
    "validate_population_evaluation_shape",
    "validate_plugin_short_circuit_return",
]
