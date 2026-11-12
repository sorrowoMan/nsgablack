"""Supply assembly requests whole child Cases without borrowing parent CPUs."""
import importlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from blackbase.project.runtime import case_import_context


PROJECT = Path(__file__).resolve().parents[1] / "examples/cases/supply_adjustment_nested"
PRODUCTION = PROJECT.parent / "production_scheduling/cases/production_scheduling"


@pytest.mark.parametrize("external", [False, True], ids=["parent-local", "project-external"])
def test_supply_assembly_wires_whole_case_concurrency(tmp_path, external):
    bom, supply = tmp_path / "bom.csv", tmp_path / "supply.csv"
    pd.DataFrame([(machine, 1, 1) for machine in range(8)],
                 columns=["machine", "material", "required"]).to_csv(bom, index=False)
    inventory = np.zeros((1, 31))
    inventory[0, 0], inventory[0, 5] = 10000, 100
    pd.DataFrame({"material": [1], **{str(day): inventory[:, day] for day in range(31)}}).to_csv(supply, index=False)
    context = {"threads": 1, "grant": {"workers": 1, "threads": 1}, "metadata": {}}
    if external:
        context["metadata"]["nested_execution"] = {"case_names": ["production_inner"]}
    with case_import_context(PROJECT, "supply_adjustment_nested"):
        assembly = importlib.import_module("solver.assembly")
        args = assembly.build_parser().parse_args([
            "--bom", str(bom), "--supply", str(supply),
            "--production-case-dir", str(PRODUCTION), "--machines", "8", "--materials", "1",
            "--outer-parallel-workers", "2", "--inner-parallel-workers", "3",
            "--no-decision-trace", "--no-profiler", "--check",
        ])
        solver = assembly._build_solver_from_args(args, resource_context=context)
        evaluator = solver.problem.inner_runtime_evaluator
        assert evaluator.max_workers == (2 if external else 1)
        assert solver.inner_resource_requirement.threads == (3 if external else 1)
        assert solver.l0_runtime_summary["inner_case_placement"] == (
            "project_external" if external else "parent_local"
        )
        assert solver.l0_runtime_summary["outer_case_max_workers_requested"] == evaluator.max_workers
        assert solver.evaluation_count == 0
        np.testing.assert_array_equal(solver.problem.base_supply[:, 0], inventory[:, 0])


def test_supply_assembly_rejects_legacy_candidate_redis_before_loading_data():
    with case_import_context(PROJECT, "supply_adjustment_nested"):
        assembly = importlib.import_module("solver.assembly")
        args = assembly.build_parser().parse_args(["--outer-parallel-backend", "redis"])
        with pytest.raises(ValueError, match="L0.nested_execution"):
            assembly._build_solver_from_args(args)
