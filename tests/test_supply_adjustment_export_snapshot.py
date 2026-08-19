from __future__ import annotations

import importlib
from pathlib import Path

import numpy as np

from blackbase.context.context_keys import (
    KEY_CONSTRAINT_VIOLATIONS,
    KEY_OBJECTIVES,
    KEY_POPULATION,
)
from blackbase.project import case_import_context


_REPO_ROOT = Path(__file__).resolve().parents[1]
_CASE_NAME = "supply_adjustment_nested"


class _Problem:
    events = ()

    @staticmethod
    def decode_shifts(candidate):
        return np.zeros(np.asarray(candidate).size, dtype=int)


class _SnapshotOnlySolver:
    adapter = None
    pareto_solutions = {}

    def read_snapshot(self):
        return {
            KEY_POPULATION: np.asarray([[2.0], [1.0]], dtype=float),
            KEY_OBJECTIVES: np.asarray([[2.0], [1.0]], dtype=float),
            KEY_CONSTRAINT_VIOLATIONS: np.zeros(2, dtype=float),
        }

    @property
    def population(self):
        raise AssertionError("plugin must read population through the snapshot protocol")

    @property
    def objectives(self):
        raise AssertionError("plugin must read objectives through the snapshot protocol")


def test_supply_export_candidate_selection_uses_snapshot_protocol(tmp_path) -> None:
    project_root = _REPO_ROOT / "examples" / "cases" / _CASE_NAME
    with case_import_context(project_root, _CASE_NAME):
        module = importlib.import_module(
            f"cases.{_CASE_NAME}.plugins.supply_adjustment_export_plugin"
        )
        plugin = module.SupplyAdjustmentExportPlugin(
            case_problem=_Problem(),
            output_dir=tmp_path,
            run_id="test",
        )
        candidate, objectives = plugin._select_export_candidate(_SnapshotOnlySolver())

    assert np.array_equal(candidate, np.asarray([1.0]))
    assert np.array_equal(objectives, np.asarray([1.0]))
