#
# This file is part of the Cardinal Optimizer, all rights reserved.
#

"""
Solve the following nonlinear problem:

  Minimize:
    x1 * x4 * (sin(x1 + x2) + cos(x2 * x3) + tan(x3 / x4)) + x3

  Subject to:
    x1 * x2 * x3 * x4 + x1 + x2 >= 35
    log(x1) + 2 * log(x2) + 3 * log(x3) + 4 * log(x4) + x3 + x4 >= 15
    x1^2 + x2^2 + x3^2 + x4^2 + x1 + x3 >= 50

  where:
    1 <= x1 <= 5
    1 <= x2 <= 5
    1 <= x3 <= 5
    1 <= x4 <= 5
"""

import coptpy as cp
from coptpy import COPT

# Create COPT environment
env = cp.Envr()

# Create COPT model
model = env.createModel("nlp_ex1")

# Add four variables
x1 = model.addVar(lb=1.0, ub=5.0, name="x1")
x2 = model.addVar(lb=1.0, ub=5.0, name="x2")
x3 = model.addVar(lb=1.0, ub=5.0, name="x3")
x4 = model.addVar(lb=1.0, ub=5.0, name="x4")

# Add two nonlinear constraints
model.addNlConstr(x1 * x2 * x3 * x4 + x1 + x2 >= 35, "nlrow1")
model.addNlConstr(cp.nl.log(x1) + 2 * cp.nl.log(x2) + 3 * cp.nl.log(x3) + 4 * cp.nl.log(x4) + x3 + x4 >= 15, "nlrow2")

# Add one quadratic constraints
model.addQConstr(x1 * x1 + x2 * x2 + x3 * x3 + x4 * x4 + x1 + x3 >= 50, "qrow1")

# Set nonlinear objective
obj = x1 * x4 * cp.nl.sum([cp.nl.sin(x1 + x2), cp.nl.cos(x2 * x3), cp.nl.tan(x3 / x4)]) + x3
model.setObjective(obj, COPT.MINIMIZE)

# Set parameters
model.setParam(COPT.Param.TimeLimit, 60)

# Solve the problem
model.solve()

# Analyze solution
if model.status == COPT.OPTIMAL:
  print("\nOptimal objective value: {0:.9e}".format(model.objval))

  print("\nVariable solution:")
  vars = model.getVars()
  for var in vars:
    print(" {0} = {1:.9e}".format(var.name, var.x))
else:
  print("\n No solution available")
