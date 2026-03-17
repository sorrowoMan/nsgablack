#
# This file is part of the Cardinal Optimizer, all rights reserved.
#

import coptpy as cp
from coptpy import COPT

# Create COPT environment
env = cp.Envr()

# Create COPT model
model = env.createModel("genconstr_max")

# Add variables
x1 = model.addVar(lb=0, ub=COPT.INFINITY, vtype=COPT.CONTINUOUS, name='x_1')
x2 = model.addVar(lb=0, ub=COPT.INFINITY, vtype=COPT.CONTINUOUS, name='x_2')
y = model.addVar(lb=0, ub=COPT.INFINITY, vtype=COPT.CONTINUOUS, name='y')

# Set objective function
model.setObjective(y, sense=COPT.MINIMIZE)

# Add max constraint: y = max{x1, x2}
model.addGenConstrMax(y, [x1, x2], name="max_constr")

# Set x1 = 100, x2 = 200
model.addConstr(x1 == 100)
model.addConstr(x2 == 200)

# Solve the model
model.solve()

# Analyze solutions
print("Optimal objective: {}".format(model.ObjVal))
