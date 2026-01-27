#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Run all tests for nsgablack project
"""

import sys
import os

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

print(f"Project root: {project_root}")

# Import and run comprehensive tests
try:
    from run_all_tests import run_tests

    print("\n" + "="*60)
    print("Running Comprehensive Test Suite")
    print("="*60 + "\n")

    result = run_tests(verbosity=2)

    if result.wasSuccessful():
        print("\n✅ All tests passed successfully!")
    else:
        print(f"\n❌ Tests failed: {len(result.failures)} failures, {len(result.errors)} errors")

        if result.failures:
            print("\nFailures:")
            for test, traceback in result.failures:
                print(f"  - {test}: {traceback.split('AssertionError:')[-1].strip()}")

        if result.errors:
            print("\nErrors:")
            for test, traceback in result.errors:
                print(f"  - {test}: {traceback.split('Exception:')[-1].strip()}")

    sys.exit(0 if result.wasSuccessful() else 1)

except ImportError as e:
    print(f"Could not import test modules: {e}")
    print("\nRunning basic import test instead...")

    # Fallback to basic import test
    print("\n" + "="*60)
    print("Running Basic Import Tests")
    print("="*60 + "\n")

    tests_passed = 0
    total_tests = 4

    # Test 1: Core module imports
    print("Test 1: Core module imports")
    try:
        from core.solver import BlackBoxSolverNSGAII
        from core.problems import ZDT1BlackBox
        from core.base import BlackBoxProblem
        print("[✅] Core modules imported successfully")
        tests_passed += 1
    except ImportError as e:
        print(f"[❌] Core module import failed: {e}")

    # Test 2: Solver imports
    print("\nTest 2: Solver imports")
    try:
        from solvers.nsga2 import BlackBoxSolverNSGAII as NSGA2Solver
        print("[✅] Solvers imported successfully")
        tests_passed += 1
    except ImportError as e:
        print(f"[❌] Solver import failed: {e}")

    # Test 3: Bias system imports
    print("\nTest 3: Bias system imports")
    try:
        from bias.bias_base import BaseBias, AlgorithmicBias, DomainBias
        from bias.bias import UniversalBiasManager
        print("[✅] Bias system imported successfully")
        tests_passed += 1
    except ImportError as e:
        print(f"[❌] Bias system import failed: {e}")

    # Test 4: Utils imports
    print("\nTest 4: Utils imports")
    try:
        from utils.visualization import SolverVisualizationMixin
        from utils.parallel_evaluator import ParallelEvaluator
        print("[✅] Utils imported successfully")
        tests_passed += 1
    except ImportError as e:
        print(f"[❌] Utils import failed: {e}")

    # Summary
    print("\n" + "="*60)
    print(f"Basic Import Tests: {tests_passed}/{total_tests} passed")
    if tests_passed == total_tests:
        print("✅ All basic imports working!")
        sys.exit(0)
    else:
        print("❌ Some imports failed")
        sys.exit(1)