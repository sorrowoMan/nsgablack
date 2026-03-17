"""Minimal demo: use `copt_template='qp'` via `CoptBackend`.

Run:
  python examples/_misc_examples/copt_qp_template_demo.py
"""

from __future__ import annotations

import numpy as np

try:
    from nsgablack.plugins import BackendSolveRequest, CoptBackend
except ModuleNotFoundError:  # pragma: no cover
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from nsgablack.plugins import BackendSolveRequest, CoptBackend


def main() -> int:
    backend = CoptBackend()

    # Minimize: 0.5 * x^T Q x + c^T x
    # s.t.      A x <= rhs
    #           lb <= x <= ub
    req = BackendSolveRequest(
        candidate=np.array([0.0, 0.0], dtype=float),
        eval_context={"scope": "outer", "generation": 0},
        payload={
            "copt_template": "qp",
            "copt_template_params": {
                "c": [1.0, 2.0],
                "Q": [
                    [2.0, 0.0],
                    [0.0, 2.0],
                ],
                "A": [
                    [1.0, 1.0],
                ],
                "rhs": [1.0],
                "sense": "<=",
                "lb": [0.0, 0.0],
                "ub": [1.0, 1.0],
                "objective_sense": "min",
            },
        },
    )

    out = dict(backend.solve(req))
    metrics = dict(out.get("metrics", {}))

    print("status:", out.get("status"))
    print("objective:", out.get("objective"))
    print("violation:", out.get("violation"))
    print("mode:", metrics.get("copt.mode"))
    print("template:", metrics.get("copt.template"))
    print("template_mode:", metrics.get("copt.template_mode"))

    if metrics.get("copt.mode") == "mock":
        print("note: coptpy unavailable, backend returned mock result.")

    sol = out.get("solution")
    if sol is not None:
        print("solution:", np.asarray(sol, dtype=float))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
