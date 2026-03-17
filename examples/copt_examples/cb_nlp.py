#
#  This file is part of the Cardinal Optimizer, all rights reserved.
#
#  This example shows how to solve a simple nonlinear problem using NLP callback.
#  This test is originally from HS071 in the Hock & Schittkowski collection.
#
#  min   x0 * x3 * (x0 + x1 + x2)  + x2    (obj)
#  s.t.  x0 * x1 * x2 * x3 >= 25           (c0)
#        x0^2 + x1^2 + x2^2 + x3^2 = 40    (c1)
#
#        1 <= x0, x1, x2, x3 <= 5
#
#  The init value is (1, 5, 5, 1) and optimal objective is 17.014017145.
#
#

import numpy as np
import coptpy as cp
from coptpy import COPT


class HS071(cp.NlpCallbackBase):
    def __init__(self) -> None:
        super().__init__()

    def EvalObj(self, xdata, outdata) -> int:
        x = cp.NdArray(xdata)
        outval = cp.NdArray(outdata)

        # Evaluate objective value
        outval[0] = x[0] * x[3] * (x[0] + x[1] + x[2]) + x[2]
        return 0

    def EvalGrad(self, xdata, outdata) -> int:
        x = cp.NdArray(xdata)
        outval = cp.NdArray(outdata)

        # Evaluate objective gradient
        outval[0] = x[0] * x[3] + x[3] * (x[0] + x[1] + x[2])
        outval[1] = x[0] * x[3]
        outval[2] = x[0] * x[3] + 1.0
        outval[3] = x[0] * (x[0] + x[1] + x[2])
        return 0

    def EvalCon(self, xdata, outdata) -> int:
        x = cp.NdArray(xdata)
        outval = cp.NdArray(outdata)

        # Evaluate constraint values
        outval[:] = [x.prod(), x.dot(x)]
        return 0

    def EvalJac(self, xdata, outdata) -> int:
        x = cp.NdArray(xdata)
        outval = cp.NdArray(outdata)

        prod = x.prod()

        # Evaluate Jacobian values
        outval[:4] = [prod / v for v in x]
        outval[4:] = 2.0 * x
        return 0

    def EvalHess(self, xdata, sigma, lambdata, outdata) -> int:
        x = cp.NdArray(xdata)
        lagrange = cp.NdArray(lambdata)
        outval = cp.NdArray(outdata)

        H = sigma * np.array(
            (
                (2 * x[3], 0, 0, 0),
                (x[3], 0, 0, 0),
                (x[3], 0, 0, 0),
                (2 * x[0] + x[1] + x[2], x[0], x[0], 0),
            )
        )

        H += lagrange[0] * np.array(
            (
                (0, 0, 0, 0),
                (x[2] * x[3], 0, 0, 0),
                (x[1] * x[3], x[0] * x[3], 0, 0),
                (x[1] * x[2], x[0] * x[2], x[0] * x[1], 0),
            )
        )

        H += lagrange[1] * 2 * np.eye(4)
        rows, cols = self.hessianstructure()

        # Evaluate Hessian values
        outval[:] = H[rows, cols]
        return 0

    def hessianstructure(self):
        return np.nonzero(np.tril(np.ones((4, 4))))


if __name__ == "__main__":
    try:
        # Create environment and model
        env = cp.Envr()
        model = env.createModel()

        # create customized NLP callback
        cb = HS071()

        hRows, hCols = cb.hessianstructure()
        nHess = len(hRows)

        # Load NL data into model
        model.loadNlData(
            4,
            2,
            COPT.MINIMIZE,  # sense
            # It means that objective gradient is dense and column index array is set to NULL.
            COPT.DENSETYPE_ROWMAJOR,
            None,
            # It means that Jacobian matrix is dense and stored in row-major order.
            COPT.DENSETYPE_ROWMAJOR,
            # Because Jocobian matrix is dense, its row and column index arrays are set to NULL.
            None,
            None,
            # Hesssian matrix is provided in sparse format.
            nHess,
            hRows,
            hCols,
            # colLower and colUpper
            [1.0, 1.0, 1.0, 1.0],
            [5.0, 5.0, 5.0, 5.0],
            # rowLower and rowUpper
            [25.0, 40.0],
            [COPT.INFINITY, 40.0],
            # init col values
            [1.0, 5.0, 5.0, 1.0],
            # The evaluation type includes 5 options, depending on user's implementation in NlpCallback.
            # Please refer to doc for details. Here -1 means that user has implemented all evaluation methods.
            -1,
            cb,
        )

        model.solve()

        print("")
        if model.haslpsol:
            values = model.getValues()
            print("Optimal objective is {:.8f}".format(model.objval))
            print("Primal values are {}".format(values))
        else:
            print("No LP solution is available, status = {}".format(model.status))

    except cp.CoptError as e:
        print('Error code ' + str(e.retcode) + ": " + str(e.message))
    except AttributeError:
        print('Encountered an attribute error')
