# 
# This file is part of the Cardinal Optimizer, all rights reserved.
#

"""
                 [2, 1, 0]   
  minimize    Tr [1, 2, 1] * X + x0
                 [0, 1, 2]
 
                 [1, 0, 0]
  subject to  Tr [0, 1, 0] * X <= 0.8
                 [0, 0, 1]
 
                 [1, 1, 1]
              Tr [1, 1, 1] * X + x1 + x2 = 0.6
                 [1, 1, 1]

              x0 + x1 + x2 <= 0.9
              x0 >= (x1^2 + x2^2) ^ (1/2)
 
    x0, x1, x2 non-negative, X in PSD
"""

import coptpy as cp
from coptpy import COPT

try:
  import numpy as np
  hasnumpy = True
except ImportError:
  hasnumpy = False

try:
  # Create COPT environment
  env = cp.Envr()

  # Create COPT model
  m = env.createModel("sdp_ex1")

  # Add symmetric matrix C
  rows = [0, 1, 1, 2, 2]
  cols = [0, 0, 1, 1, 2]
  vals = [2.0, 1.0, 2.0, 1.0, 2.0]
  C = m.addSparseMat(3, rows, cols, vals)

  # Add identity matrix A1
  A1 = m.addEyeMat(3)
  # Add ones matrix A2
  A2 = m.addOnesMat(3)

  # Add PSD variable
  barX = m.addPsdVars(3, "BAR_X")

  # Create variables
  x0 = m.addVar(lb=0.0, ub=COPT.INFINITY, name="x0")
  x1 = m.addVar(lb=0.0, ub=COPT.INFINITY, name="x1")
  x2 = m.addVar(lb=0.0, ub=COPT.INFINITY, name="x2")

  # Add PSD constraints
  m.addConstr(A1 * barX <= 0.8, name="PSD_R1")
  m.addConstr(A2 * barX + x1 + x2 == 0.6, name="PSD_R2")

  # Add linear constraint: x0 + x1 + x2 <= 0.9
  m.addConstr(x0 + x1 + x2 <= 0.9)

  # Add SOC constraint: x0^2 >= x1^2 + x2^2
  m.addCone([x0, x1, x2], COPT.CONE_QUAD)

  # Set PSD objective
  m.setObjective(barX * C + x0, COPT.MINIMIZE)

  # Solve the model
  m.solve()

  # Output solution
  if m.status == COPT.OPTIMAL:
    print("")
    print("Optimal objective value: {0}".format(m.objval))
    print("")

    psdvars = m.getPsdVars()
    for psdvar in psdvars:
      print("SDP variable '{0}', flattened by column:".format(psdvar.index))
      print("Primal solution:")
      if hasnumpy:
        print("{0}".format(np.reshape(psdvar.x, (psdvar.dim, psdvar.dim))))
      else:
        psdval = psdvar.x
        for val in psdval:
          print("  {0}".format(val))
      print("")
      print("Dual solution:")
      if hasnumpy:
        print("{0}".format(np.reshape(psdvar.dual, (psdvar.dim, psdvar.dim))))
      else:
        psddual = psdvar.dual
        for val in psddual:
          print("  {0}".format(val))
      print("")

    linvars = m.getVars()
    colval = m.getInfo(COPT.Info.Value, linvars)
    coldual = m.getInfo(COPT.Info.RedCost, linvars)

    print("Non-PSD variables:")
    print("Solution value:")
    for val in colval:
      print("  {0}".format(val))
    print("")
    print("Reduced cost:")
    for val in coldual:
      print("  {0}".format(val))
  else:
    print("No SDP solution!")
except cp.CoptError as e:
  print('Error code ' + str(e.retcode) + ": " + str(e.message))
except AttributeError:
  print('Encountered an attribute error')
