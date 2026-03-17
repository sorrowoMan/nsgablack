#
# This file is part of the Cardinal Optimizer, all rights reserved.
#

"""
Minimize
 obj: 2.1 x1 - 1.2 x2 + 3.2 x3 + x4 + x5 + x6 + 2 x7 + [ x2^2 ] / 2
Subject To
 r1: x1 + 2 x2 = 6
 r2: 2 x1 + x3 >= 5
 r3: x6 + 2 x7 <= 7
 r4: -x1 + 1.2 x7 >= -2.3
 q1: [ -1.8 x1^2 + x2^2 ] <= 0
 q2: [ 4.25 x3^2 - 2 x3 * x4 + 4.25 x4^2 - 2 x4 * x5 + 4 x5^2  ] + 2 x1 + 3 x3 <= 9.9
 q3: [ x6^2 - 2.2 x7^2 ] >= 5
Bounds
 0.2 <= x1 <= 3.8
 x2 Free
 0.1 <= x3 <= 0.7
 x4 Free
 x5 Free
 x7 Free
End
"""

import coptpy as cp
from coptpy import COPT

# Create COPT environment
env = cp.Envr()

# Create COPT model
model = env.createModel("qcp_ex1")

# Add variables
x1 = model.addVar(lb=0.2, ub=3.8, name='x1')
x2 = model.addVar(lb=-COPT.INFINITY, ub=COPT.INFINITY, name='x2')
x3 = model.addVar(lb=0.1, ub=0.7, name='x3')
x4 = model.addVar(lb=-COPT.INFINITY, ub=COPT.INFINITY, name='x4')
x5 = model.addVar(lb=-COPT.INFINITY, ub=COPT.INFINITY, name='x5')
x6 = model.addVar(lb=0.0, ub=COPT.INFINITY, name='x6')
x7 = model.addVar(lb=-COPT.INFINITY, ub=COPT.INFINITY, name='x7')

# Add linear constraints
model.addConstr(x1 + 2*x2 == 6, name="r1")
model.addConstr(2*x1 + x3 >= 5, name="r2")
model.addConstr(x6 + 2*x7 <= 7, name="r3")
model.addConstr(-x1 + 1.2*x7 >= -2.3, name="r4")

# Add quadratic constraints
model.addQConstr(-1.8*x1*x1 + x2*x2 <= 0, name="q1")
model.addQConstr(4.25*x3*x3 - 2*x3*x4 + 4.25*x4*x4 - 2*x4*x5 + 4*x5*x5 + 2*x1 + 3*x3 <= 9.9, name="q2")
model.addQConstr(x6*x6 - 2.2*x7*x7 >= 5, name="q3")

# Set quadratic objective
obj = 2.1*x1 - 1.2*x2 + 3.2*x3 + x4 + x5 + x6 + 2*x7 + 0.5*x2*x2
model.setObjective(obj, COPT.MINIMIZE)

# Set parameters
model.setParam(COPT.Param.TimeLimit, 60)

# Solve the problem
model.solve()

# Analyze solution
if model.status == COPT.OPTIMAL:
  print("\nOptimal objective value: {0:.9e}".format(model.objval))
  vars = model.getVars()

  print("Variable solution:")
  for var in vars:
    print(" {0} = {1:.9e}".format(var.name, var.x))
