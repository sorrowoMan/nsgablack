"""Ordinary solving must not load unused optional numerical runtimes."""
import subprocess
import sys
from pathlib import Path


def test_core_and_small_pareto_sort_never_probe_optional_jit_or_copt():
    code = '''
import builtins, sys
original = builtins.__import__
attempts = []
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'numba', 'llvmlite', 'coptpy'}:
        attempts.append(name)
        raise AssertionError('unused optional runtime: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from nsgablack.core import ComposableSolver, EvolutionSolver
from nsgablack.plugins import CoptBackend, CoptBackendConfig, MemoryPlugin
from nsgablack.utils.performance import MemoryManager, FastNonDominatedSort, fast_non_dominated_sort_optimized
import numpy as np
fronts, ranks = fast_non_dominated_sort_optimized(np.array([[0., 1.], [1., 0.], [2., 2.]]))
assert fronts == [[0, 1], [2]]
assert ranks.tolist() == [0, 0, 1]
assert not attempts, attempts
assert not {'numba', 'llvmlite', 'coptpy'}.intersection(sys.modules)
# An actual acceleration request may probe it, and must retain the old fallback.
values = np.column_stack((np.arange(101.), -np.arange(101.)))
fronts, ranks = fast_non_dominated_sort_optimized(values)
assert fronts == [list(range(101))]
assert 'numba' in attempts
assert not any(name.startswith('coptpy') for name in attempts)
'''
    result = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1],
                            capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stderr
