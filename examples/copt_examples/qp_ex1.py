# 
# This file is part of the Cardinal Optimizer, all rights reserved.
# 

"""
Minimize
 OBJ.FUNC: [ 2 X0 ^2 + 4 X0 * X1 + 4 X1 ^2
           + 4 X1 * X2 + 4 X2 ^2
           + 4 X2 * X3 + 4 X3 ^2
           + 4 X3 * X4 + 4 X4 ^2
           + 4 X4 * X5 + 4 X5 ^2
           + 4 X5 * X6 + 4 X6 ^2
           + 4 X6 * X7 + 4 X7 ^2
           + 4 X7 * X8 + 4 X8 ^2
           + 4 X8 * X9 + 2 X9 ^2 ] / 2
Subject To
 ROW0: X0 + 2 X1 + 3 X2  = 1
 ROW1: X1 + 2 X2 + 3 X3  = 1
 ROW2: X2 + 2 X3 + 3 X4  = 1
 ROW3: X3 + 2 X4 + 3 X5  = 1
 ROW4: X4 + 2 X5 + 3 X6  = 1
 ROW5: X5 + 2 X6 + 3 X7  = 1
 ROW6: X6 + 2 X7 + 3 X8  = 1
 ROW7: X7 + 2 X8 + 3 X9  = 1
Bounds
      X0 Free
      X1 Free
      X2 Free
      X3 Free
      X4 Free
      X5 Free
      X6 Free
      X7 Free
      X8 Free
      X9 Free
End
"""

import coptpy as cp
from coptpy import COPT

# Create COPT environment
env = cp.Envr()

# Create COPT model
model = env.createModel("qp_ex1")

# Add variables
x0 = model.addVar(lb=-COPT.INFINITY, ub=COPT.INFINITY, name='X0')
x1 = model.addVar(lb=-COPT.INFINITY, ub=COPT.INFINITY, name='X1')
x2 = model.addVar(lb=-COPT.INFINITY, ub=COPT.INFINITY, name='X2')
x3 = model.addVar(lb=-COPT.INFINITY, ub=COPT.INFINITY, name='X3')
x4 = model.addVar(lb=-COPT.INFINITY, ub=COPT.INFINITY, name='X4')
x5 = model.addVar(lb=-COPT.INFINITY, ub=COPT.INFINITY, name='X5')
x6 = model.addVar(lb=-COPT.INFINITY, ub=COPT.INFINITY, name='X6')
x7 = model.addVar(lb=-COPT.INFINITY, ub=COPT.INFINITY, name='X7')
x8 = model.addVar(lb=-COPT.INFINITY, ub=COPT.INFINITY, name='X8')
x9 = model.addVar(lb=-COPT.INFINITY, ub=COPT.INFINITY, name='X9')

# Add constraints
model.addConstr(x0 + 2*x1 + 3*x2 == 1, name="ROW0")
model.addConstr(x1 + 2*x2 + 3*x3 == 1, name="ROW1")
model.addConstr(x2 + 2*x3 + 3*x4 == 1, name="ROW2")
model.addConstr(x3 + 2*x4 + 3*x5 == 1, name="ROW3")
model.addConstr(x4 + 2*x5 + 3*x6 == 1, name="ROW4")
model.addConstr(x5 + 2*x6 + 3*x7 == 1, name="ROW5")
model.addConstr(x6 + 2*x7 + 3*x8 == 1, name="ROW6")
model.addConstr(x7 + 2*x8 + 3*x9 == 1, name="ROW7")

# Set quadratic objective
obj = x0*x0 + x9*x9
obj += 2*x1*x1 + 2*x2*x2 + 2*x3*x3 + 2*x4*x4
obj += 2*x5*x5 + 2*x6*x6 + 2*x7*x7 + 2*x8*x8
obj += 2*x0*x1 + 2*x1*x2 + 2*x2*x3 + 2*x3*x4 + 2*x4*x5
obj += 2*x5*x6 + 2*x6*x7 + 2*x7*x8 + 2*x8*x9
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
