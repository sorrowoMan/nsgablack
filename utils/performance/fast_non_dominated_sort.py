"""
Fast Non-Dominated Sorting implementation with O(MN²) complexity
Based on Deb et al. (2002) NSGA-II algorithm
"""

import numpy as np
from typing import List, Tuple
import numba
from .array_utils import validate_array_bounds


class FastNonDominatedSort:
    """
    Fast Non-Dominated Sorting algorithm implementation
    Time Complexity: O(MN²) where M is number of objectives, N is population size
    Space Complexity: O(N²) in worst case
    """

    @staticmethod
    def sort(objectives: np.ndarray, constraint_violations: np.ndarray = None) -> Tuple[List[List[int]], np.ndarray]:
        """
        Perform fast non-dominated sorting

        Args:
            objectives: Array of shape (N, M) where N is population size, M is number of objectives
            constraint_violations: Array of shape (N,) with constraint violation values (optional)

        Returns:
            Tuple of (fronts, ranks) where:
            - fronts: List of lists, where each inner list contains indices of solutions in that front
            - ranks: Array of shape (N,) with rank for each solution
        """
        # Validate inputs
        validate_array_bounds(objectives, "objectives")
        if objectives.ndim == 1:
            objectives = objectives.reshape(-1, 1)

        n = objectives.shape[0]
        m = objectives.shape[1]

        # Handle constraint violations
        if constraint_violations is None:
            constraint_violations = np.zeros(n)
        else:
            constraint_violations = np.asarray(constraint_violations)

        # Separate feasible and infeasible solutions
        feasible_mask = constraint_violations <= 1e-10
        infeasible_mask = ~feasible_mask

        fronts = []
        ranks = np.full(n, -1, dtype=int)

        # Handle feasible solutions with non-dominated sorting
        feasible_indices = np.where(feasible_mask)[0]
        if len(feasible_indices) > 0:
            feasible_objectives = objectives[feasible_indices]
            feasible_fronts = FastNonDominatedSort._sort_feasible(feasible_objectives)

            # Map local indices back to global indices
            for front_idx, front in enumerate(feasible_fronts):
                global_front = [feasible_indices[i] for i in front]
                fronts.append(global_front)
                for idx in global_front:
                    ranks[idx] = front_idx

        # Handle infeasible solutions (sorted by constraint violation)
        infeasible_indices = np.where(infeasible_mask)[0]
        if len(infeasible_indices) > 0:
            # Sort infeasible solutions by constraint violation (ascending)
            sorted_infeasible = infeasible_indices[np.argsort(constraint_violations[infeasible_indices])]

            # Add infeasible solutions to last front or create new fronts
            start_rank = len(fronts)
            for i, idx in enumerate(sorted_infeasible):
                ranks[idx] = start_rank + i
                if i == 0:
                    fronts.append([idx])
                else:
                    fronts[-1].append(idx)

        return fronts, ranks

    @staticmethod
    def _sort_feasible(objectives: np.ndarray) -> List[List[int]]:
        """
        Sort feasible solutions using fast non-dominated sorting
        Based on Deb et al. (2002) algorithm
        """
        n = objectives.shape[0]

        # Initialize domination sets and domination counts
        domination_sets = [[] for _ in range(n)]
        domination_counts = np.zeros(n, dtype=int)

        # Calculate domination relationships
        for i in range(n):
            for j in range(n):
                if i != j:
                    if FastNonDominatedSort._dominates(objectives[i], objectives[j]):
                        domination_sets[i].append(j)
                    elif FastNonDominatedSort._dominates(objectives[j], objectives[i]):
                        domination_counts[i] += 1

        # Find first front (solutions with domination count = 0)
        current_front = []
        for i in range(n):
            if domination_counts[i] == 0:
                current_front.append(i)

        fronts = []
        while current_front:
            fronts.append(current_front.copy())

            # Build next front
            next_front = []
            for i in current_front:
                for j in domination_sets[i]:
                    domination_counts[j] -= 1
                    if domination_counts[j] == 0:
                        next_front.append(j)

            current_front = next_front

        return fronts

    @staticmethod
    def _dominates(obj_a: np.ndarray, obj_b: np.ndarray) -> bool:
        """
        Check if solution a dominates solution b
        Solution a dominates b if:
        - a is no worse than b in all objectives
        - a is strictly better than b in at least one objective
        """
        # Assuming minimization problem
        return np.all(obj_a <= obj_b) and np.any(obj_a < obj_b)

    @staticmethod
    def calculate_crowding_distance(objectives: np.ndarray, front: List[int]) -> np.ndarray:
        """
        Calculate crowding distance for solutions in a front

        Args:
            objectives: Array of shape (N, M)
            front: List of indices in the front

        Returns:
            Array of crowding distances
        """
        if len(front) == 0:
            return np.array([])

        n = len(front)
        m = objectives.shape[1]
        crowding_distance = np.zeros(n, dtype=float)

        # Calculate crowding distance for each objective
        for obj_idx in range(m):
            # Sort solutions by this objective
            sorted_indices = np.argsort([objectives[front[i]][obj_idx] for i in range(n)])

            # Boundary solutions in each objective must keep infinite distance.
            if n > 0:
                crowding_distance[sorted_indices[0]] = np.inf
            if n > 1:
                crowding_distance[sorted_indices[-1]] = np.inf

            # Get objective range
            obj_min = objectives[front[sorted_indices[0]]][obj_idx]
            obj_max = objectives[front[sorted_indices[-1]]][obj_idx]
            obj_range = obj_max - obj_min

            if obj_range > 1e-10:
                # Calculate crowding distance for interior solutions
                for i in range(1, n - 1):
                    original_pos = sorted_indices[i]
                    if crowding_distance[original_pos] != np.inf:  # Skip boundary solutions
                        obj_prev = objectives[front[sorted_indices[i - 1]]][obj_idx]
                        obj_next = objectives[front[sorted_indices[i + 1]]][obj_idx]
                        crowding_distance[original_pos] += (obj_next - obj_prev) / obj_range

        # Map back to original indices
        original_distances = np.zeros(len(objectives))
        for i, idx in enumerate(front):
            original_distances[idx] = crowding_distance[i]

        return original_distances


# Numba-accelerated versions (if available)
try:
    @numba.jit(nopython=True, cache=True)
    def dominates_numba(obj_a, obj_b):
        """Numba-accelerated domination check"""
        n_obj = obj_a.shape[0]
        better_in_at_least_one = False
        for i in range(n_obj):
            if obj_a[i] > obj_b[i]:
                return False
            elif obj_a[i] < obj_b[i]:
                better_in_at_least_one = True
        return better_in_at_least_one

    @numba.jit(nopython=True, cache=True)
    def fast_non_dominated_sort_numba(objectives):
        """Numba-accelerated fast non-dominated sorting"""
        n = objectives.shape[0]
        domination_sets = [numba.typed.List.empty_list(numba.int64) for _ in range(n)]
        domination_counts = np.zeros(n, dtype=numba.int32)

        # Calculate domination relationships
        for i in range(n):
            for j in range(n):
                if i != j and dominates_numba(objectives[i], objectives[j]):
                    domination_sets[i].append(j)
                elif i != j and dominates_numba(objectives[j], objectives[i]):
                    domination_counts[i] += 1

        # Find fronts
        fronts = []
        current_front = numba.typed.List.empty_list(numba.int64)

        for i in range(n):
            if domination_counts[i] == 0:
                current_front.append(i)

        while len(current_front) > 0:
            fronts.append(list(current_front))
            next_front = numba.typed.List.empty_list(numba.int64)

            for i in current_front:
                for j in domination_sets[i]:
                    domination_counts[j] -= 1
                    if domination_counts[j] == 0:
                        next_front.append(j)

            current_front = next_front

        return fronts

    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False


def fast_non_dominated_sort_optimized(objectives: np.ndarray, constraint_violations: np.ndarray = None) -> Tuple[List[List[int]], np.ndarray]:
    """
    Optimized fast non-dominated sorting with optional Numba acceleration

    Args:
        objectives: Array of shape (N, M) where N is population size, M is number of objectives
        constraint_violations: Array of shape (N,) with constraint violation values (optional)

    Returns:
        Tuple of (fronts, ranks)
    """
    # Validate inputs
    validate_array_bounds(objectives, "objectives")

    # Use Numba version if available and beneficial
    if NUMBA_AVAILABLE and objectives.shape[0] > 100:  # Only use Numba for larger populations
        try:
            if constraint_violations is None or np.all(constraint_violations <= 1e-10):
                # All feasible, use pure Numba implementation
                fronts = fast_non_dominated_sort_numba(objectives)
                ranks = np.zeros(objectives.shape[0], dtype=int)
                for rank, front in enumerate(fronts):
                    for idx in front:
                        ranks[idx] = rank
                return fronts, ranks
        except Exception:
            # Fallback to standard implementation
            pass

    # Use standard implementation
    return FastNonDominatedSort.sort(objectives, constraint_violations)


# Convenience functions for integration with existing code
def get_pareto_front_indices(objectives: np.ndarray, constraint_violations: np.ndarray = None) -> List[int]:
    """Get indices of solutions in the first Pareto front"""
    fronts, _ = fast_non_dominated_sort_optimized(objectives, constraint_violations)
    return fronts[0] if fronts else []


def count_non_dominated_solutions(objectives: np.ndarray, constraint_violations: np.ndarray = None) -> int:
    """Count number of non-dominated solutions"""
    fronts, _ = fast_non_dominated_sort_optimized(objectives, constraint_violations)
    return len(fronts[0]) if fronts else 0


def is_pareto_optimal(objectives: np.ndarray, index: int, constraint_violations: np.ndarray = None) -> bool:
    """Check if solution at given index is Pareto optimal"""
    fronts, _ = fast_non_dominated_sort_optimized(objectives, constraint_violations)
    if fronts:
        first_front = set(fronts[0])
        return index in first_front
    return False
