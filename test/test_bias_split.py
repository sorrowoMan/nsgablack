#!/usr/bin/env python3
"""
Test script for the split bias library
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import numpy as np

def test_bias_imports():
    """Test that all imports work correctly"""
    print("Testing imports...")

    try:
        from bias_v2 import UniversalBiasManager
        print("[OK] UniversalBiasManager imported successfully")

        from bias_library_algorithmic import DiversityBias, ConvergenceBias
        print("[OK] Algorithmic biases imported successfully")

        from bias_library_domain import ConstraintBias, PreferenceBias
        print("[OK] Domain biases imported successfully")

        from bias_base import OptimizationContext
        print("[OK] Base classes imported successfully")

        return True
    except Exception as e:
        print(f"[FAIL] Import failed: {e}")
        return False

def test_bias_functionality():
    """Test basic bias functionality"""
    print("\nTesting functionality...")

    try:
        # Import again for this function scope
        from bias_v2 import UniversalBiasManager
        from bias_library_algorithmic import DiversityBias
        from bias_library_domain import ConstraintBias
        from bias_base import OptimizationContext
        # Create manager
        manager = UniversalBiasManager()
        print("[OK] Manager created")

        # Create test context
        x = np.array([1.0, 2.0])
        context = OptimizationContext(generation=10, individual=x)
        print("[OK] Context created")

        # Test bias computation
        bias_value = manager.compute_total_bias(x, context)
        print(f"[OK] Bias computed: {bias_value}")

        # Test adding biases
        diversity_bias = DiversityBias(weight=0.2)
        manager.algorithmic_manager.add_bias(diversity_bias)
        print("[OK] Algorithmic bias added")

        constraint_bias = ConstraintBias(weight=1.0)
        manager.domain_manager.add_bias(constraint_bias)
        print("[OK] Domain bias added")

        # Test bias computation with biases
        new_bias_value = manager.compute_total_bias(x, context)
        print(f"[OK] New bias computed: {new_bias_value}")

        return True
    except Exception as e:
        print(f"[FAIL] Functionality test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function"""
    print("=" * 50)
    print("Bias Library Split Test")
    print("=" * 50)

    imports_ok = test_bias_imports()
    functionality_ok = test_bias_functionality()

    print("\n" + "=" * 50)
    if imports_ok and functionality_ok:
        print("[SUCCESS] ALL TESTS PASSED!")
        print("[SUCCESS] Bias library split successful!")
        print("[SUCCESS] All modules working correctly!")
    else:
        print("[FAIL] Some tests failed!")
    print("=" * 50)

if __name__ == "__main__":
    main()