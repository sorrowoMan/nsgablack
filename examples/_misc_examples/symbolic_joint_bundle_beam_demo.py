"""Compatibility/thin wrapper：实现与装配已迁入 algorithm_units/symbolic_beam Case。"""
from __future__ import annotations
from typing import Sequence
import numpy as np
from nsgablack.examples.cases.algorithm_units.cases.symbolic_beam.problem.pool import *
from nsgablack.examples.cases.algorithm_units.cases.symbolic_beam.pipeline.operators import *
from nsgablack.examples.cases.algorithm_units.cases.symbolic_beam.adapter.beam import JointBeamAdapter
from nsgablack.examples.cases.algorithm_units.cases.symbolic_beam.config import build_parser
from nsgablack.examples.cases.algorithm_units.cases.symbolic_beam.build_solver import build_solver as _build_case

def build_solver(args):
    solver = _build_case(vars(args))
    return solver, solver.problem

def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    solver, problem = build_solver(args)
    result = solver.run(return_dict=True)
    print(
        f"[demo] status={result.get('status')} steps={result.get('steps')} "
        f"elapsed={float(result.get('elapsed_sec', 0.0)):.3f}s"
    )

    best_x = getattr(solver, "best_x", None)
    if best_x is None:
        print("[demo] no best_x available")
        return
    mask = problem.decode_mask(best_x)
    obj = problem.evaluate(problem.encode_mask(mask))
    selected = problem.selected_feature_names(mask, limit=int(args.show_top))
    print(f"[demo] best_rmse_valid={float(obj[0]):.6f} active_terms={int(np.sum(mask))}")
    print("[demo] selected_ops:", ", ".join(selected) if selected else "<none>")


if __name__ == "__main__":
    main()
