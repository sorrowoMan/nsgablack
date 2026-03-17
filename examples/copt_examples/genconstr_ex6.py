#
# This file is part of the Cardinal Optimizer, all rights reserved.
#

'''
This example considers the following separable, convex problem:

    minimize    f(x) - y + g(z)
    subject to  3 x + 2 y + 2 z <= 4
           0  <=  x,    y,    z <= 1

     where f(u) = exp(-2 u + 1) and g(u) = -sqrt(u), for all real u.
'''

from math import exp, sqrt
import coptpy as cp
from coptpy import COPT

def f(u):
    return exp(-2 * u + 1)

def g(u):
    return -sqrt(u)

# Create COPT environment
env = cp.Envr()

# Create COPT model
m = env.createModel("genconstr_pwl")

# Add variables
lb = 0.0
ub = 1.0
x = m.addVar(lb, ub, name='x')
y = m.addVar(lb, ub, name='y')
z = m.addVar(lb, ub, name='z')
s = m.addVar(lb=0.0, name='s')
t = m.addVar(lb=-COPT.INFINITY, name='t')

# Set the objective function
m.setObjective(-y + s + t)

# Set non-linear functions f(x) and g(z) (converting to PWL constraints)
npts = 101
ptu = []
ptf = []
ptg = []
for i in range(npts):
    ptu.append(lb + (ub - lb) * i / (npts - 1))
    ptf.append(f(ptu[i]))
    ptg.append(g(ptu[i]))
m.addGenConstrPWL(x, s, ptu, ptf, name='f_exp')
m.addGenConstrPWL(z, t, ptu, ptg, name='g_sqrt')

# Add the linear constraint: 3 x + 2 y + 2 z <= 4
m.addConstr(3 * x + 2 * y + 2 * z <= 4, 'c0')

# Solve the model
m.solve()

# Analyze solutions
if m.hasmipsol:
    print('')
    print('Best objective value: {0}'.format(m.objval))
    print('Variable solution:')
    print('  x: {0}'.format(x.x))
    print('  y: {0}'.format(y.x))
    print('  z: {0}'.format(z.x))
