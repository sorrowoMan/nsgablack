#
# This file is part of the Cardinal Optimizer, all rights reserved.
#

import coptpy as cp
from coptpy import COPT

import sys
import math

def solve_soc():
  try:
    # Create COPT environment
    env = cp.Envr()

    # Create COPT model
    m = env.createModel()

    # Add variables
    #
    #   minimize: z
    #
    #   bnds:
    #     x, y, t free, z non-negative
    #
    x = m.addVar(lb=-COPT.INFINITY)
    y = m.addVar(lb=-COPT.INFINITY)
    z = m.addVar()
    t = m.addVar(lb=-COPT.INFINITY)

    # Set objective: z
    m.setObjective(z, COPT.MINIMIZE)

    # Add constraints
    #
    #   r0: 3*x + y >= 1
    #   c0: z^2 >= x^2 + 2*y^2
    #
    # c0 is converted to:
    #
    #   r1: sqrt(2.0)*y - t = 0
    #   c1: z^2 >= x^2 + t^2
    #
    m.addConstr(3*x + y >= 1.0)
    m.addConstr(math.sqrt(2.0) * y - t == 0.0)

    m.addCone([z, x, t], COPT.CONE_QUAD)

    # Set parameter
    m.setParam(COPT.Param.TimeLimit, 10.0)

    # Solve the model
    m.solve()

    # Analyze solution
    if m.status == COPT.OPTIMAL:
      print("\nObjective value: {}".format(m.objval))
      allvars = m.getVars()

      print("Variable solution:")
      for var in allvars:
        print("  x[{0}] = {1}".format(var.index, var.x))
      print("\n")
  except cp.CoptError as e:
    print('Error code ' + str(e.retcode) + ": " + str(e.message))
  except AttributeError:
    print('Encountered an attribute error')

def solve_rsoc():
  try:
    # Create COPT environment
    env = cp.Envr()

    # Create COPT model
    m = env.createModel()

    # Add variables
    #
    #   minimize: 1.5*x - 2*y + z
    #
    #   bnds:
    #     0 <= x <= 20
    #     y, z, r >= 0
    #     s, t free
    #
    x = m.addVar(lb=0.0, ub=20.0)
    y = m.addVar(lb=0.0)
    z = m.addVar(lb=0.0)
    r = m.addVar(lb=0.0)
    s = m.addVar(lb=-COPT.INFINITY)
    t = m.addVar(lb=-COPT.INFINITY)

    # Set objective: 1.5*x - 2*y + z
    m.setObjective(1.5*x - 2*y + z, COPT.MINIMIZE)

    # Add constraints
    #
    #   r0: 2*x + y >= 2
    #   r1: -x + 2*y <= 6
    #   r2: r = 1
    #   r3: 2.8284271247 * x + 0.7071067811 * y - s = 0
    #   r4: 3.0822070014 * y - t = 0
    #   c0: 2*z*r >= s^2 + t^2
    #
    m.addConstr(2*x + y >= 2)
    m.addConstr(-x + 2*y <= 6)
    m.addConstr(r == 1)
    m.addConstr(2.8284271247 * x + 0.7071067811 * y - s == 0)
    m.addConstr(3.0822070014 * y - t == 0)

    m.addCone([z, r, s, t], COPT.CONE_RQUAD)

    # Set parameter
    m.setParam(COPT.Param.TimeLimit, 10.0)

    # Solve the model
    m.solve()

    # Analyze solution
    if m.status == COPT.OPTIMAL:
      print("\nObjective value: {}".format(m.objval))
      allvars = m.getVars()

      print("Variable solution:")
      for var in allvars:
        print("  x[{0}] = {1}".format(var.index, var.x))
      print("\n")
  except cp.CoptError as e:
    print('Error code ' + str(e.retcode) + ": " + str(e.message))
  except AttributeError:
    print('Encountered an attribute error')

def solve_mps(filename):
  try:
    # Create COPT environment
    env = cp.Envr()

    # Create COPT model
    m = env.createModel()

    # Read SOCP from MPS file
    m.readMps(filename)

    # Set parameter
    m.setParam(COPT.Param.TimeLimit, 10.0)

    # Solve the model
    m.solve()
  except cp.CoptError as e:
    print('Error code ' + str(e.retcode) + ": " + str(e.message))
  except AttributeError:
    print('Encountered an attribute error')

if __name__ == '__main__':
  # Solve SOCP with regular cone
  solve_soc()

  # Solve SOCP with rotated cone
  solve_rsoc()

  # Solve SOCP from MPS file
  if len(sys.argv) >= 2:
    solve_mps(sys.argv[1])
