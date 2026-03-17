#
# This file is part of the Cardinal Optimizer, all rights reserved.
#

'''
Using the matrix modeling API to solve the transport problem: 
Coefficients:
    C = [[39, 14, 11, 14, 16, 82,  8],
         [27,  9, 12,  9, 26, 95, 17],
         [24, 14, 17, 13, 28, 99, 20]] 
    s = [1400, 2600, 2900]^T
    d = [900, 1200, 600, 400, 1700, 1100, 1000]^T
    e1 is ones(7)
    e2 is ones(3)
Obj: 
    minimize <C, X>
s.t. 
    X * e1 <= s
    X^T * e2 >= d
Bounds: 
    X >= 0
'''

import coptpy as cp
from coptpy import COPT
import numpy as np

# Create environment
env = cp.Envr()

# Create model
model = env.createModel(name="transport")

# Build supply and demand constriant bound vector
supply = np.array([1400, 2600, 2900])
demand = np.array([900, 1200, 600, 400, 1700, 1100, 1000])

m = len(supply)
n = len(demand)

# Add 2-D array MVar variables
transport = model.addMVar(shape=(m, n), nameprefix="city")

# Add supply constraints by MLinExpr Builder: X e1 <= s
model.addConstrs(transport @ np.ones(n) <= supply)

# Add demand constraints by MLinExpr Builder: X^T e2 >= d
model.addConstrs(np.ones(m) @ transport >= demand)

# Set matrix objective function: minimize <C, X>
cost = np.array([[39, 14, 11, 14, 16, 82, 8], [27, 9, 12, 9, 26, 95, 17],
                 [24, 14, 17, 13, 28, 99, 20]])
model.setObjective((cost * transport).sum(), sense=COPT.MINIMIZE)

# Solve the problem
model.solve()

# Analyze solutions
if model.status == COPT.OPTIMAL:
    print("\nObjective value: {:.4f}".format(model.objval))

    allvars = model.getVars()
    print("\nVariable solution:\n")
    for var in allvars:
        print("{0}: {1:4f}".format(var.name, var.x))

    print("\nVariable basis status:\n")
    for var in allvars:
        print("{0}: {1}".format(var.name, var.basis))
