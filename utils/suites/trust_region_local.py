"""
Suites for trust-region local search adapters.
"""

from __future__ import annotations

from typing import Optional

from ...plugins import BenchmarkHarnessPlugin, ModuleReportPlugin
from ...plugins import MASModelPlugin
from ...adapters import (
    TrustRegionDFOAdapter,
    TrustRegionSubspaceAdapter,
    TrustRegionNonSmoothAdapter,
    MASAdapter,
)

def _require_set_adapter(solver) -> None:
    if not hasattr(solver, "set_adapter"):
        raise ValueError("trust_region_local suites require solver.set_adapter()")


def attach_trust_region_dfo(solver) -> None:
    """Attach TrustRegionDFOAdapter + common reporting plugins."""
    _require_set_adapter(solver)
    solver.set_adapter(TrustRegionDFOAdapter())
    solver.add_plugin(BenchmarkHarnessPlugin())
    solver.add_plugin(ModuleReportPlugin())


def attach_trust_region_subspace(solver) -> None:
    """Attach TrustRegionSubspaceAdapter + common reporting plugins."""
    _require_set_adapter(solver)
    solver.set_adapter(TrustRegionSubspaceAdapter())
    solver.add_plugin(BenchmarkHarnessPlugin())
    solver.add_plugin(ModuleReportPlugin())


def attach_trust_region_subspace_learned(solver) -> None:
    """Attach TrustRegionSubspaceAdapter + learned subspace basis."""
    from ...plugins import SubspaceBasisPlugin, SubspaceBasisConfig

    _require_set_adapter(solver)
    solver.set_adapter(TrustRegionSubspaceAdapter())
    solver.add_plugin(SubspaceBasisPlugin(SubspaceBasisConfig(method="pca")))
    solver.add_plugin(BenchmarkHarnessPlugin())
    solver.add_plugin(ModuleReportPlugin())


def attach_trust_region_nonsmooth(solver) -> None:
    """Attach TrustRegionNonSmoothAdapter + common reporting plugins."""
    _require_set_adapter(solver)
    solver.set_adapter(TrustRegionNonSmoothAdapter())
    solver.add_plugin(BenchmarkHarnessPlugin())
    solver.add_plugin(ModuleReportPlugin())


def attach_mas(solver) -> None:
    """Attach MASAdapter + MASModelPlugin + common reporting plugins."""
    _require_set_adapter(solver)
    solver.set_adapter(MASAdapter())
    solver.add_plugin(MASModelPlugin())
    solver.add_plugin(BenchmarkHarnessPlugin())
    solver.add_plugin(ModuleReportPlugin())

