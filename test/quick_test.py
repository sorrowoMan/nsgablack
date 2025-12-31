#!/usr/bin/env python3
"""
Quick test runner for nsgablack
"""

import sys
import os
import numpy as np

# Add parent directory to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

print(f"Project root: {project_root}")

def test_imports():
    """Test basic imports"""
    print("\n" + "="*50)
    print("Testing Basic Imports")
    print("="*50)

    tests = [
        ("Core modules", ["core.problems", "core.solver", "core.base"]),
        ("Solver modules", ["solvers.nsga2"]),
        ("Bias modules", ["bias.bias_base", "bias.bias"]),
        ("Utils modules", ["utils.visualization", "utils.parallel_evaluator"]),
    ]

    passed = 0
    total = 0

    for category, modules in tests:
        print(f"\n{category}:")
        for module in modules:
            total += 1
            try:
                __import__(module)
                print(f"  [OK] {module}")
                passed += 1
            except ImportError as e:
                print(f"  [FAIL] {module}: {e}")

    print(f"\nImport tests: {passed}/{total} passed")
    return passed == total

def test_basic_functionality():
    """Test basic functionality"""
    print("\n" + "="*50)
    print("Testing Basic Functionality")
    print("="*50)

    try:
        # Test problem creation
        from core.problems import ZDT1BlackBox
        problem = ZDT1BlackBox(dimension=10)
        print("[OK] ZDT1BlackBox problem created")

        # Test solver creation
        from core.solver import BlackBoxSolverNSGAII
        solver = BlackBoxSolverNSGAII(problem)
        print("[OK] BlackBoxSolverNSGAII solver created")

        # Test basic evaluation
        x = np.random.random(10)
        objectives = problem.evaluate(x)
        print(f"[OK] Problem evaluation: {len(objectives)} objectives")

        # Test short optimization run
        solver.pop_size = 10
        solver.max_generations = 3

        print("[RUNNING] Short optimization test...")
        result = solver.run()

        if 'pareto_solutions' in result and len(result['pareto_solutions']) > 0:
            print(f"[OK] Optimization completed: {len(result['pareto_solutions'])} Pareto solutions")
            return True
        else:
            print("[FAIL] Optimization failed: No Pareto solutions found")
            return False

    except Exception as e:
        print(f"[FAIL] Basic functionality test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_bias_system():
    """Test bias system"""
    print("\n" + "="*50)
    print("Testing Bias System")
    print("="*50)

    try:
        from bias.bias_base import BaseBias, AlgorithmicBias, DomainBias
        print("[OK] Base bias classes imported")

        from bias.bias_library_algorithmic import DiversityBias, ConvergenceBias
        print("[OK] Algorithmic bias classes imported")

        from bias.bias_library_domain import ConstraintBias, PreferenceBias
        print("[OK] Domain bias classes imported")

        # Note: UniversalBiasManager is in bias_v2.py which is not used anymore
        # Testing basic bias functionality instead
        from bias.bias import BiasModule
        print("[OK] BiasModule imported")

        # Test bias creation
        bias = DiversityBias(weight=0.5)
        print("[OK] DiversityBias created")

        # Test bias module
        bias_module = BiasModule()
        print("[OK] BiasModule created")

        return True

    except Exception as e:
        print(f"[FAIL] Bias system test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all quick tests"""
    print("nsgablack Quick Test Suite")
    print("="*50)

    results = []

    # Run tests
    results.append(("Imports", test_imports()))
    results.append(("Basic Functionality", test_basic_functionality()))
    results.append(("Bias System", test_bias_system()))

    # Summary
    print("\n" + "="*50)
    print("Test Summary")
    print("="*50)

    passed = 0
    total = len(results)

    for test_name, result in results:
        status = "PASSED" if result else "FAILED"
        print(f"{test_name:20} {status}")
        if result:
            passed += 1

    print(f"\nOverall: {passed}/{total} test suites passed")

    if passed == total:
        print("\nAll tests passed! nsgablack is working correctly.")
        return 0
    else:
        print("\nSome tests failed. Please check the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())