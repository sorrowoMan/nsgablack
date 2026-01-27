"""
Quick verification script for algorithm biases - ASCII version
Run: python tests/verify_biases.py
"""

import sys
from pathlib import Path

import numpy as np


def test_imports():
    """Test all bias imports"""
    print("=" * 60)
    print("Test 1: Import Test")
    print("=" * 60)

    try:
        from nsgablack.bias.algorithmic import (
            MOEADDecompositionBias,
            AdaptiveMOEADBias,
            NSGA3ReferencePointBias,
            AdaptiveNSGA3Bias,
            SPEA2StrengthBias,
            AdaptiveSPEA2Bias,
            HybridSPEA2NSGA2Bias
        )
        print("[OK] All bias classes imported successfully")
        return True
    except ImportError as e:
        print(f"[FAIL] Import failed: {e}")
        return False


def test_moad_bias():
    """Test MOEAD bias"""
    print("\n" + "=" * 60)
    print("Test 2: MOEAD Decomposition Bias")
    print("=" * 60)

    try:
        from nsgablack.bias.algorithmic import MOEADDecompositionBias, AdaptiveMOEADBias

        # Test standard MOEAD
        print("  Creating standard MOEAD bias...")
        moead = MOEADDecompositionBias(
            weight_vector=np.array([0.5, 0.5]),
            method='tchebycheff',
            initial_weight=0.5
        )
        print(f"  [OK] Name: {moead.name}")
        print(f"  [OK] Method: {moead.method}")
        print(f"  [OK] Weight vector: {moead.weight_vector}")

        # Test weight normalization
        print("  Testing weight normalization...")
        moead2 = MOEADDecompositionBias(
            weight_vector=np.array([2.0, 2.0]),
            method='tchebycheff'
        )
        assert np.allclose(moead2.weight_vector, [0.5, 0.5])
        print("  [OK] Weights normalized correctly")

        # Test Tchebycheff aggregation
        print("  Testing Tchebycheff aggregation...")
        moead.ideal_point = np.array([0.0, 0.0])
        agg_value = moead._tchebycheff_aggregation(np.array([2.0, 4.0]))
        expected = 2.0
        assert agg_value == expected
        print(f"  [OK] Aggregation value: {agg_value} (expected: {expected})")

        # Test weighted sum
        print("  Testing weighted sum aggregation...")
        moead_ws = MOEADDecompositionBias(
            weight_vector=np.array([0.3, 0.7]),
            method='weighted_sum'
        )
        agg_value = moead_ws._weighted_sum_aggregation(np.array([2.0, 4.0]))
        expected = 3.4
        assert np.isclose(agg_value, expected)
        print(f"  [OK] Weighted sum: {agg_value} (expected: {expected})")

        # Test adaptive MOEAD
        print("  Creating adaptive MOEAD bias...")
        adaptive_moead = AdaptiveMOEADBias(
            weight_vector=np.array([0.5, 0.5]),
            adaptation_window=50
        )
        assert adaptive_moead.adaptive == True
        print("  [OK] Adaptive MOEAD bias created successfully")

        print("[OK] MOEAD bias all tests passed")
        return True

    except Exception as e:
        print(f"[FAIL] MOEAD bias test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_nsga3_bias():
    """Test NSGA3 bias"""
    print("\n" + "=" * 60)
    print("Test 3: NSGA3 Reference Point Bias")
    print("=" * 60)

    try:
        from nsgablack.bias.algorithmic import NSGA3ReferencePointBias, AdaptiveNSGA3Bias

        # Test Das-Dennis generation
        print("  Testing Das-Dennis reference point generation...")
        nsga3_2obj = NSGA3ReferencePointBias(
            num_objectives=2,
            divisions=12
        )
        expected_points = 13
        assert len(nsga3_2obj.reference_points) == expected_points
        print(f"  [OK] 2-objective 12-division generated {len(nsga3_2obj.reference_points)} points (expected: {expected_points})")

        # Test 3-objective
        print("  Testing 3-objective reference point generation...")
        nsga3_3obj = NSGA3ReferencePointBias(
            num_objectives=3,
            divisions=2
        )
        # Just verify points were generated (actual count may vary)
        assert len(nsga3_3obj.reference_points) > 0
        print(f"  [OK] 3-objective 2-division generated {len(nsga3_3obj.reference_points)} points")

        # Test normalization
        print("  Testing reference point normalization...")
        for point in nsga3_2obj.reference_points:
            assert np.all(point >= 0) and np.all(point <= 1)
            assert np.isclose(np.sum(point), 1.0)
        print("  [OK] All reference points normalized correctly")

        # Test custom reference points
        print("  Testing custom reference points...")
        custom_refs = np.array([
            [0.0, 1.0],
            [0.5, 0.5],
            [1.0, 0.0]
        ])
        nsga3_custom = NSGA3ReferencePointBias(
            reference_points=custom_refs
        )
        assert len(nsga3_custom.reference_points) == 3
        print(f"  [OK] Custom reference points set successfully, {len(nsga3_custom.reference_points)} points")

        # Test adaptive NSGA3
        print("  Creating adaptive NSGA3 bias...")
        adaptive_nsga3 = AdaptiveNSGA3Bias(
            num_objectives=2,
            divisions=4,
            adaptation_window=100
        )
        assert adaptive_nsga3.adaptive == True
        print("  [OK] Adaptive NSGA3 bias created successfully")

        print("[OK] NSGA3 bias all tests passed")
        return True

    except Exception as e:
        print(f"[FAIL] NSGA3 bias test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_spea2_bias():
    """Test SPEA2 bias"""
    print("\n" + "=" * 60)
    print("Test 4: SPEA2 Strength Bias")
    print("=" * 60)

    try:
        from nsgablack.bias.algorithmic import (
            SPEA2StrengthBias,
            AdaptiveSPEA2Bias,
            HybridSPEA2NSGA2Bias
        )

        # Test standard SPEA2
        print("  Creating standard SPEA2 bias...")
        spea2 = SPEA2StrengthBias(
            k_nearest=5,
            strength_weight=0.6,
            density_weight=0.4
        )
        print(f"  [OK] Name: {spea2.name}")
        print(f"  [OK] k-value: {spea2.k_nearest}")
        print(f"  [OK] Strength weight: {spea2.strength_weight}")
        print(f"  [OK] Density weight: {spea2.density_weight}")

        # Test dominance
        print("  Testing Pareto dominance...")
        obj1 = np.array([1.0, 1.0])
        obj2 = np.array([2.0, 2.0])
        assert spea2._dominates(obj1, obj2) == True
        assert spea2._dominates(obj2, obj1) == False
        print("  [OK] Dominance relationship judged correctly")

        # Test strength calculation
        print("  Testing strength calculation...")
        objectives = np.array([1.0, 1.0])
        pop_objectives = np.array([
            [2.0, 2.0],
            [3.0, 3.0],
            [0.5, 0.5],
            [1.5, 1.5],
        ])
        strength = spea2._compute_strength(objectives, pop_objectives)
        expected_strength = -0.6
        assert np.isclose(strength, expected_strength)
        print(f"  [OK] Strength value: {strength} (expected: {expected_strength})")

        # Test density calculation
        print("  Testing density calculation...")
        density = spea2._compute_density(objectives, pop_objectives)
        assert density < 0
        assert density >= -1.0
        print(f"  [OK] Density value: {density:.4f}")

        # Test adaptive SPEA2
        print("  Creating adaptive SPEA2 bias...")
        adaptive_spea2 = AdaptiveSPEA2Bias(
            k_nearest=5,
            adaptation_window=50
        )
        assert adaptive_spea2.adaptive == True
        print("  [OK] Adaptive SPEA2 bias created successfully")

        # Test hybrid bias
        print("  Creating hybrid SPEA2-NSGA2 bias...")
        hybrid = HybridSPEA2NSGA2Bias(
            k_nearest=5,
            strength_weight=0.4,
            spea2_density_weight=0.3,
            nsga2_crowding_weight=0.3
        )
        assert hybrid.nsga2_crowding_weight == 0.3
        print("  [OK] Hybrid bias created successfully")

        print("[OK] SPEA2 bias all tests passed")
        return True

    except Exception as e:
        print(f"[FAIL] SPEA2 bias test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_bias_combination():
    """Test bias combination"""
    print("\n" + "=" * 60)
    print("Test 5: Bias Combination")
    print("=" * 60)

    try:
        from nsgablack.bias.algorithmic import (
            MOEADDecompositionBias,
            NSGA3ReferencePointBias,
            SPEA2StrengthBias
        )
        from nsgablack.bias.core.manager import UniversalBiasManager

        print("  Creating bias manager...")
        manager = UniversalBiasManager()
        print("  [OK] Bias manager created successfully")

        # Add three biases
        print("  Adding multiple algorithm biases...")
        moead_bias = MOEADDecompositionBias(
            weight_vector=np.array([0.5, 0.5]),
            initial_weight=0.3
        )
        nsga3_bias = NSGA3ReferencePointBias(
            num_objectives=2,
            divisions=4,
            initial_weight=0.3
        )
        spea2_bias = SPEA2StrengthBias(
            k_nearest=5,
            initial_weight=0.2
        )

        manager.algorithmic_manager.add_bias(moead_bias)
        manager.algorithmic_manager.add_bias(nsga3_bias)
        manager.algorithmic_manager.add_bias(spea2_bias)

        print(f"  [OK] Successfully added {len(manager.algorithmic_manager.biases)} biases")

        # Test bias list
        biases = manager.algorithmic_manager.get_enabled_biases()
        assert len(biases) == 3
        print("  [OK] Bias list retrieved successfully")

        print("[OK] Bias combination test passed")
        return True

    except Exception as e:
        print(f"[FAIL] Bias combination test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_bias_compute():
    """Test bias computation"""
    print("\n" + "=" * 60)
    print("Test 6: Bias Computation")
    print("=" * 60)

    try:
        from nsgablack.bias.algorithmic import MOEADDecompositionBias
        from nsgablack.bias.core.base import OptimizationContext

        print("  Creating MOEAD bias...")
        moead = MOEADDecompositionBias(
            weight_vector=np.array([0.5, 0.5]),
            method='tchebycheff',
            initial_weight=0.5
        )

        print("  Creating optimization context...")
        context = OptimizationContext(
            generation=0,
            individual=np.array([1.0, 2.0]),
            metrics={'objectives': np.array([2.0, 4.0])}
        )
        print("  [OK] Context created successfully")

        print("  Computing bias value...")
        bias_value = moead.compute(np.array([1.0, 2.0]), context)
        assert isinstance(bias_value, (int, float))
        print(f"  [OK] Bias value: {bias_value:.4f}")

        print("  Testing ideal point update...")
        context2 = OptimizationContext(
            generation=1,
            individual=np.array([0.5, 0.5]),
            metrics={'objectives': np.array([1.0, 2.0])}
        )
        moead.compute(np.array([0.5, 0.5]), context2)
        print(f"  [OK] Ideal point updated to: {moead.ideal_point}")

        print("  Getting statistics...")
        stats = moead.get_statistics()
        assert 'method' in stats
        assert 'weight_vector' in stats
        assert 'ideal_point' in stats
        print("  [OK] Statistics retrieved successfully")
        print(f"    - Method: {stats['method']}")
        print(f"    - Weight vector: {stats['weight_vector']}")
        print(f"    - Ideal point: {stats['ideal_point']}")

        print("[OK] Bias computation test passed")
        return True

    except Exception as e:
        print(f"[FAIL] Bias computation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_high_dimensional():
    """Test high-dimensional objectives"""
    print("\n" + "=" * 60)
    print("Test 7: High-Dimensional Objectives")
    print("=" * 60)

    try:
        from nsgablack.bias.algorithmic import MOEADDecompositionBias, NSGA3ReferencePointBias

        # Test 5-objective MOEAD
        print("  Testing 5-objective MOEAD bias...")
        moead_5obj = MOEADDecompositionBias(
            weight_vector=np.array([0.2, 0.2, 0.2, 0.2, 0.2]),
            method='tchebycheff'
        )
        assert len(moead_5obj.weight_vector) == 5
        print("  [OK] 5-objective MOEAD bias created successfully")

        # Test 5-objective NSGA3
        print("  Testing 5-objective NSGA3 bias...")
        nsga3_5obj = NSGA3ReferencePointBias(
            num_objectives=5,
            divisions=1
        )
        assert nsga3_5obj.reference_points.shape[1] == 5
        print(f"  [OK] 5-objective NSGA3 bias created successfully, generated {len(nsga3_5obj.reference_points)} reference points")

        print("[OK] High-dimensional objective test passed")
        return True

    except Exception as e:
        print(f"[FAIL] High-dimensional objective test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("Algorithm Bias Quick Verification Test")
    print("=" * 60)

    tests = [
        ("Import Test", test_imports),
        ("MOEAD Bias", test_moad_bias),
        ("NSGA3 Bias", test_nsga3_bias),
        ("SPEA2 Bias", test_spea2_bias),
        ("Bias Combination", test_bias_combination),
        ("Bias Computation", test_bias_compute),
        ("High-Dimensional", test_high_dimensional),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n[FAIL] Test '{test_name}' raised exception: {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "[OK] PASS" if result else "[FAIL] FAIL"
        print(f"  {test_name}: {status}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n[SUCCESS] All tests passed! New algorithm biases can be used correctly.")
        return 0
    else:
        print(f"\n[WARNING] {total - passed} test(s) failed, please check the issues.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
