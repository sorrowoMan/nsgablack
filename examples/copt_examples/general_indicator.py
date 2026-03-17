#
# This file is part of the Cardinal Optimizer, all rights reserved.
#

'''
Using the indicator constraints to modeling a tiny production planning problem: 

Coefficients:
    products = ['A', 'B', 'C', 'D', 'E']
    lines = ['P1', 'P2', 'P3']
    fixed_costs = {'P1': 100, 'P2': 120, 'P3': 150}
    unit_costs = {
        'P1': [2, 3, 4, 5, 6],
        'P2': [2.5, 3.5, 4.5, 5.5, 6.5],
        'P3': [3, 4, 5, 6, 7]
    }
    capacity = {'P1': 500, 'P2': 600, 'P3': 700}
    demand = {'A': 300, 'B': 400, 'C': 500, 'D': 200, 'E': 100}
    min_production = {'P1': 100, 'P2': 200, 'P3': 250}

Objective: 
    minimize sum(fixed_costs[i] * lines[i] for i in lines) + sum(unit_costs[i,j] * products[i,j] for j in products for i in lines)

s.t. 
    sum(x[i, j] for i in lines) >= demand[j] for j in products
    sum(x[i, j] for j in products) <= capacity[i] for i in lines
    Indicator constraints: if-then, only-if, if-and-only-if

Bounds: 
    x >= 0 and integer
    y binary
'''

import coptpy as cp
from coptpy import COPT


# Create COPT environment and COPT model
env = cp.Envr()
model = env.createModel("Production_Planning")

# Define production lines, products, demand, and production capacity
products = ['A', 'B', 'C', 'D', 'E']
lines = ['P1', 'P2', 'P3']

fixed_costs = {'P1': 100, 'P2': 120, 'P3': 150}
unit_costs = {
    'P1': [2, 3, 4, 5, 6],
    'P2': [2.5, 3.5, 4.5, 5.5, 6.5],
    'P3': [3, 4, 5, 6, 7]
}
capacity = {'P1': 500, 'P2': 600, 'P3': 700}
demand = {'A': 300, 'B': 400, 'C': 500, 'D': 200, 'E': 100}
min_production = {'P1': 100, 'P2': 200, 'P3': 250}

# Add variables x for production and y for line(on/off)
x = model.addVars(lines, products, vtype=COPT.INTEGER, nameprefix="x")
y = model.addVars(lines, vtype=COPT.BINARY, nameprefix="y")

# Set objective: minimize total production cost
model.setObjective(
    cp.quicksum(fixed_costs[i] * y[i] for i in lines) +
    cp.quicksum(unit_costs[i][j] * x[i, products[j]] for i in lines for j in range(len(products))),
    sense=COPT.MINIMIZE
)

# Add demand satisfication constraints
for j in products:
    model.addConstr(cp.quicksum(x[i, j] for i in lines) >= demand[j], name=f"demand_{j}")

# Add production capacity limitation constraints
for i in lines:
    model.addConstr(cp.quicksum(x[i, j] for j in products) <= capacity[i], name=f"capacity_{i}")

# Add If-Then constraints 
# If line i is enabled (y_i = 1), then production must be at least min_production; if line i is unabled (y_i = 0), then production must be 0
for i in lines:
    model.addConstr((y[i] == 1) >> (cp.quicksum(x[i, j] for j in products) >= min_production[i]), name=f"ifthen_on({i})")
    model.addConstr((y[i] == 0) >> (cp.quicksum(x[i, j] for j in products) == 0), name=f"ifthen_off({i})")

# Add Only-If constraint: If the total production of line P2 <= 0.5* capacity['P2'], then line P2 is unabled
model.addConstr((y['P2'] == 0) << (cp.quicksum(x['P2', j] for j in products) <= 0.5 * capacity['P2']), name="onlyif_P2")

# Add If-and-Only-If constraints: If and only if P1 and P2 are both active, P3 produces at least 2*min_production['P3']
y1_2 = model.addVar(vtype=COPT.BINARY)
model.addGenConstrAnd(y1_2, [y['P1'], y['P2']])
model.addGenConstrIndicator(y1_2, True, cp.quicksum(x['P3', j] for j in products) >= 2*min_production['P3'], COPT.INDICATOR_IFANDONLYIF, name="iff_P3")

# Solve the model
model.solve()

# Output the result
if model.status == COPT.OPTIMAL:
    print("Optimal solution found:")
    print(f"Total production cost: {model.objVal:.2f}\n")
    for i in lines:
        print(f"Production line {i} is {'enabled' if y[i].x > 0.5 else 'disabled'}.")
        for j in products:
            print(f"Product {j}: {x[i, j].x:.0f} units")
        print()
else:
    print("No optimal solution found.")
