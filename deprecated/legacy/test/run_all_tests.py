"""
Run all tests for nsgablack
"""

import unittest
import sys
import os
from io import StringIO

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import all test modules
try:
    from test_core import TestCore, TestDifferentProblems
    from test_bias import TestBiasBase, TestAlgorithmicBias, TestDomainBias, TestBiasModule, TestBiasIntegration
    from test_solvers import TestNSGA2, TestSolverIntegration
except ImportError as e:
    print(f"Error importing test modules: {e}")
    print("Please ensure you're running tests from the nsgablack directory")
    sys.exit(1)


def run_tests(verbosity=2):
    """Run all tests and return results"""

    # Create test suite
    test_suite = unittest.TestSuite()

    # Add test cases
    test_classes = [
        TestCore,
        TestDifferentProblems,
        TestBiasBase,
        TestAlgorithmicBias,
        TestDomainBias,
        TestBiasModule,
        TestBiasIntegration,
        TestNSGA2,
        TestSolverIntegration
    ]

    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)

    # Run tests
    runner = unittest.TextTestRunner(
        verbosity=verbosity,
        stream=sys.stdout,
        buffer=True
    )

    result = runner.run(test_suite)

    return result


def run_quick_tests():
    """Run a quick subset of tests for development"""
    quick_suite = unittest.TestSuite()

    # Add only core tests for quick check
    quick_classes = [
        TestCore,
        TestNSGA2
    ]

    for test_class in quick_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        quick_suite.addTests(tests)

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(quick_suite)

    return result


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Run nsgablack tests')
    parser.add_argument('--quick', action='store_true', help='Run only quick tests')
    parser.add_argument('--coverage', action='store_true', help='Run with coverage report')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')

    args = parser.parse_args()

    if args.coverage:
        try:
            import coverage
            cov = coverage.Coverage()
            cov.start()

            print("Running tests with coverage...")
            result = run_tests(verbosity=2 if args.verbose else 1)

            cov.stop()
            cov.save()

            print("\nCoverage Report:")
            cov.report()

            # Generate HTML report
            cov.html_report(directory='htmlcov')
            print("\nHTML coverage report generated in htmlcov/")

        except ImportError:
            print("Coverage package not installed. Install with: pip install coverage")
            result = run_tests(verbosity=2 if args.verbose else 1)
    elif args.quick:
        print("Running quick tests...")
        result = run_quick_tests()
    else:
        print("Running all tests...")
        result = run_tests(verbosity=2 if args.verbose else 1)

    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)