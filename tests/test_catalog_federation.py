from dataclasses import replace
import sys
from types import ModuleType

import pytest

from blackbase.catalog import Catalog as SharedCatalog, CatalogEntry as SharedEntry
from nsgablack.catalog import registry
from nsgablack.catalog.federation import (
    PROVIDERS_ENV, configured_catalog_sources, load_federated_entries,
)
from nsgablack.catalog.usage import build_usage_profile


@pytest.fixture
def catalog_source(monkeypatch):
    module = ModuleType("test_public_catalog_source")
    module.get_catalog = lambda: SharedCatalog(())
    monkeypatch.setitem(sys.modules, module.__name__, module)
    monkeypatch.setenv(PROVIDERS_ENV, f"mlblack={module.__name__}:get_catalog")
    monkeypatch.setattr(registry, "_SOURCE_CATALOG_BY_PROFILE", {})
    monkeypatch.setattr(registry, "_CATALOG_BY_PROFILE", {})
    monkeypatch.setattr(registry, "_load_external_entries", lambda: [])
    monkeypatch.setattr(registry, "_load_entrypoint_entries", lambda: [])
    return module


def test_federation_preserves_public_records_and_namespaces_local_links(catalog_source):
    entry = SharedEntry(
        key="codec.model", title="Model codec", kind="codec", import_path="mlblack.codec:Model",
        tags=("layout",), companions=("head.point", "adapter.nsga2"),
        required_companions=("head.point",), context_requires=("model_ref",),
        artifact_requires=("data",), artifact_provides=("model",),
        phase_in=("fit",), phase_out=("predict",),
        config_keys=("layout",), minimal_wiring=("codec = Model(layout)",),
        contract={"supports_gradient": True, "metadata": {"shape": [3, 1]}},
        metadata={"architecture_path": "representation.codec", "custom": {"a": 1}},
    )
    head = SharedEntry(key="head.point", title="Head", kind="head", import_path="mlblack.head:Point")
    catalog_source.get_catalog = lambda: SharedCatalog((entry, head))

    values = load_federated_entries()
    expected = replace(
        entry, key="mlblack.codec.model",
        companions=("mlblack.head.point", "adapter.nsga2"),
        required_companions=("mlblack.head.point",),
        metadata={**entry.metadata, "catalog_framework": "mlblack", "catalog_original_key": entry.key},
    )
    assert values[0].as_dict() == expected.as_dict()
    assert values[1].key == "mlblack.head.point"
    assert entry.key == "codec.model"  # the owning registry is unchanged


def test_explicit_provider_failure_does_not_publish_partial_catalog(catalog_source):
    def broken_provider():
        raise TypeError("invalid source contract")

    catalog_source.get_catalog = broken_provider
    with pytest.raises(RuntimeError, match="Required Catalog provider 'mlblack'.*invalid source contract"):
        registry.get_source_catalog(refresh=True)
    assert registry._SOURCE_CATALOG_BY_PROFILE == {}


@pytest.mark.parametrize("value", [
    "mlblack", "mlblack=module", "nsgablack=module:factory", "MLBlack=module:factory",
    "mlblack=module:factory,mlblack=other:factory",
])
def test_invalid_provider_configuration_is_rejected(value):
    with pytest.raises(ValueError):
        configured_catalog_sources(value)


def test_provider_requires_shared_records_and_unique_keys(catalog_source):
    catalog_source.get_catalog = lambda: [{"key": "model"}]
    with pytest.raises(RuntimeError, match="CatalogEntry"):
        load_federated_entries()
    entry = SharedEntry(key="model", title="Model", kind="model", import_path="model:Model")
    catalog_source.get_catalog = lambda: [entry, entry]
    with pytest.raises(RuntimeError, match="unique"):
        load_federated_entries()


def test_native_and_foreign_duplicate_names_do_not_override_each_other(catalog_source, monkeypatch):
    native = registry.CatalogEntry(key="bias.penalty", title="Native", kind="bias", import_path="native:Bias")
    foreign = SharedEntry(key="bias.penalty", title="ML", kind="bias", import_path="mlblack.bias:Bias")
    monkeypatch.setattr(registry, "_load_external_entries", lambda: [native])
    catalog_source.get_catalog = lambda: [foreign]
    catalog = registry.get_source_catalog(refresh=True)
    assert catalog.get("bias.penalty").title == "Native"
    assert catalog.get("bias.penalty").metadata["catalog_framework"] == "nsgablack"
    assert catalog.get("mlblack.bias.penalty").title == "ML"


def test_global_namespace_collision_is_rejected(catalog_source, monkeypatch):
    monkeypatch.setattr(registry, "_load_external_entries", lambda: [registry.CatalogEntry(
        key="mlblack.model", title="Existing", kind="model", import_path="native:Model",
    )])
    catalog_source.get_catalog = lambda: [SharedEntry(
        key="model", title="External", kind="model", import_path="mlblack.model:Model",
    )]
    with pytest.raises(ValueError, match="unique"):
        registry.get_source_catalog(refresh=True)


def test_source_configuration_participates_in_both_cache_keys(catalog_source, monkeypatch):
    calls = []

    def get_catalog(*, refresh=False):
        calls.append(refresh)
        return SharedCatalog((SharedEntry(key="model", title="ML", kind="model", import_path="ml:Model"),))

    catalog_source.get_catalog = get_catalog
    configured = registry.get_catalog(refresh=True)
    assert configured.get("mlblack.model") is not None
    monkeypatch.delenv(PROVIDERS_ENV)
    assert registry.get_catalog().get("mlblack.model") is None
    monkeypatch.setenv(PROVIDERS_ENV, f"mlblack={catalog_source.__name__}:get_catalog")
    assert registry.get_catalog() is configured
    registry.get_source_catalog(refresh=True)
    assert calls == [True, True]


def test_framework_core_filters_foreign_examples_and_dotted_paths(catalog_source):
    catalog_source.get_catalog = lambda: SharedCatalog((
        SharedEntry(key="model", title="ML", kind="model", import_path="mlblack.models:Model",
                    example_entry="mlblack.examples.project:build"),
        SharedEntry(key="demo", title="Demo", kind="example", import_path="mlblack.examples:run"),
        SharedEntry(key="demo_model", title="Demo model", kind="model", import_path="mlblack.examples.demo:Model"),
    ))
    full = registry.get_source_catalog(profile="default", refresh=True)
    core = registry.get_source_catalog(profile="framework-core", refresh=True)
    assert len(full.list()) == 3
    assert [entry.key for entry in core.list()] == ["mlblack.model"]
    assert core.get("mlblack.model").example_entry == ""


@pytest.mark.parametrize("kind", ["bias", "representation", "plugin"])
def test_foreign_usage_has_no_guessed_nsga_recipe(catalog_source, kind):
    catalog_source.get_catalog = lambda: [SharedEntry(
        key=f"{kind}.model", title="ML component", kind=kind, import_path="mlblack.component:Model",
    )]
    entry = registry.get_source_catalog(refresh=True).list()[0]
    # Source and DB read paths preserve the same foreign declarations.
    assert registry._enrich_catalog_entries([entry])[0] == entry
    usage = build_usage_profile(entry)
    assert usage.minimal_wiring == ()
    assert usage.use_when == ()
    assert usage.example_entry == ""
    assert usage.config_keys == ()


def test_real_mlblack_public_catalog_includes_current_semantics(monkeypatch):
    ml_registry = pytest.importorskip("mlblack.catalog.registry")
    monkeypatch.setenv(PROVIDERS_ENV, "mlblack=mlblack.catalog.registry:get_catalog")
    original = ml_registry.get_catalog(refresh=True)
    foreign = {entry.key: entry for entry in load_federated_entries()}
    assert len(foreign) == len(original.list())
    for key in ("trainer.learning_solver", "codec.linear_point", "core.model", "core.learning"):
        assert foreign[f"mlblack.{key}"].import_path == original.get(key).import_path
        assert foreign[f"mlblack.{key}"].contract == original.get(key).contract
        for name, value in original.get(key).metadata.items():
            assert foreign[f"mlblack.{key}"].metadata[name] == value
    assert {"trainer", "codec", "head", "data_view", "provider", "problem"} <= {
        entry.kind for entry in foreign.values()
    }
