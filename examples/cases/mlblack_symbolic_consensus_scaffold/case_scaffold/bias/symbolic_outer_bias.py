# -*- coding: utf-8 -*-
"""Domain bias assembly for the symbolic consensus outer search."""

from __future__ import annotations

import numpy as np

from nsgablack.bias import BiasModule, DiversityBias, StructurePriorBias, TabuSearchBias

from case_scaffold.problem.outer_problem import MlblackSymbolicConsensusOuterProblem


def build_symbolic_outer_bias_module(problem: MlblackSymbolicConsensusOuterProblem) -> BiasModule:
    module = BiasModule()

    def structure_penalty(x: np.ndarray, _context) -> float:
        decoded = problem._decode_plan(x)
        overrides = dict(decoded.get("trainer_params_overrides", {}) or {})
        complexity = float(problem._complexity_score(x))
        support = float(decoded.get("core_min_support_rate", 0.0) or 0.0)
        max_basis = int(overrides.get("orth_max_basis_count", 0) or 0)
        core_terms = int(decoded.get("core_max_terms", 0) or 0)
        under_exposed_core = max(0.0, 0.45 - support)
        arity_collapse_risk = max(0.0, float(core_terms - max_basis))
        return float((0.4 * complexity) + under_exposed_core + arity_collapse_risk)

    module.add(
        StructurePriorBias(
            name="symbolic_structure_prior",
            mode="custom",
            custom_penalty=structure_penalty,
            weight=0.05,
        )
    )
    module.add(DiversityBias(weight=0.02, metric="manhattan"))
    module.add(TabuSearchBias(weight=0.04, tabu_size=48, distance_threshold=0.08, penalty_scale=0.5))
    return module
