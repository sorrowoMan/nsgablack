#
# This file is part of the Cardinal Optimizer, all rights reserved.
#

'''
Using the matrix modeling API to solve the diet problem: 
Coefficients:
    c = [3.19, 2.59, 2.29, 2.89, 1.89, 1.99, 1.99, 2.49]
    A = [[60, 20, 10, 15],
         [ 8,  0, 20, 20],
         [ 8, 10, 15, 10],
         [40, 40, 35, 10],
         [15, 35, 15, 15],
         [ 0, 30, 15, 15],
         [25, 50, 25, 15],
         [60, 20, 15, 10]] 
Obj: 
    minimize c^T * x
s.t. 
    700 <= A * x <= 10000
Bounds: 
    x >= 0
'''

import coptpy as cp
from coptpy import COPT
import numpy as np

# Create COPT environment
env = cp.Envr()

# Create COPT model
model = env.createModel('diet_matrix')

# Load coefficient matrix
A = np.array([[60, 20, 10, 15], [8, 0, 20, 20], [8, 10, 15, 10],
              [40, 40, 35, 10], [15, 35, 15, 15], [0, 30, 15, 15],
              [25, 50, 25, 15], [60, 20, 15, 10]]).T

# Add 1-D array MVar variables
x = model.addMVar(shape=A.shape[1], nameprefix='food')

# Build lower and upper bound nutrition requirement vector
nuri_upper = np.full(4, 10000)
nuri_lower = np.full(4, 700)

# Add nutrition upper bound MConstr by MLinExpr Builder: A * x <= 10000
c1 = model.addConstrs(A @ x <= nuri_upper)

# Add nutrition lower bound MConstr by specific function: A * x >= 700
c2 = model.addMConstr(A, x, 'G', nuri_lower, nameprefix='c')

# Set matrix objective function: minimize c^Tx
cost = np.array([3.19, 2.59, 2.29, 2.89, 1.89, 1.99, 1.99, 2.49])
model.setObjective(cost @ x, sense=COPT.MINIMIZE)

# Solve the model
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
