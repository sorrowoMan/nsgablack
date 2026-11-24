"""Risk guidance follows runtime declarations without evaluating candidates."""
from __future__ import annotations

from dataclasses import fields
import inspect
from pathlib import Path

import pytest

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

from nsgablack.bias.domain.risk_bias import RiskBias
from nsgablack.catalog import guidance_for
from nsgablack.catalog.facade import catalog_neighbors
from nsgablack.catalog import registry
from nsgablack.catalog.registry import CatalogEntry
from nsgablack.plugins.evaluation.monte_carlo_evaluation import (
    MonteCarloEvaluationConfig,
    MonteCarloEvaluationProviderPlugin,
)


ROOT = Path(__file__).resolve().parents[1]


def _record(shard: str, key: str) -> dict:
    payload = tomllib.loads((ROOT / "catalog" / "entries" / shard).read_text(encoding="utf-8-sig"))
    return next(record for record in payload["entry"] if record["key"] == key)


def test_monte_carlo_config_and_context_match_the_public_implementation():
    record = _record("plugin.toml", "plugin.monte_carlo_eval")
    entry = CatalogEntry(**record)
    assert tuple(entry.config_keys) == tuple(field.name for field in fields(MonteCarloEvaluationConfig))
    assert set(entry.config_keys) == {"mc_samples", "reduce", "cvar_alpha", "random_seed"}
    for field_name in ("context_requires", "context_provides", "context_mutates", "context_cache"):
        assert tuple(getattr(entry, field_name)) == tuple(getattr(MonteCarloEvaluationProviderPlugin, field_name))
    assert set(entry.context_provides) == {
        f"metrics.{metric}" for metric in MonteCarloEvaluationProviderPlugin.provides_metrics
    }
    assert entry.required_companions == ("(none)",)
    assert {"bias.risk", "bias.robustness"} <= set(entry.companions)
    assert guidance_for(entry).role == "evaluation_provider"
    boundaries = " ".join(guidance_for(entry).boundaries)
    assert "MonteCarloEvaluationConfig" in boundaries
    assert all(parameter in inspect.signature(MonteCarloEvaluationProviderPlugin).parameters
               for parameter in ("name", "config", "priority"))


def test_risk_guidance_declares_actual_parameters_metrics_and_soft_semantics():
    entry = CatalogEntry(**_record("bias.toml", "bias.risk"))
    assert set(entry.config_keys) == set(inspect.signature(RiskBias).parameters)
    assert set(entry.context_requires) == set(RiskBias.context_requires) | {
        f"metrics.{metric}" for metric in RiskBias.requires_metrics
    }
    for field_name in ("context_provides", "context_mutates", "context_cache"):
        assert tuple(getattr(entry, field_name)) == tuple(getattr(RiskBias, field_name))
    notes = " ".join(entry.context_notes)
    assert RiskBias.metrics_fallback == "safe_zero" and RiskBias.metrics_fallback in notes
    assert all(metric in notes for metric in RiskBias.requires_metrics)
    assert entry.required_companions == ("(none)",)
    assert set(entry.companions) == set(RiskBias.recommended_plugins)
    guidance = guidance_for(entry)
    assert guidance.role == "soft_preference"
    boundaries = " ".join(guidance.boundaries)
    assert "raw feedback" in boundaries and "safe_zero" in boundaries
    assert "Provider" in boundaries and "尾部均值" in boundaries


@pytest.fixture
def native_source_catalog(monkeypatch):
    """Use real TOML registries while excluding local DB/account configuration."""
    monkeypatch.setenv("NSGABLACK_CATALOG_PATH", "")
    monkeypatch.setenv("NSGABLACK_CATALOG_PROVIDERS", "")
    monkeypatch.setenv("NSGABLACK_CATALOG_DB_MODE", "off")
    monkeypatch.setenv("NSGABLACK_CATALOG_HOSTED", "1")
    monkeypatch.setenv("NSGABLACK_CATALOG_HOSTED_SOURCE", "registry")
    monkeypatch.setattr(registry, "_SOURCE_CATALOG_BY_PROFILE", {})

    from nsgablack.core import ComposableSolver
    from nsgablack.units import UnitBinding

    def forbidden_execution(*args, **kwargs):
        pytest.fail("Catalog navigation must not construct Units or execute evaluation/search")

    monkeypatch.setattr(UnitBinding, "build", forbidden_execution)
    monkeypatch.setattr(ComposableSolver, "run", forbidden_execution)
    monkeypatch.setattr(MonteCarloEvaluationProviderPlugin, "evaluate_feedback_population", forbidden_execution)


@pytest.mark.parametrize("profile", ("default", "framework-core"))
def test_real_neighbor_navigation_connects_candidate_statistics_in_both_directions(native_source_catalog, profile):
    catalog = registry.get_source_catalog(profile=profile, refresh=True)
    provider = catalog.get("plugin.monte_carlo_eval")
    risk = catalog.get("bias.risk")
    assert provider is not None and risk is not None
    assert provider.required_companions == risk.required_companions == ("(none)",)

    provider_neighbors = catalog_neighbors(provider.key, profile=profile, source_mode="off")
    risk_neighbors = catalog_neighbors(risk.key, profile=profile, source_mode="off")
    assert provider_neighbors is not None and risk_neighbors is not None
    assert {"bias.risk", "bias.robustness"} <= {
        item["key"] for item in provider_neighbors["companions"]
    }
    assert provider.key in {item["key"] for item in risk_neighbors["companions"]}
    assert provider_neighbors["missing_companions"] == risk_neighbors["missing_companions"] == ()

    for metric in RiskBias.requires_metrics:
        context_key = f"metrics.{metric}"
        consumers = provider_neighbors["relation_groups"][f"context_provides::{context_key}"]
        producers = risk_neighbors["relation_groups"][f"context_requires::{context_key}"]
        assert risk.key in {item["key"] for item in consumers}
        assert provider.key in {item["key"] for item in producers}
        assert all(item["contract_value"] == context_key for item in (*consumers, *producers))
        assert any(card["family"] == "context" and card["value"] == context_key
                   and card["outgoing_count"] >= 1
                   for card in provider_neighbors["relation_chain_cards"])
        if profile == "framework-core":
            assert all(item["kind"] not in {"example", "doc"} for item in (*consumers, *producers))
