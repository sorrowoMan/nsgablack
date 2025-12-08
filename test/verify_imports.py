#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify package imports work correctly with proper setup"""

import subprocess
import sys
import os

def run_test(test_code, description):
    """Run a test in a subprocess to ensure clean environment"""
    print(f"\n{description}")
    print("-" * 50)

    # Create a temporary test script
    test_file = "temp_test.py"
    with open(test_file, "w", encoding="utf-8") as f:
        f.write(f"""
import sys
import os
sys.path.insert(0, r'{os.path.dirname(os.path.abspath(__file__))}')
{test_code}
""")

    try:
        result = subprocess.run([sys.executable, test_file],
                              capture_output=True, text=True, encoding='utf-8')
        if result.returncode == 0:
            print(result.stdout.strip())
            print("[OK] Test passed")
        else:
            print(result.stdout.strip())
            print(result.stderr.strip())
            print("[FAIL] Test failed")
    finally:
        # Clean up
        if os.path.exists(test_file):
            os.remove(test_file)

# Test 1: Test basic imports
test1_code = """
try:
    from core.solver import BlackBoxSolverNSGAII
    from utils.visualization import SolverVisualizationMixin
    from solvers.nsga2 import BlackBoxSolverNSGAII as SolverNSGA2
    print("Basic imports successful")
except ImportError as e:
    print(f"Import error: {{e}}")
"""

run_test(test1_code, "Test 1: Basic imports")

# Test 2: Test package structure with -m flag
print("\nTest 2: Package structure test (using python -m)")
print("-" * 50)
result = subprocess.run([sys.executable, "-c",
                        "import sys; sys.path.insert(0, '.'); import core"],
                       capture_output=True, text=True, encoding='utf-8')
if result.returncode == 0:
    print("[OK] Package import successful")
else:
    print("[FAIL] Package import failed")
    print(result.stderr)

# Test 3: Test that examples can run
print("\nTest 3: Example test")
print("-" * 50)
example_test = """
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# This should work for examples
print("Testing example-style imports...")
try:
    from core.base import BlackBoxProblem
    from core.solver import BlackBoxSolverNSGAII
    from bias import BiasModule
    from solvers.nsga2 import BlackBoxSolverNSGAII
    print("Example-style imports successful")
except ImportError as e:
    print(f"Example import error: {{e}}")
"""

run_test(example_test, "Test 3: Example imports")

print("\n" + "=" * 50)
print("Verification complete!")