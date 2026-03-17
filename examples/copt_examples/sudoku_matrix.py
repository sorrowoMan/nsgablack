#
# This file is part of the Cardinal Optimizer, all rights reserved.
#

import coptpy as cp
from coptpy import COPT
import time
import numpy as np


def solve_mip():
    print(f"=== Model and solve 'sudoku' problem with ordinary style ===")
    sol = np.zeros((9, 9), dtype=np.int32)

    # Start timer
    start = time.time()

    # Create COPT environment
    env = cp.Envr()

    # Create COPT model
    m = env.createModel("sudoku")

    # Add n-by-n-by-n binary variables; x[i, j, k] decides whether number k is placed at position (i, j)
    x = m.addVars([(i, j, k) for i in range(9) for j in range(9) for k in range(1, 10)], vtype=COPT.BINARY, nameprefix="x")

    # Maximize a constant (seeking for a feasible solution)
    m.setObjective(0, COPT.MAXIMIZE)

    # Each number shows up once in each column (summation over rows)
    m.addConstrs((cp.quicksum(x[i, j, k] for i in range(9)) == 1 for j in range(9) for k in range(1, 10)), nameprefix="col")

    # Each number shows up once in each row (summation over columns)
    m.addConstrs((cp.quicksum(x[i, j, k] for j in range(9)) == 1 for i in range(9) for k in range(1, 10)), nameprefix="row")

    # One number placed in each grid (summation over numbers)
    m.addConstrs((cp.quicksum(x[i, j, k] for k in range(1, 10)) == 1 for i in range(9) for j in range(9)), nameprefix="num")

    # Each number shows up in each sub-grid once
    m.addConstrs((cp.quicksum(x[i + i_, j + j_, k] for i_ in range(3) for j_ in range(3)) == 1
                  for i in range(0, 9, 3) for j in range(0, 9, 3) for k in range(1, 10)), nameprefix="sub")

    # Disable logging
    m.setParam(COPT.Param.Logging, 0)

    # Solve the problem
    m.solve()

    # End timer
    end = time.time()

    # Record and print solution
    for i in range(9):
        for j in range(9):
            for k in range(1, 10):
                if x[i, j, k].X > 0.9999:
                    sol[i][j] = k
    print(sol)

    print(f"Building time: {end - start - m.solvingtime}")
    print(f"Solving time : {m.solvingtime}")

def solve_mip_matrix():
    print(f"=== Model and solve 'sudoku' problem with matrix style ===")
    sol = np.zeros((9, 9), dtype=np.int32)

    # Start timer
    start = time.time()

    # Create COPT environment
    env = cp.Envr()

    # Create COPT model
    m = env.createModel("sudoku")

    # Use experimental matrix modeling feature
    m.matrixmodelmode = 'experimental'

    # Add n-by-n-by-n binary variables; x[i, j, k] decides whether number k is placed at position (i, j)
    x = m.addMVar((9, 9, 9), vtype=COPT.BINARY, nameprefix="x")

    # Maximize a constant (seeking for a feasible solution)
    m.setObjective(0, COPT.MAXIMIZE)

    # Each number shows up once in each column (summation along rows)
    m.addConstrs(x.sum(axis=0) == 1, nameprefix="col")

    # Each number shows up once in each row (summation along columns)
    m.addConstrs(x.sum(axis=1) == 1, nameprefix="row")

    # One number placed in each grid (summation along numbers)
    m.addConstrs(x.sum(axis=2) == 1, nameprefix="num")

    # Each number shows up in each sub-grid once
    for i in range(0, 9, 3):
        for j in range(0, 9, 3):
            for k in range(9):
                sub = x[i:i+3, j:j+3, k]
                m.addConstrs(sub.sum() == 1, nameprefix="sub")

    # Disable logging
    m.setParam(COPT.Param.Logging, 0)

    # Solve the problem
    m.solve()

    # End timer
    end = time.time()

    # Record and print solution
    for i in range(9):
        for j in range(9):
            for k in range(9):
                if x[i, j, k].X > 0.9999:
                    sol[i][j] = k + 1
    print(sol)

    print(f"Building time: {end - start - m.solvingtime}")
    print(f"Solving time : {m.solvingtime}")

if __name__ == '__main__':
    solve_mip()
    solve_mip_matrix()
