#
# This file is part of the Cardinal Optimizer, all rights reserved.
#

import coptpy as cp
from coptpy import COPT
import numpy as np

def factorMarkowitz(n, mu, G_factor_T, theta, x0, w, gamma):
    env = cp.Envr()
    model = env.createModel("factorMarkowitz")
    model.matrixmodelmode = "experimental"

    x = model.addMVar(n, nameprefix="x")

    model.setObjective(x @ mu, COPT.MAXIMIZE)
    model.addConstr(x.sum() == w + sum(x0))

    model.addAffineCone(
        cp.vstack(gamma, cp.vstack(G_factor_T @ x, np.sqrt(theta) * x)),
        ctype=COPT.CONE_QUAD,
        name="affqcone",
    )
    model.setParam(COPT.Param.Logging, 0)
    model.solve()

    print("Objective value: %.5f" % model.objval)
    X_value = []
    for i in range(n):
        X_value.append(model.getVarByName(f"x({i})").X)

    return (cp.NdArray(mu) @ x.getInfo(COPT.Info.Value)).sum(), X_value

if __name__ == "__main__":
    n = 8
    w = 1.0
    mu = [0.07197, 0.15518, 0.17535, 0.08981, 0.42896, 0.39292, 0.32171, 0.18379]
    x0 = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    B = np.array([
        [0.4256, 0.1869],
        [0.2413, 0.3877],
        [0.2235, 0.3697],
        [0.1503, 0.4612],
        [1.5325, -0.2633],
        [1.2741, -0.2613],
        [0.6939, 0.2372],
        [0.5425, 0.2116]
    ])
    S_F = np.array([
        [0.0620, 0.0577],
        [0.0577, 0.0908]
    ])
    theta = np.array([0.0720, 0.0508, 0.0377, 0.0394, 0.0663, 0.0224, 0.0417, 0.0459])
    P = np.array([
        [0.2489, 0.0],
        [0.2317, 0.1926]
    ])
    G_factor = B @ P
    G_factor_T = G_factor.T
    gammas = [0.24, 0.28, 0.32, 0.36, 0.4, 0.44, 0.48]

    print("\n-----------------------------------------------------------------------------------")
    print("Markowitz portfolio optimization with factor model")
    print("-----------------------------------------------------------------------------------\n")
    for index, gamma in enumerate(gammas):
        expect, x = factorMarkowitz(n, mu, G_factor_T, theta, x0, w, gamma)
        print("Expected return:    %.5f" % expect)
        print("Standrad deviation: %.5f" % gamma)
