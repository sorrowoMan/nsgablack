#
# This example was adapted from https://github.com/MOSEK/Tutorials/tree/master/filterdesign
# and rewrote with COPT python interface.
#

import coptpy as cp
from coptpy import COPT

import numpy as np
import matplotlib.pyplot as plt

def T_dot_X(M, n, i, X, a=1.0):
  if i >= n or i <= -n:
    return cp.PsdExpr(0.0)
  elif i == 0:
    return M.addDiagMat(n, a, i) * X
  else:
    return M.addDiagMat(n, a * 0.5, i) * X

def trigpoly_0_pi(M, x):
  '''
  Add constraint: x[i] == <T(n + 1, i), X>
  '''
  n = len(x) - 1
  X = M.addPsdVar(n + 1, "X")
    
  for i in range(n + 1):
    M.addConstr(T_dot_X(M, n + 1, i, X) == x[i])

def trigpoly_0_a(M, x, a):
  '''
  Add constraint: x[i] == <T(n + 1, i), X1> + <T(n, i + 1), X2> + <T(n, i - 1), X2> - 2*cos(a)*<T(n, i), X2>
  '''
  n  = len(x) - 1
  X1 = M.addPsdVar(n + 1)
  X2 = M.addPsdVar(n)

  for i in range(n + 1):
    M.addConstr(T_dot_X(M, n + 1, i, X1) + \
                T_dot_X(M, n, i + 1, X2) + \
                T_dot_X(M, n, i - 1, X2) + \
                T_dot_X(M, n, i, X2, -2.0 * np.cos(a)) == x[i])

def trigpoly_a_pi(M, x, a):
  '''
  Add constraint: x[i] == <T(n + 1, i), X1> - <T(n, i + 1), X2> - <T(n, i - 1), X2> + 2*cos(a)*<T(n, i), X2>
  '''
  n  = len(x) - 1
  X1 = M.addPsdVar(n + 1)
  X2 = M.addPsdVar(n)

  for i in range(n+1):
    M.addConstr(T_dot_X(M, n + 1, i, X1) + \
                T_dot_X(M, n, i + 1, X2, -1) + \
                T_dot_X(M, n, i - 1, X2, -1) + \
                T_dot_X(M, n, i, X2, 2.0 * np.cos(a)) == x[i])

def epigraph(M, x, t, a, b):
  '''
  Models 0 <= H(w) <= t, for all w in [a, b]
  where, H(w) = x0 + 2*x1*cos(w) + 2*x2*cos(2*w) + ... + 2*xn*cos(n*w)
  '''
  n  = len(x) - 1
  u = M.addVars(n + 1, lb=-COPT.INFINITY)

  M.addConstr(t == x[0] + u[0])
  for i in range(n):
    M.addConstr(x[i + 1] + u[i + 1] == 0)
    
  if a == 0.0 and b == np.pi:
    trigpoly_0_pi(M, u)
  elif a == 0.0 and b < np.pi:
    trigpoly_0_a(M, u, b)
  elif a < np.pi and b == np.pi:
    trigpoly_a_pi(M, u, a)
  else:
    raise ValueError("Invalid interval.")

def hypograph(M, x, t, a, b):
  '''
  Models 0 <= t <= H(w), for all w in [a, b]
  where, H(w) = x0 + 2*x1*cos(w) + 2*x2*cos(2*w) + ... + 2*xn*cos(n*w)
  '''
  n  = len(x) - 1
  u0 = M.addVar(lb = -COPT.INFINITY)
  u = cp.VarArray()
  u.pushBack(u0)
  for i in range(n):
    u.pushBack(x[i + 1])

  M.addConstr(t == x[0] - u0)

  if a == 0.0 and b == np.pi:
    trigpoly_0_pi(M, u)
  elif a == 0.0 and b < np.pi:
    trigpoly_0_a(M, u,  b)
  elif a < np.pi and b == np.pi:
    trigpoly_a_pi(M, u, a)
  else:
    raise ValueError("Invalid interval.")

if __name__ == "__main__":
  n = 10

  # Create COPT environment and problem
  env = cp.Envr()
  M = env.createModel("trigpoly")

  # Add variables
  x = M.addVars(n + 1, lb=-COPT.INFINITY, nameprefix="x")

  # Add constraints: H(w) >= 0
  trigpoly_0_pi(M, x)

  wp = np.pi / 4.0
  delta = 0.05

  # Add constraints: H(w) <= (1 + delta), w in [0, wp]    
  epigraph(M, x, 1.0 + delta, 0.0, wp)

  # Add constraints: (1 - delta) <= H(w), w in [0, wp]
  hypograph(M, x, 1.0 - delta, 0.0, wp)

  ws = wp + np.pi / 8.0

  # Add constraints: H(w) < t, w in [ws, pi]
  t = M.addVar(lb=0.0, name="t")
  epigraph(M, x, t, ws, np.pi)

  # Set objective
  M.setObjective(t, COPT.MINIMIZE)

  # Solve the problem
  M.solve()

  # Plot the result
  if M.status == COPT.OPTIMAL:
    xx = M.getInfo(COPT.Info.Value, x)

    def H(w):
      return xx[0] + 2*sum([xx[i] * np.cos(i*w) for i in range(1, len(xx))])

    w  = np.linspace(0, np.pi, 100)
    plt.plot(w, [H(wi) for wi in w], 'k')
    plt.show()
  else:
    print("No solution found!")
