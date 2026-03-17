#
# This file is part of the Cardinal Optimizer, all rights reserved.
#

"""
We will compute an IIS for the following infeasible LP problem, the problem
is 'itest6' test case from netlib-infeas:

Minimize
  X2 + X3 + X4
Subject To
  ROW1: 0.8 X3 + X4 <= 10000
  ROW2: X1 <= 90000
  ROW3: 2 X6 - X8 <= 10000
  ROW4: - X2 + X3 >= 50000
  ROW5: - X2 + X4 >= 87000
  ROW6: X3 <= 50000
  ROW7: - 3 X5 + X7 >= 10000
  ROW8: 0.5 X5 + 0.6 X6 <= 300000
  ROW9: X2 - 0.05 X3 = 5000
  ROW10: X2 - 0.04 X3 - 0.05 X4 = 4500
  ROW11: X2 >= 80000
END
"""

import coptpy as cp
from coptpy import COPT

# Create COPT environment
env = cp.Envr()

# Create COPT model
model = env.createModel("iis_ex1")

# Add variables
x1 = model.addVar(lb=0.0, ub=COPT.INFINITY, name='X1')
x2 = model.addVar(lb=0.0, ub=COPT.INFINITY, name='X2')
x3 = model.addVar(lb=0.0, ub=COPT.INFINITY, name='X3')
x4 = model.addVar(lb=0.0, ub=COPT.INFINITY, name='X4')
x5 = model.addVar(lb=0.0, ub=COPT.INFINITY, name='X5')
x6 = model.addVar(lb=0.0, ub=COPT.INFINITY, name='X6')
x7 = model.addVar(lb=0.0, ub=COPT.INFINITY, name='X7')
x8 = model.addVar(lb=0.0, ub=COPT.INFINITY, name='X8')

# Add constraints
model.addConstr(0.8*x3 + x4 <= 10000, name="ROW1")
model.addConstr(x1 <= 90000, name="ROW2")
model.addConstr(2*x6 - x8 <= 10000, name="ROW3")
model.addConstr(-x2 + x3 >= 50000, name="ROW4")
model.addConstr(-x2 + x4 >= 87000, name="ROW5")
model.addConstr(x3 <= 50000, name="ROW6")
model.addConstr(-3*x5 + x7 >= 10000, name="ROW7")
model.addConstr(0.5*x5 + 0.6*x6 <= 300000, name="ROW8")
model.addConstr(x2 - 0.05*x3 == 5000, name="ROW9")
model.addConstr(x2 - 0.04*x3 - 0.05*x4 == 4500, name="ROW10")
model.addConstr(x2 >= 80000, name="ROW11")

# Set objective
model.setObjective(x2 + x3 + x4, COPT.MINIMIZE)

# Set parameters
model.setParam(COPT.Param.TimeLimit, 60)

# Solve the problem
model.solve()

# Compute IIS if problem is infeasible
if model.status == COPT.INFEASIBLE:
  # Compute IIS
  model.computeIIS()

  # Check if IIS is available
  if model.hasIIS:
    # Print variables and constraints in IIS
    cons = model.getConstrs()
    vars = model.getVars()

    print("\n======================== IIS result ========================")
    for con in cons:
      if con.iislb or con.iisub:
        print('  {0}: {1}'.format(con.name, "lower" if con.iislb else "upper"))

    print("")
    for var in vars:
      if var.iislb or var.iisub:
        print('  {0}: {1}'.format(var.name, "lower" if var.iislb else "upper"))

    # Write IIS to file
    print("")
    model.writeIIS('iis_ex1.iis')
