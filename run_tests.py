#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run import tests with proper package setup"""

import sys
import os

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

print(f"Project root: {project_root}")
print(f"Python path: {sys.path[0]}")

print("\nTest 1: Test core module imports")
try:
    # Import through absolute imports from project root
    from core.solver import BlackBoxSolverNSGAII
    from core.problems import SphereBlackBox
    from utils.visualization import SolverVisualizationMixin
    from utils.bias import BiasModule
    from solvers.nsga2 import BlackBoxSolverNSGAII as SolverNSGAII
    print("[OK] All imports successful")
except ImportError as e:
    print(f"[FAIL] Import failed: {e}")
    import traceback
    traceback.print_exc()

print("\nTest 2: Test example can run (checking imports only)")
try:
    # Test that examples can import modules correctly
    exec("""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath('__file__'))))

from core.base import BlackBoxProblem
from core.solver import BlackBoxSolverNSGAII
from utils.bias import BiasModule
from solvers.nsga2 import BlackBoxSolverNSGAII
print("[OK] Example imports successful")
""")
except ImportError as e:
    print(f"[FAIL] Example imports failed: {e}")

print("\nTest 3: Test class instantiation")
try:
    from core.problems import SphereBlackBox
    from core.solver import BlackBoxSolverNSGAII

    # Create a simple test problem
    problem = SphereBlackBox(dimension=2)
    solver = BlackBoxSolverNSGAII(problem)
    print("[OK] Classes can be instantiated")
except Exception as e:
    print(f"[FAIL] Instantiation failed: {e}")

print("\nTest 4: Test package init imports")
try:
    import core
    import utils
    import solvers
    import ml
    import meta
    print("[OK] All packages can be imported")
except ImportError as e:
    print(f"[FAIL] Package import failed: {e}")

print("\nAll tests completed!")