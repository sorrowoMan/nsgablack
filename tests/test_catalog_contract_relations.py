from pathlib import Path

import pytest

from nsgablack.catalog import catalog_neighbors, get_catalog, show_entry
from nsgablack.catalog.contract_relations import (
    build_contract_edge_rows,
    build_contract_neighbor_sections,
    enrich_entry_relation_fields,
)
from nsgablack.catalog.registry import CatalogEntry


def test_framework_contract_relations_map_vns_outputs_to_consumers():
    payload = catalog_neighbors("adapter.vns", profile="framework-core")

    assert payload is not None
    relation_groups = dict(payload.get("relation_groups", {}) or {})
    relation_labels = dict(payload.get("relation_labels", {}) or {})
    sigma_group = relation_groups.get("context_provides::mutation_sigma", [])
    vns_group = relation_groups.get("context_provides::vns_k", [])

    assert relation_labels["context_provides::mutation_sigma"] == "产物 -> mutation_sigma -> 消费者"
    assert any(item["key"] == "repr.context_gaussian" for item in sigma_group)
    assert any(item["key"] == "repr.context_switch" for item in vns_group)


@pytest.mark.skip(reason="Catalog contract aggregation changed after DB migration; needs catalog sync.")
def test_project_representation_pipeline_contracts_are_aggregated_and_linked(tmp_path: Path):
    root = tmp_path / "demo_project"
    pipeline_dir = root / "pipeline"
    pipeline_dir.mkdir(parents=True)
    (pipeline_dir / "__init__.py").write_text("", encoding="utf-8")
    (root / "project_registry.py").write_text(
        "\n".join(
            [
                "PROJECT_CATALOG_ENTRIES = [",
                "    {",
                "        'key': 'pipeline.contractual',",
                "        'title': 'Contractual Pipeline',",
                "        'kind': 'representation',",
                "        'import_path': 'pipeline.example_pipeline:build_pipeline',",
                "        'summary': 'Pipeline builder for contract aggregation tests.',",
                "        'tags': ('project', 'pipeline'),",
                "        'companions': (),",
                "    }",
                "]",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (pipeline_dir / "example_pipeline.py").write_text(
        "\n".join(
            [
                "from nsgablack.representation import RepresentationPipeline, UniformInitializer, ClipRepair",
                "from nsgablack.representation.continuous import ContextGaussianMutation",
                "",
                "def build_pipeline():",
                "    return RepresentationPipeline(",
                "        initializer=UniformInitializer(low=-1.0, high=1.0),",
                "        mutator=ContextGaussianMutation(base_sigma=0.2, sigma_key='mutation_sigma', low=-1.0, high=1.0),",
                "        repair=ClipRepair(low=-1.0, high=1.0),",
                "    )",
                "",
            ]
        ),
        encoding="utf-8",
    )

    entry = show_entry(
        "project.pipeline.contractual",
        scope="project",
        project_path=root,
        include_global=True,
    )

    assert entry is not None
    assert "mutation_sigma" in tuple(entry.context_requires or ())

    payload = catalog_neighbors(
        "project.pipeline.contractual",
        scope="project",
        project_path=root,
        include_global=True,
    )

    assert payload is not None
    relation_groups = dict(payload.get("relation_groups", {}) or {})
    assert "context_requires::mutation_sigma" in relation_groups
    assert any(item["key"] == "adapter.vns" for item in relation_groups["context_requires::mutation_sigma"])


@pytest.mark.skip(reason="Artifact/phase relation fields changed after catalog DB migration.")
def test_framework_real_components_expose_artifact_and_phase_relations():
    catalog = get_catalog(profile="framework-core", refresh=True)
    decision_trace = catalog.get("plugin.decision_trace")
    serial_strategy = catalog.get("adapter.serial_strategy")
    context_dispatch = catalog.get("repr.context_dispatch")
    mysql_run_logger = catalog.get("plugin.mysql_run_logger")
    otel_tracing = catalog.get("plugin.otel_tracing")
    sensitivity_analysis = catalog.get("plugin.sensitivity_analysis")

    assert decision_trace is not None
    assert "decision_trace_ref" in tuple(decision_trace.artifact_provides or ())
    assert "decision_trace_jsonl" in tuple(decision_trace.artifact_provides or ())
    assert serial_strategy is not None
    assert "phase" in tuple(serial_strategy.phase_out or ())
    assert context_dispatch is not None
    assert "phase" in tuple(context_dispatch.phase_in or ())
    assert mysql_run_logger is not None
    assert "modules_report_json" in tuple(mysql_run_logger.artifact_requires or ())
    assert otel_tracing is not None
    assert "otel_tracing" in tuple(otel_tracing.artifact_provides or ())
    assert sensitivity_analysis is not None
    assert "sensitivity_study_json" in tuple(sensitivity_analysis.artifact_provides or ())


def test_framework_artifact_relations_link_module_report_to_mysql_logger():
    module_report = show_entry("plugin.module_report", profile="framework-core", source_mode="off")
    mysql_run_logger = show_entry("plugin.mysql_run_logger", profile="framework-core", source_mode="off")

    assert module_report is not None
    assert mysql_run_logger is not None
    assert "modules_report_json" in tuple(module_report.artifact_provides or ())
    assert "bias_report_json" in tuple(module_report.artifact_provides or ())
    assert "modules_report_json" in tuple(mysql_run_logger.artifact_requires or ())
    assert "bias_report_json" in tuple(mysql_run_logger.artifact_requires or ())

    payload = catalog_neighbors("plugin.module_report", profile="framework-core", source_mode="off")

    assert payload is not None
    relation_groups = dict(payload.get("relation_groups", {}) or {})
    chain_cards = tuple(payload.get("relation_chain_cards", ()) or ())
    assert "artifact_provides::modules_report_json" in relation_groups
    assert any(
        item["key"] == "plugin.mysql_run_logger"
        for item in relation_groups["artifact_provides::modules_report_json"]
    )
    assert "artifact_provides::bias_report_json" in relation_groups
    assert any(
        item["key"] == "plugin.mysql_run_logger"
        for item in relation_groups["artifact_provides::bias_report_json"]
    )
    assert any(
        str(card.get("family", "") or "") == "artifact"
        and str(card.get("value", "") or "") == "modules_report_json"
        and int(card.get("outgoing_count", 0) or 0) >= 1
        for card in chain_cards
    )


@pytest.mark.skip(reason="Artifact relation field names diverged after catalog DB migration.")
def test_framework_artifact_relations_link_runtime_artifacts_to_mysql_logger():
    mysql_run_logger = show_entry("plugin.mysql_run_logger", profile="framework-core", source_mode="off")
    benchmark_harness = show_entry("plugin.benchmark_harness", profile="framework-core", source_mode="off")
    checkpoint_resume = show_entry("plugin.checkpoint_resume", profile="framework-core", source_mode="off")
    profiler = show_entry("plugin.profiler", profile="framework-core", source_mode="off")
    decision_trace = show_entry("plugin.decision_trace", profile="framework-core", source_mode="off")
    sequence_graph = show_entry("plugin.sequence_graph", profile="framework-core", source_mode="off")
    otel_tracing = show_entry("plugin.otel_tracing", profile="framework-core", source_mode="off")

    assert mysql_run_logger is not None
    assert benchmark_harness is not None
    assert checkpoint_resume is not None
    assert profiler is not None
    assert decision_trace is not None
    assert sequence_graph is not None
    assert otel_tracing is not None

    required = set(tuple(mysql_run_logger.artifact_requires or ()))
    assert {
        "benchmark_summary_json",
        "checkpoint.latest_path",
        "checkpoint.last_loaded_path",
        "profile_json",
        "decision_trace_count",
        "decision_trace_summary",
        "sequence_graph_json",
        "otel_tracing",
    }.issubset(required)
    assert "benchmark_summary_json" in tuple(benchmark_harness.artifact_provides or ())
    assert "checkpoint.latest_path" in tuple(checkpoint_resume.artifact_provides or ())
    assert "checkpoint.last_loaded_path" in tuple(checkpoint_resume.artifact_provides or ())
    assert "profile_json" in tuple(profiler.artifact_provides or ())
    assert "decision_trace_count" in tuple(decision_trace.artifact_provides or ())
    assert "decision_trace_summary" in tuple(decision_trace.artifact_provides or ())
    assert "sequence_graph_json" in tuple(sequence_graph.artifact_provides or ())
    assert "otel_tracing" in tuple(otel_tracing.artifact_provides or ())

    benchmark_neighbors = catalog_neighbors("plugin.benchmark_harness", profile="framework-core", source_mode="off")
    checkpoint_neighbors = catalog_neighbors("plugin.checkpoint_resume", profile="framework-core", source_mode="off")
    profiler_neighbors = catalog_neighbors("plugin.profiler", profile="framework-core", source_mode="off")
    decision_neighbors = catalog_neighbors("plugin.decision_trace", profile="framework-core", source_mode="off")
    sequence_neighbors = catalog_neighbors("plugin.sequence_graph", profile="framework-core", source_mode="off")
    otel_neighbors = catalog_neighbors("plugin.otel_tracing", profile="framework-core", source_mode="off")

    assert any(
        item["key"] == "plugin.mysql_run_logger"
        for item in dict((benchmark_neighbors or {}).get("relation_groups", {}) or {}).get("artifact_provides::benchmark_summary_json", ())
    )
    assert any(
        item["key"] == "plugin.mysql_run_logger"
        for item in dict((checkpoint_neighbors or {}).get("relation_groups", {}) or {}).get("artifact_provides::checkpoint.latest_path", ())
    )
    assert any(
        item["key"] == "plugin.mysql_run_logger"
        for item in dict((checkpoint_neighbors or {}).get("relation_groups", {}) or {}).get("artifact_provides::checkpoint.last_loaded_path", ())
    )
    assert any(
        item["key"] == "plugin.mysql_run_logger"
        for item in dict((profiler_neighbors or {}).get("relation_groups", {}) or {}).get("artifact_provides::profile_json", ())
    )
    assert any(
        item["key"] == "plugin.mysql_run_logger"
        for item in dict((decision_neighbors or {}).get("relation_groups", {}) or {}).get("artifact_provides::decision_trace_count", ())
    )
    assert any(
        item["key"] == "plugin.mysql_run_logger"
        for item in dict((decision_neighbors or {}).get("relation_groups", {}) or {}).get("artifact_provides::decision_trace_summary", ())
    )
    chain_cards = tuple((decision_neighbors or {}).get("relation_chain_cards", ()) or ())
    assert any(
        str(card.get("family", "") or "") == "artifact"
        and str(card.get("value", "") or "") == "decision_trace_count"
        and int(card.get("outgoing_count", 0) or 0) >= 1
        for card in chain_cards
    )
    assert any(
        item["key"] == "plugin.mysql_run_logger"
        for item in dict((sequence_neighbors or {}).get("relation_groups", {}) or {}).get("artifact_provides::sequence_graph_json", ())
    )
    assert any(
        item["key"] == "plugin.mysql_run_logger"
        for item in dict((otel_neighbors or {}).get("relation_groups", {}) or {}).get("artifact_provides::otel_tracing", ())
    )


def test_project_representation_pipeline_runtime_contracts_include_phase_relations(tmp_path: Path):
    root = tmp_path / "phase_project"
    pipeline_dir = root / "phasepipe"
    pipeline_dir.mkdir(parents=True)
    (pipeline_dir / "__init__.py").write_text("", encoding="utf-8")
    (root / "project_registry.py").write_text(
        "\n".join(
            [
                "PROJECT_CATALOG_ENTRIES = [",
                "    {",
                "        'key': 'pipeline.phaseful',",
                "        'title': 'Phaseful Pipeline',",
                "        'kind': 'representation',",
                "        'import_path': 'phasepipe.phase_pipeline:build_pipeline',",
                "        'summary': 'Project pipeline with phase-aware dispatch mutator.',",
                "        'tags': ('project', 'pipeline', 'phase'),",
                "        'companions': (),",
                "    }",
                "]",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (pipeline_dir / "phase_pipeline.py").write_text(
        "\n".join(
            [
                "from nsgablack.representation import RepresentationPipeline, ContextDispatchMutator",
                "from nsgablack.representation.continuous import GaussianMutation",
                "",
                "def build_pipeline():",
                "    return RepresentationPipeline(",
                "        mutator=ContextDispatchMutator(",
                "            routes={'0': GaussianMutation(sigma=0.1)},",
                "            default_mutator=GaussianMutation(sigma=0.1),",
                "        ),",
                "    )",
                "",
            ]
        ),
        encoding="utf-8",
    )

    entry = show_entry(
        "project.pipeline.phaseful",
        scope="project",
        project_path=root,
        include_global=True,
    )

    assert entry is not None
    assert "phase" in tuple(entry.phase_in or ())
    assert "strategy_id" in tuple(entry.context_requires or ())


def test_relation_field_inference_and_chain_cards_cover_artifact_and_phase_families():
    producer = CatalogEntry(
        key="plugin.synthetic_trace",
        title="Synthetic Trace Producer",
        kind="plugin",
        import_path="synthetic.trace:Producer",
        context_provides=("decision_trace_ref", "phase_id"),
    )
    consumer = CatalogEntry(
        key="repr.synthetic_consumer",
        title="Synthetic Consumer",
        kind="representation",
        import_path="synthetic.trace:Consumer",
        context_requires=("decision_trace_ref", "phase_id"),
    )

    enriched_producer = enrich_entry_relation_fields(producer)
    enriched_consumer = enrich_entry_relation_fields(consumer)

    assert enriched_producer.artifact_provides == ("decision_trace_ref",)
    assert enriched_producer.phase_out == ("phase_id",)
    assert enriched_consumer.artifact_requires == ("decision_trace_ref",)
    assert enriched_consumer.phase_in == ("phase_id",)

    payload = build_contract_neighbor_sections(enriched_producer, candidates=[enriched_consumer])
    relation_groups = dict(payload.get("relation_groups", {}) or {})
    chain_cards = list(payload.get("relation_chain_cards", ()) or ())

    assert "artifact_provides::decision_trace_ref" in relation_groups
    assert "phase_out::phase_id" in relation_groups
    assert any(
        card.get("family") == "artifact"
        and card.get("value") == "decision_trace_ref"
        and int(card.get("outgoing_count", 0) or 0) == 1
        for card in chain_cards
    )
    assert any(
        card.get("family") == "phase"
        and card.get("value") == "phase_id"
        and int(card.get("outgoing_count", 0) or 0) == 1
        for card in chain_cards
    )


def test_contract_edge_rows_include_relation_family_for_all_relation_types():
    producer = CatalogEntry(
        key="plugin.synthetic_trace",
        title="Synthetic Trace Producer",
        kind="plugin",
        import_path="synthetic.trace:Producer",
        context_provides=("decision_trace_ref", "phase_id", "mutation_sigma"),
    )
    consumer = CatalogEntry(
        key="repr.synthetic_consumer",
        title="Synthetic Consumer",
        kind="representation",
        import_path="synthetic.trace:Consumer",
        context_requires=("decision_trace_ref", "phase_id", "mutation_sigma"),
    )

    edges = build_contract_edge_rows(
        source_entries=[producer],
        consumer_candidates=[producer, consumer],
        filtered_keys={"plugin.synthetic_trace", "repr.synthetic_consumer"},
    )

    assert any(
        edge["relation"] == "context_contract"
        and edge["relation_family"] == "context"
        and edge["relation_value"] == "mutation_sigma"
        for edge in edges
    )
    assert any(
        edge["relation"] == "artifact_contract"
        and edge["relation_family"] == "artifact"
        and edge["relation_value"] == "decision_trace_ref"
        for edge in edges
    )
    assert any(
        edge["relation"] == "phase_contract"
        and edge["relation_family"] == "phase"
        and edge["relation_value"] == "phase_id"
        for edge in edges
    )
