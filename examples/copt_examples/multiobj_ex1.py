#
# This file is part of the Cardinal Optimizer, all rights reserved.
#
import coptpy as cp
from coptpy import COPT

"""
Multi-Objective Knapsack Problem:
  Consider a set of 20 items divided into 5 groups, where each group contains
  mutually exclusive items (only one item per group can be selected).

  Each item i in group j has a volume V_ij, a value P_ij, and a weight W_ij.

  Volume = [10, 13, 24, 32, 4]
           [12, 15, 22, 26, 5.2]
           [14, 18, 25, 28, 6.8]
           [14, 14, 28, 32, 6.8]

  Value  = [3, 4, 9, 15, 2]
           [4, 6, 8, 10, 2.5]
           [5, 7, 10, 12, 3]
           [3, 5, 10, 10, 2]]

  Weight = [0.2, 0.3, 0.4, 0.6, 0.1]
           [0.25, 0.35, 0.38, 0.45, 0.15]
           [0.3, 0.37, 0.5, 0.5, 0.2]
           [0.3, 0.32, 0.45, 0.6, 0.2]

  Objectives:
    Maximize total value while minimizing total weight of selected items

  Subject to:
    - Exactly one item must be selected from each group
    - Total volume of selected items <= knapsack capacity
"""

# Create COPT environment
env = cp.Envr()

# Create COPT model and enable experimental matrix mode
model = env.createModel("Multi-Objective Knapsack")
model.matrixmodelmode = "experimental"

# Add binary variables in shape of (4, 5), representing which item is selected
# in each group (5 groups and 4 items per group)
mv = model.addMVar((4, 5), vtype=COPT.BINARY, nameprefix="MX")

# Add constraint of mutual exclusivity
model.addConstrs(mv.sum(axis=0) == 1, nameprefix="Exclusivity")

# Add constraint of total volume not exceeding knapsack capacity
volume = cp.NdArray(
    [
        [10, 13, 24, 32, 4],
        [12, 15, 22, 26, 5.2],
        [14, 18, 25, 28, 6.8],
        [14, 14, 28, 32, 6.8],
    ],
    dtype=float,
)
model.addConstr((volume * mv).sum() <= 90.0, "Capacity")

# Add first objective: maximize total value of selected items
value = cp.NdArray(
    [[3, 4, 9, 15, 2], [4, 6, 8, 10, 2.5], [5, 7, 10, 12, 3], [3, 5, 10, 10, 2]],
    dtype=float,
)
model.setObjectiveN(0, (value * mv).sum(), COPT.MAXIMIZE, priority=2)

# Add second objective: minimize total weight of selected items
weight = cp.NdArray(
    [
        [0.2, 0.3, 0.4, 0.6, 0.1],
        [0.25, 0.35, 0.38, 0.45, 0.15],
        [0.3, 0.37, 0.5, 0.5, 0.2],
        [0.3, 0.32, 0.45, 0.6, 0.2],
    ],
    dtype=float,
)
model.setObjectiveN(1, (weight * mv).sum(), COPT.MINIMIZE, priority=1)

# Solve the multi-objective knapsack problem
model.solve()

# Show the solution
if model.status == COPT.OPTIMAL:
    sumVolume = 0
    sumValue = 0
    sumWeight = 0
    print("\n Group\tVolume \tValue \tWeight")

    sol = mv.getInfo(COPT.Info.Value)
    for k in range(5):
        for i in range(4):
            if sol[i][k] > 0.99:
                sumVolume += volume[i][k]
                sumValue += value[i][k]
                sumWeight += weight[i][k]
                print("  {0}\t{1}\t{2}\t{3}".format(k, volume[i][k], value[i][k], weight[i][k]))
    print(" Total\t{0}\t{1}\t{2}".format(sumVolume, sumValue, sumWeight))
else:
    print("Optimal solution is not available, with status " + str(model.status))
