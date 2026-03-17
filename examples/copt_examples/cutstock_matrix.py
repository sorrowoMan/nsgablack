#
# This file is part of the Cardinal Optimizer, all rights reserved.
#

'''
Using the matrix modeling API to solve the cutstock problem: 
Coefficients:
    d = [50, 36, 24, 8, 30]^T
    w = [25, 40, 50, 55, 70]^T
    W = 115
    e is ones(200)
Obj: 
    minimize e^T*y
s.t. 
    X * e >= d
    X^T * w >= W y
    y[:-1] >= y[1:]
Bounds: 
    X >= 0 and integer
    y binary
'''

import coptpy as cp
from coptpy import COPT
import numpy as np

# Load data
rollwidth = 115
rollsize = [25, 40, 50, 55, 70]
rolldemand = [50, 36, 24, 8, 30]
nkind = len(rollsize)
ndemand = 200

# Create COPT environment
env = cp.Envr()

# Create COPT model
mcut = env.createModel()

# Add 2-D array MVar integer variables
ncut = mcut.addMVar(shape=(nkind, ndemand),
                    vtype=COPT.INTEGER,
                    nameprefix='ncut')

# Add 1-D array MVar binary variables
ifcut = mcut.addMVar(shape=ndemand, vtype=COPT.BINARY, nameprefix='c')

# Add demand constraints by MLinExpr Builder: X * e >= d
mcut.addConstrs(ncut @ np.ones(ndemand) >= rolldemand)

# Add rollwidth constraints by MLinExpr Builder: X^T * w >= W y
mcut.addConstrs(rollsize @ ncut <= rollwidth * ifcut)

# Add Optional constraints: Symmetry breaking constraints
mcut.addConstrs(ifcut[:-1] >= ifcut[1:])

# Set objective function: minimize e^Ty
mcut.setObjective(np.ones(ndemand) @ ifcut, COPT.MINIMIZE)

# Set optimization parameters "TimeLimit"
mcut.setParam(COPT.Param.TimeLimit, 120)

# Solve the problem
mcut.solve()

# Analyze solutions
if mcut.hasmipsol:
    print("\nBest MIP objective value: {0:.0f}".format(mcut.objval))

    print("\nCut patterns: ")
    for i in range(nkind):
        for j in range(ndemand):
            if ncut[i, j].x > 1e-6:
                print("{0:8s} = {1:.0f}".format(ncut[i, j].name, ncut[i, j].x))
