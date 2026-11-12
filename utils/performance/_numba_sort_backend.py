"""Optional JIT backend, imported only when acceleration is requested."""
import numpy as np

try:
    import numba  # type: ignore
except Exception:
    # Optional dependency; must never break package import.
    numba = None  # type: ignore


# Numba-accelerated versions (optional)
if numba is not None:
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
    except Exception:
        dominates_numba = None
        fast_non_dominated_sort_numba = None
        NUMBA_AVAILABLE = False
else:
    dominates_numba = None
    fast_non_dominated_sort_numba = None
    NUMBA_AVAILABLE = False
