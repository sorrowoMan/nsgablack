# -*- coding: utf-8 -*-
"""Tests for evaluation shape validation across all evaluation paths."""

from __future__ import annotations

import pytest
import numpy as np
import warnings

from nsgablack.utils.evaluation.shape_validation import (
    EvaluationShapeError,
    validate_individual_evaluation_shape,
    validate_population_evaluation_shape,
    validate_plugin_short_circuit_return,
)


# ============================================================================
# Test validate_individual_evaluation_shape
# ============================================================================

def test_individual_valid_shape_1d():
    """Test valid 1D objective array."""
    objectives = np.array([1.0, 2.0, 3.0])
    violation = 0.5
    
    obj, vio = validate_individual_evaluation_shape(objectives, violation, 3, strict=True)
    
    assert obj.shape == (3,)
    assert vio == 0.5
    np.testing.assert_array_equal(obj, [1.0, 2.0, 3.0])


def test_individual_valid_shape_2d_single_row():
    """Test valid 2D objective array with single row."""
    objectives = np.array([[1.0, 2.0, 3.0]])
    violation = 0.0
    
    obj, vio = validate_individual_evaluation_shape(objectives, violation, 3, strict=True)
    
    assert obj.shape == (3,)
    np.testing.assert_array_equal(obj, [1.0, 2.0, 3.0])


def test_individual_scalar_objective():
    """Test scalar objective (single-objective case)."""
    objectives = 5.0
    violation = 0.0
    
    obj, vio = validate_individual_evaluation_shape(objectives, violation, 1, strict=False)
    
    assert obj.shape == (1,)
    assert obj[0] == 5.0


def test_individual_shape_mismatch_strict():
    """Test shape mismatch in strict mode raises."""
    objectives = np.array([1.0, 2.0])
    violation = 0.0
    
    with pytest.raises(EvaluationShapeError, match="expected 3 objectives, got 2"):
        validate_individual_evaluation_shape(objectives, violation, 3, strict=True)


def test_individual_shape_mismatch_soft():
    """Test shape mismatch in soft mode pads/truncates."""
    # Too few objectives
    objectives = np.array([1.0, 2.0])
    violation = 0.0
    
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        obj, vio = validate_individual_evaluation_shape(objectives, violation, 4, strict=False)
        assert len(w) > 0
        assert "expected 4 objectives, got 2" in str(w[0].message)
    
    assert obj.shape == (4,)
    np.testing.assert_array_equal(obj[:2], [1.0, 2.0])
    assert obj[2] == np.inf
    assert obj[3] == np.inf
    
    # Too many objectives
    objectives = np.array([1.0, 2.0, 3.0, 4.0])
    
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        obj, vio = validate_individual_evaluation_shape(objectives, violation, 2, strict=False)
        assert len(w) > 0
    
    assert obj.shape == (2,)
    np.testing.assert_array_equal(obj, [1.0, 2.0])


def test_individual_invalid_dtype():
    """Test invalid dtype handling."""
    objectives = ["not", "a", "number"]
    violation = 0.0
    
    with pytest.raises(EvaluationShapeError, match="cannot be converted to float"):
        validate_individual_evaluation_shape(objectives, violation, 3, strict=True)
    
    # Soft mode returns inf
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        obj, vio = validate_individual_evaluation_shape(objectives, violation, 3, strict=False)
    
    assert obj.shape == (3,)
    assert all(np.isinf(obj))


def test_individual_invalid_violation_type():
    """Test invalid violation type."""
    objectives = np.array([1.0, 2.0])
    violation = "not a number"
    
    with pytest.raises(EvaluationShapeError, match="violation cannot be converted"):
        validate_individual_evaluation_shape(objectives, violation, 2, strict=True)
    
    # Soft mode returns inf
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        obj, vio = validate_individual_evaluation_shape(objectives, violation, 2, strict=False)
    
    assert vio == np.inf


# ============================================================================
# Test validate_population_evaluation_shape
# ============================================================================

def test_population_valid_shape():
    """Test valid population evaluation shape."""
    objectives = np.array([
        [1.0, 2.0],
        [3.0, 4.0],
        [5.0, 6.0],
    ])
    violations = np.array([0.0, 0.5, 1.0])
    
    obj, vio = validate_population_evaluation_shape(
        objectives, violations, 3, 2, strict=True
    )
    
    assert obj.shape == (3, 2)
    assert vio.shape == (3,)
    np.testing.assert_array_equal(obj, objectives)
    np.testing.assert_array_equal(vio, violations)


def test_population_single_objective_1d():
    """Test single-objective case with 1D array — shape (N,) should be quietly reshaped to (N,1)."""
    objectives = np.array([1.0, 2.0, 3.0])
    violations = np.array([0.0, 0.0, 0.0])

    # num_objectives=1 + 1D array: valid, no warning expected (silent reshape)
    obj, vio = validate_population_evaluation_shape(
        objectives, violations, 3, 1, strict=False
    )

    assert obj.shape == (3, 1)
    np.testing.assert_array_equal(obj.reshape(-1), objectives)


def test_population_size_mismatch_strict():
    """Test population size mismatch in strict mode."""
    objectives = np.array([
        [1.0, 2.0],
        [3.0, 4.0],
    ])
    violations = np.array([0.0, 0.5])
    
    with pytest.raises(EvaluationShapeError, match="population size mismatch: expected 5, got 2"):
        validate_population_evaluation_shape(
            objectives, violations, 5, 2, strict=True
        )


def test_population_size_mismatch_soft_pad():
    """Test population size mismatch with padding."""
    objectives = np.array([
        [1.0, 2.0],
        [3.0, 4.0],
    ])
    violations = np.array([0.0, 0.5])
    
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        obj, vio = validate_population_evaluation_shape(
            objectives, violations, 4, 2, strict=False
        )
        assert len(w) > 0
    
    assert obj.shape == (4, 2)
    assert vio.shape == (4,)
    # First 2 rows should match
    np.testing.assert_array_equal(obj[:2], objectives)
    # Padded rows should be inf
    assert all(np.isinf(obj[2]))
    assert all(np.isinf(obj[3]))
    assert vio[2] == np.inf
    assert vio[3] == np.inf


def test_population_size_mismatch_soft_truncate():
    """Test population size mismatch with truncation."""
    objectives = np.array([
        [1.0, 2.0],
        [3.0, 4.0],
        [5.0, 6.0],
        [7.0, 8.0],
    ])
    violations = np.array([0.0, 0.5, 1.0, 1.5])
    
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        obj, vio = validate_population_evaluation_shape(
            objectives, violations, 2, 2, strict=False
        )
        assert len(w) > 0
    
    assert obj.shape == (2, 2)
    assert vio.shape == (2,)
    np.testing.assert_array_equal(obj, objectives[:2])
    np.testing.assert_array_equal(vio, violations[:2])


def test_population_objectives_mismatch():
    """Test number of objectives mismatch."""
    objectives = np.array([
        [1.0, 2.0, 3.0],
        [4.0, 5.0, 6.0],
    ])
    violations = np.array([0.0, 0.5])
    
    # Too many objectives - truncate
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        obj, vio = validate_population_evaluation_shape(
            objectives, violations, 2, 2, strict=False
        )
        assert any("number of objectives mismatch" in str(w_item.message) for w_item in w)
    
    assert obj.shape == (2, 2)
    np.testing.assert_array_equal(obj, objectives[:, :2])
    
    # Too few objectives - pad
    objectives_short = np.array([
        [1.0],
        [2.0],
    ])
    
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        obj, vio = validate_population_evaluation_shape(
            objectives_short, violations, 2, 3, strict=False
        )
        assert any("number of objectives mismatch" in str(w_item.message) for w_item in w)
    
    assert obj.shape == (2, 3)
    np.testing.assert_array_equal(obj[:, 0], [1.0, 2.0])
    assert np.isinf(obj[0, 1]) and np.isinf(obj[0, 2])


def test_population_violations_shape_mismatch():
    """Test violations shape mismatch."""
    objectives = np.array([
        [1.0, 2.0],
        [3.0, 4.0],
        [5.0, 6.0],
    ])
    violations = np.array([0.0, 0.5])  # Too short
    
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        obj, vio = validate_population_evaluation_shape(
            objectives, violations, 3, 2, strict=False
        )
        assert any("violations size mismatch" in str(w_item.message) for w_item in w)
    
    assert vio.shape == (3,)
    np.testing.assert_array_equal(vio[:2], [0.0, 0.5])
    assert vio[2] == np.inf


# ============================================================================
# Test validate_plugin_short_circuit_return
# ============================================================================

def test_plugin_short_circuit_none():
    """Test that None passthrough works."""
    result = validate_plugin_short_circuit_return(
        None, "individual", None, 2, strict=True
    )
    assert result is None


def test_plugin_short_circuit_individual_mode():
    """Test plugin short-circuit for individual evaluation."""
    objectives = np.array([1.0, 2.0])
    violation = 0.5
    
    result = validate_plugin_short_circuit_return(
        (objectives, violation), "individual", None, 2, strict=True
    )
    
    assert result is not None
    obj, vio = result
    assert obj.shape == (2,)
    assert vio == 0.5


def test_plugin_short_circuit_population_mode():
    """Test plugin short-circuit for population evaluation."""
    objectives = np.array([[1.0, 2.0], [3.0, 4.0]])
    violations = np.array([0.0, 0.5])
    
    result = validate_plugin_short_circuit_return(
        (objectives, violations), "population", 2, 2, strict=True
    )
    
    assert result is not None
    obj, vio = result
    assert obj.shape == (2, 2)
    assert vio.shape == (2,)


def test_plugin_short_circuit_invalid_return_type():
    """Test invalid return type handling."""
    result = validate_plugin_short_circuit_return(
        "not a tuple", "individual", None, 2, strict=False
    )
    
    # Should return None with warning
    assert result is None


def test_plugin_short_circuit_invalid_tuple_length():
    """Test invalid tuple length."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = validate_plugin_short_circuit_return(
            (1, 2, 3), "individual", None, 2, strict=False
        )
        assert len(w) > 0
        assert "expected (objectives, violations) tuple" in str(w[0].message)
    
    assert result is None


def test_plugin_short_circuit_missing_population_size():
    """Test error when population_size is missing in population mode."""
    objectives = np.array([[1.0, 2.0]])
    violations = np.array([0.0])
    
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = validate_plugin_short_circuit_return(
            (objectives, violations), "population", None, 2, strict=False
        )
        assert any("population_size required" in str(w_item.message) for w_item in w)
    
    assert result is None


# ============================================================================
# Integration test: snapshot roundtrip
# ============================================================================

def test_snapshot_roundtrip_consistency():
    """Test that validated shapes survive snapshot roundtrip."""
    # Simulate population evaluation
    objectives = np.array([
        [1.0, 2.0],
        [3.0, 4.0],
        [5.0, 6.0],
    ])
    violations = np.array([0.0, 0.5, 1.0])
    
    # Validate
    obj_validated, vio_validated = validate_population_evaluation_shape(
        objectives, violations, 3, 2, strict=True
    )
    
    # Simulate snapshot write/read (serialize + deserialize)
    obj_roundtrip = np.copy(obj_validated)
    vio_roundtrip = np.copy(vio_validated)
    
    # Re-validate after roundtrip
    obj_revalidated, vio_revalidated = validate_population_evaluation_shape(
        obj_roundtrip, vio_roundtrip, 3, 2, strict=True
    )
    
    # Should be identical
    np.testing.assert_array_equal(obj_validated, obj_revalidated)
    np.testing.assert_array_equal(vio_validated, vio_revalidated)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
