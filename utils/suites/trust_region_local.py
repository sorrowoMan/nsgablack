"""
Suites for trust-region local search adapters.
"""

from __future__ import annotations

from typing import Optional

from ..plugins import BenchmarkHarnessPlugin, ModuleReportPlugin
from ..plugins import MASModelPlugin
from ...core.adapters import (
    TrustRegionDFOAdapter,
    TrustRegionSubspaceAdapter,
    TrustRegionNonSmoothAdapter,
    MASAdapter,
)


def attach_trust_region_dfo(solver) -> None:
    """Attach TrustRegionDFOAdapter + common reporting plugins."""
    solver.adapter = TrustRegionDFOAdapter()
    solver.add_plugin(BenchmarkHarnessPlugin())
    solver.add_plugin(ModuleReportPlugin())


def attach_trust_region_subspace(solver) -> None:
    """Attach TrustRegionSubspaceAdapter + common reporting plugins."""
    solver.adapter = TrustRegionSubspaceAdapter()
    solver.add_plugin(BenchmarkHarnessPlugin())
    solver.add_plugin(ModuleReportPlugin())


def attach_trust_region_subspace_learned(solver) -> None:
    """Attach TrustRegionSubspaceAdapter + learned subspace basis."""
    from ..plugins import SubspaceBasisPlugin, SubspaceBasisConfig

    solver.adapter = TrustRegionSubspaceAdapter()
    solver.add_plugin(SubspaceBasisPlugin(SubspaceBasisConfig(method="pca")))
    solver.add_plugin(BenchmarkHarnessPlugin())
    solver.add_plugin(ModuleReportPlugin())


def attach_trust_region_nonsmooth(solver) -> None:
    """Attach TrustRegionNonSmoothAdapter + common reporting plugins."""
    solver.adapter = TrustRegionNonSmoothAdapter()
    solver.add_plugin(BenchmarkHarnessPlugin())
    solver.add_plugin(ModuleReportPlugin())


def attach_mas(solver) -> None:
    """Attach MASAdapter + MASModelPlugin + common reporting plugins."""
    solver.adapter = MASAdapter()
    solver.add_plugin(MASModelPlugin())
    solver.add_plugin(BenchmarkHarnessPlugin())
    solver.add_plugin(ModuleReportPlugin())
