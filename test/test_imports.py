#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test project imports"""

import sys
import os

print("Test 1: Import from project root as package")
try:
    from core import BlackBoxProblem, BlackBoxSolverNSGAII
    from utils import CallableSingleObjectiveProblem
    from solvers import SurrogateAssistedNSGAII
    from ml import ModelManager
    print("[OK] All packages imported successfully")
except ImportError as e:
    print(f"[FAIL] Import failed: {e}")
    import traceback
    traceback.print_exc()

print("\nTest 2: Test relative imports within packages")
try:
    from core.diversity import DiversityAwareInitializerBlackBox
    from core.convergence import log_and_maybe_evaluate_convergence
    from utils.headless import run_headless_single_objective
    from bias import BiasModule
    print("[OK] Relative imports successful")
except ImportError as e:
    print(f"[FAIL] Relative import failed: {e}")

print("\nTest 3: Test cross-package imports")
try:
    from utils.numba_helpers import fast_is_dominated, NUMBA_AVAILABLE
    print("[OK] Cross-package imports successful")
except ImportError as e:
    print(f"[FAIL] Cross-package import failed: {e}")

print("\nTest 4: Test direct import from examples directory")
current_dir = os.getcwd()
examples_dir = os.path.join(current_dir, 'examples')
os.chdir(examples_dir)
sys.path.insert(0, current_dir)

try:
    from core.base import BlackBoxProblem
    from core.solver import BlackBoxSolverNSGAII
    from bias import BiasModule
    from solvers.nsga2 import BlackBoxSolverNSGAII
    print("[OK] Examples directory import successful")
except ImportError as e:
    print(f"[FAIL] Examples directory import failed: {e}")
finally:
    os.chdir(current_dir)

print("\nTest 5: Test class instantiation")
try:
    from core.problems import SphereBlackBox
    problem = SphereBlackBox(dimension=2)
    solver = BlackBoxSolverNSGAII(problem)
    print("[OK] Class instantiation successful")
except Exception as e:
    print(f"[FAIL] Instantiation failed: {e}")

print("\nImport tests completed!")