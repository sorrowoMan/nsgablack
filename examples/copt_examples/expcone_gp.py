#
# This file is part of the Cardinal Optimizer, all rights reserved.
#

r"""
 Solve the following Geometric Programming problem with exponential cone:

 maximize: x + y + z

 s.t.  log[exp(x + y + log(2 / Aw)) + exp(x + z + log(2 / Aw))] <= 0
             -inf <= y + z <= log(Af)
       log(alpha) <= x - y <= log(beta)
       log(gamma) <= z - y <= log(delta)

 where:
             -inf <= x <= +inf
             -inf <= y <= +inf
             -inf <= z <= +inf

 reformulated as exponential cone problem:

 maximize: x + y + z

 s.t.  u1 >= exp(u3)
       u3 == x + y + log(2 / Aw)
       v1 >= exp(v3)
       v3 = x + z + log(2 / Aw)
       u1 + v1 == 1.0
             -inf <= y + z <= log(Af)
       log(alpha) <= x - y <= log(beta)
       log(gamma) <= z - y <= log(delta)

 where:
             -inf <= x <= +inf
             -inf <= y <= +inf
             -inf <= z <= +inf
  (u1, u2, u3) \in Kexp, (v1, v2, v3) \in Kexp, u2 == 1.0, v2 == 1.0
"""

import coptpy as cp
from coptpy import COPT

import math

Aw, Af, alpha, beta, gamma, delta = 200.0, 50.0, 2.0, 10.0, 2.0, 10.0

# Create COPT environment
env = cp.Envr()

# Create COPT model
model = env.createModel("expcone_gp")

# Create variables: x, y, z
x = model.addVar(lb=-COPT.INFINITY,ub=+COPT.INFINITY, name='x')
y = model.addVar(lb=-COPT.INFINITY,ub=+COPT.INFINITY, name='y')
z = model.addVar(lb=-COPT.INFINITY,ub=+COPT.INFINITY, name='z')

# Add constraint: u1 >= exp(x + y + log(2/Aw)
u1 = model.addVar(lb=-COPT.INFINITY)
u2 = model.addVar(lb=1.0, ub=1.0)
u3 = model.addVar(lb=-COPT.INFINITY)
model.addConstr(u3 == x + y + math.log(2.0/Aw))
model.addExpCone([u1, u2, u3], COPT.EXPCONE_PRIMAL)

# Add constraint: v1 >= exp(x + z + log(2/Aw)
v1 = model.addVar(lb=-COPT.INFINITY)
v2 = model.addVar(lb=1.0, ub=1.0)
v3 = model.addVar(lb=-COPT.INFINITY)
model.addConstr(v3 == x + z + math.log(2.0/Aw))
model.addExpCone([v1, v2, v3], COPT.EXPCONE_PRIMAL)

# Add constraint: u1 + v1 == 1.0
model.addConstr(u1 + v1 == 1.0)

# Add constraints:
#         -inf <= y + z <= log(Af)
#   log(alpha) <= x - y <= log(beta)
#   log(gamma) <= z - y <= log(delta)
model.addConstr(y + z <= math.log(Af))
model.addConstr(x - y == [math.log(alpha), math.log(beta)])
model.addConstr(z - y == [math.log(gamma), math.log(delta)])

# Set objective
model.setObjective(x + y + z, COPT.MAXIMIZE)

# Solve the model
model.solve()

# Analyze solution
if model.status == COPT.OPTIMAL:
    print("Objective value: {}".format(model.objval))

    print("Variable solution:")
    print("  {0}: {1}".format(x.name, x.x))
    print("  {0}: {1}".format(y.name, y.x))
    print("  {0}: {1}".format(z.name, z.x))
