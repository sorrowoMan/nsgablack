#
# This file is part of the Cardinal Optimizer, all rights reserved.
#

import coptpy as cp
from coptpy import COPT

# Create COPT environment
env = cp.Envr()

# Create COPT model
model = env.createModel("genconstr_abs")

# Add variables
x = model.addVar(lb=-COPT.INFINITY,
                 ub=COPT.INFINITY,
                 vtype=COPT.CONTINUOUS,
                 name='x')
z = model.addVar(lb=0, ub=COPT.INFINITY, vtype=COPT.CONTINUOUS, name='z')

# Set objective function
model.setObjective(z, COPT.MAXIMIZE)

# Add absolute constraint: z = |x|
model.addGenConstrAbs(z, x, name="abs_constr")

# Set x = -10
model.addConstr(x == -10)

# Solve the model
model.solve()

# Analyze solutions
print("Optimal objective: {}".format(model.objval))
print("z = {}".format(z.x))
