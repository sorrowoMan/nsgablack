#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Simple test to check imports"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Testing imports...")

# Test if we can import from packages
try:
    # This will test if our imports work
    exec("""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Try importing like an example would
from core.base import BlackBoxProblem
print("Imported BlackBoxProblem")

from core.solver import BlackBoxSolverNSGAII
print("Imported BlackBoxSolverNSGAII")

from utils.bias import BiasModule
print("Imported BiasModule")

from solvers.nsga2 import BlackBoxSolverNSGAII as NSGA2
print("Imported NSGA2 from solvers")

print("All imports successful!")
""")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()