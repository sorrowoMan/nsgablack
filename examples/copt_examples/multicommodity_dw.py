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

# Optimization parameters for Dantzig-Wolfe decomposition
itercnt     = 0
priceconvex = 1.0
price       = {(i, j): 0 for i in ORIG for j in DEST}
propcost    = []
propshipl   = []

vweight     = []

# Create COPT environment
env = cp.Envr()

# Create the MASTER and SUB problem
mMaster = env.createModel()
mSub    = env.createModel()

# Disable log information
mMaster.setParam(COPT.Param.Logging, 0)
mSub.setParam(COPT.Param.Logging, 0)

# Add variable to the MASTER problem
vexcess = mMaster.addVar(name='excess')

# Add constraints to the MASTER problem
cmulti = mMaster.addConstrs((-vexcess <= limit[i, j] for i in ORIG for j in DEST), \
                             nameprefix='multi')

# Add initial 'convex' constraint to the MASTER problem
cconvex = mMaster.addConstr(cp.LinExpr(0.0) == 1.0, 'convex')

# Add variables to the SUB problem
vtrans = mSub.addVars(ORIG, DEST, PROD, nameprefix='trans')

# Add constraints to the SUB problem
mSub.addConstrs((vtrans.sum(i, '*', k) == supply[i, k] for i in ORIG for k in PROD), \
                 nameprefix='supply')
mSub.addConstrs((vtrans.sum('*', j, k) == demand[j, k] for j in DEST for k in PROD), \
                 nameprefix='demand')

# Set objective function for MASTER problem
mMaster.setObjective(vexcess, COPT.MINIMIZE)

# Dantzig-Wolfe decomposition
print("               *** Dantzig-Wolfe Decomposition ***               ")

# Phase I
print('Phase I: ')

while True:
  # Display the iteration number
  print('Iteration {}: '.format(itercnt))

  # Set objective function 'Artificial Reduced Cost' for the SUB problem
  mSub.setObjective(cp.quicksum(-price[i, j] * vtrans[i, j, k] for i in ORIG for j in DEST for k in PROD) \
                    - priceconvex, \
                    COPT.MINIMIZE)

  # Solve the SUB problem
  mSub.solve()

  # Check if problem is feasible
  if mSub.objval >= -1e-6:
    print('No feasible solution...')
    break
  else:
    itercnt += 1

    # Get the solution of 'trans' variables in the SUB problem
    transval = mSub.getInfo(COPT.Info.Value, vtrans)
    # Calculate parameters for the MASTER problem
    propship = {(i, j): transval.sum(i, j, '*') for i in ORIG for j in DEST}
    propcost.append(transval.prod(cost))
    propshipl.append(propship)

    # Update constraints 'multi' in the MASTER problem
    weightcol = cp.Column()
    weightcol.addTerms(cmulti, propship)
    weightcol.addTerm(cconvex, 1.0)

    # Add variables 'weight' to the MASTER problem
    vweight.append(mMaster.addVar(column=weightcol))

    # Solve the MASTER problem
    mMaster.solve()

    # Update 'price'
    if mMaster.objval <= 1e-6:
      break
    else:
      price = mMaster.getInfo(COPT.Info.Dual, cmulti)
      priceconvex = cconvex.pi

# Phase II
print('Phase II: ')

# Fix variable 'excess'
vexcess_x  = vexcess.x
vexcess.lb = vexcess_x
vexcess.ub = vexcess_x

# Set objective function 'Total Cost' for the MASTER problem
mMaster.setObjective(cp.quicksum(propcost[i] * vweight[i] for i in range(itercnt)), \
                     COPT.MINIMIZE)

# Solve the MASTER problem
mMaster.solve()

# Update 'price' and 'priceconvex'
price = mMaster.getInfo(COPT.Info.Dual, cmulti)
priceconvex = cconvex.pi

# Set the objection function 'Reduced Cost' for the SUB problem
mSub.setObjective(cp.quicksum((cost[i, j, k] - price[i, j]) * vtrans[i, j, k] \
                  for i in ORIG for j in DEST for k in PROD) - priceconvex, \
                  COPT.MINIMIZE)

while True:
  print('Iteration {}: '.format(itercnt))

  # Solve the SUB problem
  mSub.solve()

  if mSub.objval >= -1e-6:
    print('Optimal solution...')
    break
  else:
    itercnt += 1

    # Get the solution of 'trans' variables in the SUB problem
    transval = mSub.getInfo(COPT.Info.Value, vtrans)
    # Calculate parameters for the MASTER problem
    propship = {(i, j): transval.sum(i, j, '*') for i in ORIG for j in DEST}
    propcost.append(transval.prod(cost))
    propshipl.append(propship)

    # Update constraints 'multi' in the MASTER problem
    weightcol = cp.Column()
    weightcol.addTerms(cmulti, propship)
    weightcol.addTerm(cconvex, 1.0)

    # Add variables 'weight' to the MASTER problem
    vweight.append(mMaster.addVar(obj=propcost[itercnt - 1], column=weightcol))

    # Solve the MASTER problem
    mMaster.solve()

    # Update 'price' and 'priceconvex'
    price = mMaster.getInfo(COPT.Info.Dual, cmulti)
    priceconvex = cconvex.pi

    # Set the objection function 'Reduced Cost' for the SUB problem
    mSub.setObjective(cp.quicksum((cost[i, j, k] - price[i, j]) * vtrans[i, j, k] \
                      for i in ORIG for j in DEST for k in PROD) - priceconvex, \
                      COPT.MINIMIZE)

# Phase III
print('Phase III: ')

optship = {(i, j): 0 for i in ORIG for j in DEST}
for i in ORIG:
  for j in DEST:
    optship[i, j] = sum(propshipl[k][i, j] * vweight[k].x for k in range(itercnt))

# Set objective function 'Opt Cost' for SUB problem
mSub.setObjective(vtrans.prod(cost), COPT.MINIMIZE)

# Add new constraints to the SUB problem
mSub.addConstrs((vtrans.sum(i, j, '*') == optship[i, j] for i in ORIG for j in DEST))

# Solve the SUB problem
mSub.solve()
print("                        *** End Loop ***                        \n")

# Report solution
print("               *** Summary Report ***                           ")

print('Objective value: {}'.format(mSub.objval))
print('Variable solution: ')
for i in ORIG:
  for j in DEST:
    for k in PROD:
      if math.fabs(vtrans[i, j, k].x) >= 1e-6:
        print('    {0:s} = {1:.6f}'.format(vtrans[i, j, k].name, vtrans[i, j, k].x))
