"""
Canonical CLI entry point for this case.

Usage:
    python run_solver.py
    python run_solver.py --check
"""
from .build_solver import build_solver

if __name__ == "__main__":
    solver = build_solver()
    if solver is not None:
        result = getattr(solver, "run", getattr(solver, "fit", None))
        if callable(result):
            print(result())
    else:
        print("build_solver() returned None (template)")
