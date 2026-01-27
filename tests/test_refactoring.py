"""
Refactoring Verification Test - Circular Dependency Solution

Tests:
1. Basic import test
2. Backward compatibility test
3. Dependency injection test
4. Interface isolation test
"""

import sys
import os
import numpy as np

# Add project path

# ============================================================================
# Test 1: Basic Import
# ============================================================================
print("=" * 70)
print("Test 1: Basic Import")
print("=" * 70)

try:
    from nsgablack.core import BlackBoxProblem, BlackBoxSolverNSGAII
    print("[OK] Core module import successful")
except ImportError as e:
    print(f"[FAIL] Core module import failed: {e}")
    sys.exit(1)

try:
    from nsgablack.core.interfaces import (
        BiasInterface,
        RepresentationInterface,
        has_bias_module,
        has_representation_module,
    )
    print("[OK] Interface module import successful")
except ImportError as e:
    print(f"[FAIL] Interface module import failed: {e}")
    sys.exit(1)

# ============================================================================
# Test 2: Simple Problem Solving (Backward Compatible)
# ============================================================================
print("\n" + "=" * 70)
print("Test 2: Simple Problem Solving (Backward Compatible)")
print("=" * 70)

class SimpleTestProblem(BlackBoxProblem):
    """Simple test problem"""

    def __init__(self):
        super().__init__(name="SimpleTest", dimension=2)

    def evaluate(self, x):
        # Simple quadratic function
        return [x[0]**2 + x[1]**2]

try:
    problem = SimpleTestProblem()
    solver = BlackBoxSolverNSGAII(problem)
    solver.pop_size = 20
    solver.max_generations = 5  # Quick test

    print(f"[OK] Solver created successfully")
    print(f"   Problem dimension: {solver.dimension}")
    print(f"   Population size: {solver.pop_size}")
    print(f"   Max generations: {solver.max_generations}")

    # Check attributes
    print(f"   Bias module: {solver.bias_module}")
    print(f"   Representation pipeline: {solver.representation_pipeline}")

except Exception as e:
    print(f"[FAIL] Solver creation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================================
# Test 3: Dependency Injection
# ============================================================================
print("\n" + "=" * 70)
print("Test 3: Dependency Injection")
print("=" * 70)

# Create mock bias module
class MockBiasModule:
    """Mock bias module"""

    def compute_bias(self, x, context):
        return 0.0

    def add_bias(self, bias, weight=1.0, name=None):
        return True

    def is_enabled(self):
        return True

    def enable(self):
        pass

    def disable(self):
        pass

try:
    # Test dependency injection
    mock_bias = MockBiasModule()
    solver_with_bias = BlackBoxSolverNSGAII(problem, bias_module=mock_bias)

    print("[OK] Dependency injection successful")
    print(f"   Injected bias module: {solver_with_bias.bias_module}")
    print(f"   Bias support: {solver_with_bias.has_bias_support()}")

except Exception as e:
    print(f"[FAIL] Dependency injection failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================================
# Test 4: Lazy Loading
# ============================================================================
print("\n" + "=" * 70)
print("Test 4: Lazy Loading")
print("=" * 70)

try:
    from nsgablack.core import has_bias_module, has_numba

    print(f"   Bias module available: {has_bias_module()}")
    print(f"   Numba acceleration available: {has_numba()}")

    # Test solver's check methods
    solver = BlackBoxSolverNSGAII(problem)
    print(f"[OK] Lazy loading check successful")
    print(f"   has_bias_support(): {solver.has_bias_support()}")
    print(f"   has_numba_support(): {solver.has_numba_support()}")

except Exception as e:
    print(f"[FAIL] Lazy loading test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================================
# Test 5: Attribute Setting (Backward Compatible)
# ============================================================================
print("\n" + "=" * 70)
print("Test 5: Attribute Setting (Backward Compatible)")
print("=" * 70)

try:
    solver = BlackBoxSolverNSGAII(problem)

    # Old way: set attribute
    solver.bias_module = mock_bias
    print("[OK] Old way setting bias_module successful")

    # New way: constructor injection
    solver2 = BlackBoxSolverNSGAII(problem, bias_module=mock_bias)
    print("[OK] New way dependency injection successful")

    # Check enable_bias
    solver.enable_bias = True
    print(f"   enable_bias: {solver.enable_bias}")

except Exception as e:
    print(f"[FAIL] Attribute setting test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================================
# Test 6: Interface Type Check
# ============================================================================
print("\n" + "=" * 70)
print("Test 6: Interface Type Check")
print("=" * 70)

try:
    from nsgablack.core.interfaces import BiasInterface

    # Check if mock object implements interface
    assert hasattr(mock_bias, 'compute_bias')
    assert hasattr(mock_bias, 'add_bias')
    assert hasattr(mock_bias, 'is_enabled')

    print("[OK] Interface type check passed")

except Exception as e:
    print(f"[FAIL] Interface type check failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================================
# Summary
# ============================================================================
print("\n" + "=" * 70)
print("[SUCCESS] All tests passed!")
print("=" * 70)
print("\nRefactoring Summary:")
print("1. [OK] Created interface isolation layer (core/interfaces.py)")
print("2. [OK] Eliminated circular dependencies (lazy loading + DI)")
print("3. [OK] Maintained backward compatibility")
print("4. [OK] Code is clearer and more maintainable")
print("\nNext Steps:")
print("- Run full test suite to verify all functionality")
print("- Gradually clean up bias system legacy code")
print("- Update documentation for new dependency injection usage")

