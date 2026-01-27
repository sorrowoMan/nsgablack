"""
Array utilities and boundary checking functions for safe array operations
"""

import numpy as np
from typing import Sequence, Union, Tuple, Any


def safe_array_index(array: Union[np.ndarray, Sequence], index: Union[int, slice, Sequence[int]],
                    default: Any = None, allow_empty: bool = True) -> Any:
    """
    Safe array indexing with boundary checking

    Args:
        array: Input array or sequence
        index: Index or slice to access
        default: Default value if index is out of bounds
        allow_empty: Whether to allow empty arrays

    Returns:
        Array element or default value

    Raises:
        ValueError: If array is empty and allow_empty is False
    """
    if not allow_empty and len(array) == 0:
        raise ValueError("Array is empty and allow_empty is False")

    try:
        if isinstance(index, slice):
            # Handle slices safely
            start, stop, step = index.indices(len(array))
            return array[index]
        elif isinstance(index, (list, tuple, np.ndarray)):
            # Handle multiple indices
            if len(index) == 0:
                return default if default is not None else np.array([])
            safe_indices = []
            for i in index:
                if 0 <= i < len(array):
                    safe_indices.append(i)
                elif i < 0:
                    # Handle negative indices
                    neg_index = len(array) + i
                    if 0 <= neg_index < len(array):
                        safe_indices.append(neg_index)
            if not safe_indices:
                return default if default is not None else np.array([])
            return array[safe_indices]
        else:
            # Handle single index
            if isinstance(index, int) and index < 0:
                index = len(array) + index
            if 0 <= index < len(array):
                return array[index]
            else:
                return default
    except (IndexError, TypeError):
        return default


def safe_slice_bounds(array_length: int, start: int, end: int, step: int = 1) -> Tuple[int, int, int]:
    """
    Calculate safe slice bounds for array of given length

    Args:
        array_length: Length of the array
        start: Start index (can be negative)
        end: End index (can be negative)
        step: Step size (default: 1)

    Returns:
        Tuple of (safe_start, safe_end, safe_step)
    """
    if array_length <= 0:
        return 0, 0, 1

    # Convert negative indices
    if start < 0:
        start = array_length + start
    if end < 0:
        end = array_length + end

    # Clamp bounds
    safe_start = max(0, min(start, array_length))
    safe_end = max(0, min(end, array_length))
    safe_step = max(1, step)  # Ensure step is positive

    return safe_start, safe_end, safe_step


def safe_array_concat(arrays: Sequence[np.ndarray], axis: int = 0) -> np.ndarray:
    """
    Safely concatenate arrays, handling empty arrays

    Args:
        arrays: Sequence of arrays to concatenate
        axis: Axis along which to concatenate

    Returns:
        Concatenated array or empty array if all inputs are empty
    """
    # Filter out empty arrays
    non_empty_arrays = [arr for arr in arrays if arr.size > 0]

    if not non_empty_arrays:
        return np.array([])

    # Check if arrays are compatible for concatenation
    first_shape = non_empty_arrays[0].shape
    for arr in non_empty_arrays[1:]:
        if arr.shape != first_shape:
            raise ValueError(f"Array shapes are not compatible: {first_shape} vs {arr.shape}")

    return np.concatenate(non_empty_arrays, axis=axis)


def safe_array_reshape(array: np.ndarray, new_shape: Tuple[int, ...],
                      allow_reshape_empty: bool = True) -> np.ndarray:
    """
    Safely reshape array with boundary checking

    Args:
        array: Input array
        new_shape: Desired new shape
        allow_reshape_empty: Whether to allow reshaping empty arrays

    Returns:
        Reshaped array

    Raises:
        ValueError: If reshape is not possible
    """
    if not allow_reshape_empty and array.size == 0:
        raise ValueError("Cannot reshape empty array")

    # Calculate required size from new shape
    required_size = 1
    for dim in new_shape:
        if dim == -1:
            # Auto-dimension will be calculated by numpy
            continue
        required_size *= dim

    # Check if reshape is possible
    if -1 not in new_shape and required_size != array.size:
        raise ValueError(f"Cannot reshape array of size {array.size} into shape {new_shape}")

    try:
        return array.reshape(new_shape)
    except ValueError as e:
        raise ValueError(f"Reshape failed: {e}")


def validate_array_bounds(array: np.ndarray, name: str = "array") -> None:
    """
    Validate that array has valid bounds and is not corrupted

    Args:
        array: Array to validate
        name: Name of the array for error messages

    Raises:
        ValueError: If array is invalid
    """
    if array is None:
        raise ValueError(f"{name} is None")

    if not isinstance(array, np.ndarray):
        raise ValueError(f"{name} is not a numpy array")

    # Check for NaN or infinite values
    if np.any(np.isnan(array)):
        raise ValueError(f"{name} contains NaN values")

    if np.any(np.isinf(array)):
        raise ValueError(f"{name} contains infinite values")

    # Check dimensions
    if len(array.shape) == 0:
        raise ValueError(f"{name} is scalar (0-dimensional)")


class SafeArrayAccess:
    """
    Class providing safe array access methods with automatic boundary checking
    """

    @staticmethod
    def safe_get(array: np.ndarray, row: int, col: int = None, default: Any = 0.0) -> Any:
        """
        Safely get array element with boundary checking

        Args:
            array: Input array
            row: Row index
            col: Column index (optional, for 1D arrays)
            default: Default value if index is out of bounds

        Returns:
            Array element or default value
        """
        if array.size == 0:
            return default

        try:
            if col is None:
                # 1D array access
                if 0 <= row < len(array):
                    return array[row]
                elif row < 0:
                    neg_index = len(array) + row
                    if 0 <= neg_index < len(array):
                        return array[neg_index]
            else:
                # 2D array access
                if (0 <= row < array.shape[0] and 0 <= col < array.shape[1]):
                    return array[row, col]
                elif row < 0:
                    neg_row = array.shape[0] + row
                    if (0 <= neg_row < array.shape[0] and 0 <= col < array.shape[1]):
                        return array[neg_row, col]
        except (IndexError, TypeError):
            pass

        return default

    @staticmethod
    def safe_slice_1d(array: np.ndarray, start: int, end: int, default: Any = None) -> np.ndarray:
        """
        Safely slice 1D array

        Args:
            array: Input array
            start: Start index
            end: End index
            default: Default value if slice is invalid

        Returns:
            Array slice or default value
        """
        if array.size == 0:
            return default if default is not None else np.array([])

        safe_start, safe_end, _ = safe_slice_bounds(len(array), start, end)

        if safe_start >= safe_end:
            return default if default is not None else np.array([])

        return array[safe_start:safe_end]

    @staticmethod
    def safe_slice_2d(array: np.ndarray, row_start: int, row_end: int,
                     col_start: int, col_end: int, default: Any = None) -> np.ndarray:
        """
        Safely slice 2D array

        Args:
            array: Input 2D array
            row_start: Start row index
            row_end: End row index
            col_start: Start column index
            col_end: End column index
            default: Default value if slice is invalid

        Returns:
            Array slice or default value
        """
        if array.size == 0 or len(array.shape) < 2:
            return default if default is not None else np.array([[]])

        safe_row_start, safe_row_end, _ = safe_slice_bounds(array.shape[0], row_start, row_end)
        safe_col_start, safe_col_end, _ = safe_slice_bounds(array.shape[1], col_start, col_end)

        if safe_row_start >= safe_row_end or safe_col_start >= safe_col_end:
            return default if default is not None else np.array([[]])

        return array[safe_row_start:safe_row_end, safe_col_start:safe_col_end]


# Convenience functions for common operations
def safe_get_element(array: np.ndarray, index: int, default: float = 0.0) -> float:
    """Safely get element from 1D array"""
    return SafeArrayAccess.safe_get(array, index, default=default)


def safe_get_row(array: np.ndarray, row: int, default: np.ndarray = None) -> np.ndarray:
    """Safely get row from 2D array"""
    if default is None:
        default = np.zeros(array.shape[1] if len(array.shape) > 1 else 0)
    return SafeArrayAccess.safe_get(array, row, default=default)


def safe_get_2d_element(array: np.ndarray, row: int, col: int, default: float = 0.0) -> float:
    """Safely get element from 2D array"""
    return SafeArrayAccess.safe_get(array, row, col, default=default)