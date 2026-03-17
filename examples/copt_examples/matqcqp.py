#
# This file is part of the Cardinal Optimizer, all rights reserved.
#

import coptpy as cp
from coptpy import COPT
import numpy as numpy

# SDP relaxation for solving MIQCP problem
def sdp_relaxation(n, P, q):
    env = cp.Envr()
    M = env.createModel("sdp_relaxation")
    M.matrixmodelmode = 'experimental'

    Z = M.addPsdVar(n + 1, name="Z")
    X = Z[:-1, :-1]
    x = Z[:-1, -1:]

    M.addConstrs(X.diagonal() >= x)
    M.addConstr(Z[n, n].sum()== 1)

    M.setObjective((P * X).sum().item()+ 2.0 * (x * q).sum().item(), COPT.MINIMIZE)

    M.solve()

    sliceZarr = Z.x[0:n, n:n + 1].tolist()
    return M.getAttr(COPT.Attr.SolvingTime), numpy.rint(sliceZarr)

# A direct integer model for minimizing |Ax-b|
def least_squares(n, A, b):
    env = cp.Envr()
    M = env.createModel("least_squares")
    M.matrixmodelmode = 'experimental'

    x = M.addMVar(n, vtype=COPT.INTEGER, nameprefix="x")
    t = M.addVar(lb=-COPT.INFINITY, vtype=COPT.CONTINUOUS, name="t")

    M.addAffineCone(cp.vstack(t, A @ x - b), ctype=COPT.CONE_QUAD)
    M.setObjective(t, COPT.MINIMIZE)

    M.solve()

    return M.getAttr(COPT.Attr.SolvingTime), numpy.rint(M.getInfo(COPT.Info.Value, x).tolist())

if __name__ == '__main__':
    n = 20
    m = 2 * n

    A = numpy.reshape(numpy.random.normal(0., 1.0, n * m), (m, n))
    c = numpy.random.uniform(0., 1.0, n)
    P = A.transpose().dot(A)
    q = - P.dot(c)
    b = A.dot(c)

    timeM, xRound = sdp_relaxation(n, P, q)
    timeMint, xOpt = least_squares(n, A, b)

    resM = numpy.linalg.norm(A.dot(xRound) - b)
    resMint = numpy.linalg.norm(A.dot(xOpt) - b)
    print(timeM, timeMint)
    print(resM, resMint)
