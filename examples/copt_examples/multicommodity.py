#
# This file is part of the Cardinal Optimizer, all rights reserved.
#

import coptpy as cp
from coptpy import COPT

import math
import itertools

# Optimization data for multicommodity problem
ORIG        = ['GARY', 'CLEV', 'PITT']
DEST        = ['FRA', 'DET', 'LAN', 'WIN', 'STL', 'FRE', 'LAF']
PROD        = ['bands', 'coils', 'plate']

supply_list = [400,  800, 200,
               700, 1600, 300,
               800, 1800, 300]
supply      = dict(zip(itertools.product(ORIG, PROD), supply_list))

demand_list = [300, 500, 100,
               300, 750, 100,
               100, 400,   0,
                75, 250,  50,
               650, 950, 200,
               225, 850, 100,
               250, 500, 250]
demand      = dict(zip(itertools.product(DEST, PROD), demand_list))

limit_list  = [625.0] * len(ORIG) * len(DEST)
limit       = dict(zip(itertools.product(ORIG, DEST), limit_list))

cost_list   = [30, 39, 41,
               10, 14, 15,
                8, 11, 12,
               10, 14, 16,
               11, 16, 17,
               71, 82, 86,
                6,  8,  8,
              
               22, 27, 29,
                7,  9,  9,
               10, 12, 13,
                7,  9,  9,
               21, 26, 28,
               82, 95, 99,
               13, 17, 18,

               19, 24, 26,
               11, 14, 14,
               12, 17, 17,
               10, 13, 13,
               25, 28, 31,
               83, 99, 104,
               15, 20, 20]
cost        = dict(zip(itertools.product(ORIG, DEST, PROD), cost_list))

# Create COPT environment
env = cp.Envr()

# Create COPT problem
mmulti = env.createModel()

# Add variables to problem
vtrans = mmulti.addVars(ORIG, DEST, PROD, nameprefix='trans')

# Add constraints to problem
mmulti.addConstrs((vtrans.sum(i, '*', k) == supply[i, k] for i in ORIG for k in PROD), nameprefix='supply')
mmulti.addConstrs((vtrans.sum('*', j, k) == demand[j, k] for j in DEST for k in PROD), nameprefix='demand')
mmulti.addConstrs((vtrans.sum(i, j, '*') <= limit[i, j] for i in ORIG for j in DEST), nameprefix='multi')

# Set objective function
mmulti.setObjective(vtrans.prod(cost), COPT.MINIMIZE)

# Set optimization parameters
mmulti.setParam(COPT.Param.TimeLimit, 100)

# Solve the problem
mmulti.solve()

# Display solution
if mmulti.status == COPT.OPTIMAL:
  print('\nObjective value: {}'.format(mmulti.objval))

  print('Variable solution: ')
  multvars = mmulti.getVars()
  for mvar in multvars:
    if math.fabs(mvar.x) >= 1e-6:
      print('    {0:s} = {1:.6f}'.format(mvar.name, mvar.x))
