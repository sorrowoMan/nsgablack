"""Withdrawn source cards must explain migration instead of offering old calls.

These tests read the public source registry in both profiles. They never build
an algorithm, construct a Unit, connect a database or execute a paid generator.
"""
from __future__ import annotations

import ast
from pathlib import Path
import socket
import sqlite3

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

import pytest

from nsgablack.catalog import registry
from nsgablack.catalog.usage_api_validation import inspect_usage_api


ROOT = Path(__file__).resolve().parents[1]
ROOTS = {name: ROOT.parent / name for name in ("nsgablack", "blackbase", "mlblack")}
DIVERSITY = {
    "bias.diversity", "bias.diversity_adaptive", "bias.diversity_crowding",
    "bias.diversity_niche", "bias.diversity_sharing",
}
WITHDRAWN = set("""
bias.diversity bias.diversity_adaptive bias.diversity_crowding
bias.diversity_niche bias.diversity_sharing
bias.convergence bias.convergence_adaptive bias.convergence_precision
bias.convergence_late_stage bias.convergence_multi_stage bias.levy
bias.local_gd bias.local_newton bias.local_line_search bias.local_trust_region
bias.local_nelder_mead bias.local_quasi_newton
bias.bayesian_guidance bias.bayesian_exploration bias.bayesian_convergence
bias.surrogate_control bias.surrogate_phase_schedule bias.surrogate_uncertainty_budget
bias.safety bias.manufacturing bias.scheduling bias.resource_constraint
bias.time_window bias.engineering_design bias.engineering_precision
bias.engineering_robustness bias.uncertainty_exploration
bias.graph_connectivity bias.graph_sparsity bias.graph_degree_distribution
bias.graph_shortest_path bias.graph_max_flow bias.graph_coloring bias.graph_community
bias.graph_tsp_constraint bias.graph_path_constraint bias.graph_hamiltonian_constraint
plugin.elite plugin.diversity_init plugin.dynamic_switch
plugin.gpu_eval_template plugin.sensitivity_analysis
""".split())


def _migration_sources():
    sources = {}
    manifests = (
        "bias_algorithm_migrations.toml", "bias_domain_production.toml",
        "bias_graph_applications.toml", "lifecycle_legacy_migrations.toml",
        "orchestration_adapters_applications.toml",
    )
    for name in manifests:
        payload = tomllib.loads((ROOT / "catalog/example_manifests" / name).read_text(encoding="utf-8"))
        for example in payload["example"]:
            if example.get("usage_status") != "migration_reference":
                continue
            for key in example.get("component_keys", ()):
                if key in WITHDRAWN:
                    sources[key] = example["sources"][0]["path"].removeprefix("nsgablack/")
    return sources


@pytest.fixture
def source_only_catalog(monkeypatch):
    monkeypatch.setenv("NSGABLACK_CATALOG_PATH", "")
    monkeypatch.setenv("NSGABLACK_CATALOG_PROVIDERS", "")
    monkeypatch.setenv("NSGABLACK_CATALOG_DB_MODE", "off")
    monkeypatch.setenv("NSGABLACK_CATALOG_HOSTED", "1")
    monkeypatch.setenv("NSGABLACK_CATALOG_HOSTED_SOURCE", "registry")
    monkeypatch.setattr(registry, "_SOURCE_CATALOG_BY_PROFILE", {})

    def forbidden(*args, **kwargs):
        pytest.fail("Migration-card source inspection must not execute or connect")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    from nsgablack.core import ComposableSolver
    from nsgablack.units import UnitBinding
    monkeypatch.setattr(ComposableSolver, "run", forbidden)
    monkeypatch.setattr(UnitBinding, "build", forbidden)


@pytest.mark.parametrize("profile", ("default", "framework-core"))
def test_native_withdrawn_cards_keep_comment_guidance_and_real_sources(source_only_catalog, profile):
    assert len(WITHDRAWN) == 47
    sources = _migration_sources()
    assert sources.keys() == WITHDRAWN
    catalog = registry.get_source_catalog(profile=profile, refresh=True)
    for key in sorted(WITHDRAWN):
        entry = catalog.get(key)
        assert entry is not None, (profile, key)
        lines = tuple(entry.minimal_wiring)
        assert lines and all(line.strip().startswith("#") for line in lines), (profile, key, lines)
        source = "\n".join(lines)
        assert ast.parse(source).body == [], (profile, key)
        inspection = inspect_usage_api(source, source_roots=ROOTS)
        assert inspection["issues"] == [], (profile, key, inspection["issues"])
        assert inspection["checked_calls"] == [], (profile, key)
        assert entry.summary and entry.use_when and entry.import_path, (profile, key)
        assert entry.example_entry and (ROOT / entry.example_entry).is_file(), (profile, key)
        if key in DIVERSITY:
            # Existing explicit recipes own these public cards; do not add a
            # competing per-shard recipe or change their established target.
            assert entry.example_entry == "docs/catalog_usage/POPULATION_PREFERENCE_APPLICATIONS_CN.md"
        else:
            assert entry.example_entry == sources[key], (profile, key)
            assert "迁移" in entry.summary, (profile, key)
        assert (ROOT / sources[key]).is_file(), (profile, key)
