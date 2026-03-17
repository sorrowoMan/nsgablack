#
# This file is part of the Cardinal Optimizer, all rights reserved.
#
import coptpy as cp
from coptpy import COPT

"""
Production Planning Problem:
  A company manufactures four variants of the same product and in the final part of
  the manufacturing process there are assembly, polishing and packing operations. 
  For each variant the time required for these operations is shown below (in minutes)
  as is the profit per unit sold.

    Variant   Assembly      Polish    Pack        Profit ($)
        1       2             3         2           1.50
        2       4             2         3           2.50
        3       3             3         2           3.00
        4       7             4         5           4.50

  Let Xi be the number of units of variant i (i=1, 2, 3, 4) made per year.

Objectives:
  Maximize total profit 
  1.5*X1 + 2.5*X2 + 3.0*X3 + 4.5*X4 

Subject to:
  (Assembly time) 2*X1 + 4*X2 + 3*X3 + 7*X4 <= 100000
  (Polish time)   3*X1 + 2*X2 + 3*X3 + 4*X4 <= 50000
  (Pack time)     2*X1 + 3*X2 + 2*X3 + 5*X4 <= 60000
"""

def print_sensitivity(model):
    vars = model.getVars()
    cons = model.getConstrs()

    obj_low = model.getInfo(COPT.Info.SAObjLow, vars)
    obj_upp = model.getInfo(COPT.Info.SAObjUp, vars)
    print("")
    print("Variant\tObjective Range")
    for i in range(vars.size):
        print(f"  {vars[i].name}\t({obj_low[i]}, {obj_upp[i]})")

    lb_low = model.getInfo(COPT.Info.SALBLow, vars)
    lb_upp = model.getInfo(COPT.Info.SALBUp, vars)
    ub_low = model.getInfo(COPT.Info.SAUBLow, vars)
    ub_upp = model.getInfo(COPT.Info.SAUBUp, vars)
    print("")
    print("Variant\tLowBound Range  \tUppBound Range")
    for i in range(vars.size):
        print(f"  {vars[i].name}\t({lb_low[i]}, {lb_upp[i]})\t({ub_low[i]}, {ub_upp[i]})")

    rowlb_low = model.getInfo(COPT.Info.SALBLow, cons)
    rowlb_upp = model.getInfo(COPT.Info.SALBUp, cons)
    rowub_low = model.getInfo(COPT.Info.SAUBLow, cons)
    rowub_upp = model.getInfo(COPT.Info.SAUBUp, cons)
    print("")
    print("Constraint\tLHS Range         \tRHS Range")
    for i in range(cons.size):
        print(f"  {cons[i].name}\t({rowlb_low[i]}, {rowlb_upp[i]})\t({rowub_low[i]}, {rowub_upp[i]})")

if __name__ == "__main__":

    # Create COPT environment
    env = cp.Envr()

    # Create COPT model and enable sensitivity analysis
    model = env.createModel("Production Planning Problem")
    model.param.ReqSensitivity = 1

    # Add variable Xi, the number of units of variant i of the same product
    X1 = model.addVar(lb=0.0, name="X1")
    X2 = model.addVar(lb=0.0, name="X2")
    X3 = model.addVar(lb=0.0, name="X3")
    X4 = model.addVar(lb=0.0, name="x4")

    # The total assembly time should be less than 100000 miniutes
    model.addConstr(2 * X1 + 4 * X2 + 3 * X3 + 7 * X4 <= 100000, name="AssemblyTime")

    # The total polishing time should be less than 50000 miniutes
    model.addConstr(3 * X1 + 2 * X2 + 3 * X3 + 4 * X4 <= 50000, name="PolishTime")

    # The total packing time should be less than 60000 miniutes
    model.addConstr(2 * X1 + 3 * X2 + 2 * X3 + 5 * X4 <= 60000, name="PackTime")

    # The objective is to maximize total profit
    model.setObjective(1.5 * X1 + 2.5 * X2 + 3.0 * X3 + 4.5 * X4, COPT.MAXIMIZE)

    # Solve the production planning problem
    model.solve()

    # Show the results of sensitivity analysis
    if model.status == COPT.OPTIMAL:
        if model.HasSensitivity:
            print("")
            print("Sensitivity information of production planning problem:")
            print_sensitivity(model)
        else:
            print("Sensitivity information is not available")
    else:
        print("Optimal solution is not available, with status " + str(model.status))
