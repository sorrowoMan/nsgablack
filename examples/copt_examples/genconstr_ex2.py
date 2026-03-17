#
# This file is part of the Cardinal Optimizer, all rights reserved.
#

import coptpy as cp
from coptpy import COPT

# Create COPT environment
env =cp.Envr()

# Create COPT model
model = env.createModel("genconstr_or")

# Add 0-1 variables
x1 = model.addVar(lb=0, ub=1, vtype=COPT.BINARY, name='x1')
x2 = model.addVar(lb=0, ub=1, vtype=COPT.BINARY, name='x2')
y = model.addVar(lb=0, ub=1, vtype=COPT.BINARY, name='y')

# Set objective function
model.setObjective(y, COPT.MAXIMIZE)

# Add logical constraint: y = x1 or x2
model.addGenConstrOr(y, [x1, x2], name="or_constr")

# Set x1 = 1, x2 = 1
cons1 = model.addConstr(x1 == 1)
cons2 = model.addConstr(x2 == 1)

# Solve the model and analyze solutions
model.solve()
print("Case 1: x1 = 1, x2 = 1 | {} = {}".format(y.getName(), y.x))
print("")

# Set x1 = 0, x2 = 1
model.remove(cons1)
model.remove(cons2)
cons3 = model.addConstr(x1 == 0)
cons4 = model.addConstr(x2 == 1)

# Solve the model and analyze solutions
model.solve()
print("Case 2: x1 = 0, x2 = 1 | {} = {}".format(y.getName(), y.x))
print("")

# Set x1 = 0, x2 = 0
model.remove(cons3)
model.remove(cons4)
cons5 = model.addConstr(x1 == 0)
cons6 = model.addConstr(x2 == 0)

# Solve the model and analyze solutions
model.solve()
print("Case 3: x1 = 0, x2 = 0 | {} = {}".format(y.getName(), y.x))