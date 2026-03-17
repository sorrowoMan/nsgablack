# 
# This file is part of the Cardinal Optimizer, all rights reserved.
#

"""
This example solves the mixed SDP problem:

                  [1,  0]
  minimize     Tr [     ] * X + x0 + 2 * x1 + 3       
                  [0,  1]

                  [0,  1]
  subject to   Tr [     ] * X - x0 - 2 * x1 >= 0
                  [1,  0]
             
                  [0,  1]        [5,  1]   [1,  0]
             x0 * [     ] + x1 * [     ] - [     ] in PSD
                  [1,  5]        [1,  0]   [0,  2]

             x0, x1 free, X in PSD
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
  m = env.createModel("lmi_ex1")

  # Create variables
  x0 = m.addVar(lb=-COPT.INFINITY, ub=+COPT.INFINITY, name="x0")
  x1 = m.addVar(lb=-COPT.INFINITY, ub=+COPT.INFINITY, name="x1")

  # Create PSD variable
  X = m.addPsdVar(2, name="BAR_X")

  # Add symmetric matrices
  C0 = m.addEyeMat(2)
  C1 = m.addSparseMat(2, [1], [0], [1.0])

  H1 = m.addSparseMat(2, [(1, 0, 1.0), (1, 1, 5.0)])
  H2 = m.addSparseMat(2, [(0, 0, 5.0), (1, 0, 1.0)])

  D1 = m.addSparseMat(2, [0, 1], [0, 1], [1.0, 2.0])

  # Add PSD constraint
  psdcon = m.addConstr(C1 * X - x0 - 2 * x1 >= 0, name="PSD_c0")

  # Add LMI constraint
  lmicon = m.addConstr(H1 * x0 + H2 * x1 - D1, name="LMI_c0")

  # Set objective
  m.setObjective(C0 * X + x0 + 2 * x1 + 3, COPT.MINIMIZE)

  # Solve the model
  m.solve()

  # Output solution
  if m.status == COPT.OPTIMAL:
    print("")
    print("Optimal objective value: {0}".format(m.objval))
    print("")

    print("SDP variable '{0}':".format(X.name))
    print("Primal solution:")
    if hasnumpy:
      print("{0}".format(np.reshape(X.x, X.shape)))
    else:
      psdval = X.x
      for val in psdval:
        print("  {0}".format(val))
    print("Dual solution:")
    if hasnumpy:
      print("{0}".format(np.reshape(X.dual, X.shape)))
    else:
      psddual = X.dual
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
    print("Reduced cost:")
    for val in coldual:
      print("  {0}".format(val))
    print("")

    print("PSD constraint '{0}':".format(psdcon.name))
    print("Activity: {0}".format(psdcon.slack))
    print("Dual:     {0}".format(psdcon.dual))
    print("")

    print("LMI constraint '{0}':".format(lmicon.name))
    print("Activity:")
    if hasnumpy:
      print("{0}".format(np.reshape(lmicon.slack, lmicon.shape)))
    else:
      lmival = lmicon.slack
      for val in lmival:
        print("  {0}".format(val))
    print("Dual:")
    if hasnumpy:
      print("{0}".format(np.reshape(lmicon.dual, lmicon.shape)))
    else:
      lmidual = lmicon.dual
      for val in lmidual:
        print("  {0}".format(val))
  else:
    print("No SDP solution!")
except cp.CoptError as e:
    print('Error code ' + str(e.retcode) + ": " + str(e.message))
