"""Real source federation contract neighbors, without running any Solver."""
import pytest

from nsgablack.catalog import registry
from nsgablack.catalog.facade import catalog_neighbors
from nsgablack.catalog.federation import PROVIDERS_ENV


@pytest.mark.parametrize("profile", ["default", "framework-core"])
def test_ml_source_contracts_reach_actual_neighbors(monkeypatch, profile):
    pytest.importorskip("mlblack.catalog.registry")
    monkeypatch.setenv(PROVIDERS_ENV, "mlblack=mlblack.catalog.registry:get_catalog")
    monkeypatch.setenv("NSGABLACK_CATALOG_DB_MODE", "off")
    monkeypatch.setattr(registry, "_SOURCE_CATALOG_BY_PROFILE", {})
    monkeypatch.setattr(registry, "_CATALOG_BY_PROFILE", {})

    source = registry.get_source_catalog(profile=profile, refresh=True)
    learning = source.get("mlblack.core.learning")
    assert learning.context_requires == ("candidate.model", "data")
    assert learning.context_provides == ("feedback.objectives", "feedback.metrics")
    assert learning.contract["context_provides"] == list(learning.context_provides)

    payload = catalog_neighbors("mlblack.core.learning", profile=profile, source_mode="off")
    groups = payload["relation_groups"]
    assert any(item["key"] == "mlblack.bias.objective_policy"
               for item in groups["context_provides::feedback.objectives"])
    assert any(item["key"] == "mlblack.bias.objective_weight"
               for item in groups["context_provides::feedback.objectives"])
    assert any(item["key"].startswith("mlblack.")
               for item in groups["context_requires::candidate.model"])
