"""Read-only checks for source coverage and separate AI maintenance details."""
from collections import Counter
from contextlib import ExitStack, redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
from unittest.mock import patch

from runtime import configure_reader


def verify():
    assert configure_reader(os.environ) == "only"
    assert not Path("/run/secrets/deepseek.json").exists()
    from nsgablack.catalog import curation_ui, dashboard, examples_ui, facade
    from nsgablack.catalog.curation_provider import DeepSeekGenerator
    from nsgablack.catalog.curation_store import CatalogKnowledgeStore
    from nsgablack.catalog.fingerprint import catalog_entries_digest
    from nsgablack.catalog.registry import get_source_catalog
    from nsgablack.core.blank_solver import SolverBase
    from nsgablack.units import UnitBinding
    from streamlit.testing.v1 import AppTest
    from verify_examples import (_verify_material_caption, _example_publication_digest,
                                 _verify_source_files, SOURCE_ROOTS)
    from verify_release import verify_manifest

    overlay = json.loads(Path("/opt/catalog/status-overlay.json").read_text())
    for name, expected in overlay["preserved_artifacts"].items():
        assert hashlib.sha256(Path("/opt/catalog", name).read_bytes()).hexdigest() == expected
    material = examples_ui.examples_snapshot()
    assert material.get("available")
    manifest, whitelist, _files = verify_manifest(Path("/opt/catalog/release-manifest.json"), None)
    base = json.loads(Path("/opt/catalog/status-base-manifest.json").read_text())
    index_sha = hashlib.sha256(Path("/opt/catalog/examples.json").read_bytes()).hexdigest()
    publication = _example_publication_digest(manifest, base,
        preserved_index_sha256=overlay["preserved_artifacts"]["examples.json"], actual_index_sha256=index_sha)
    assert material["index"]["publication_digest"] == publication
    source_summary = _verify_source_files(material["index"], whitelist, SOURCE_ROOTS)
    packets = json.loads(Path("/opt/catalog/knowledge-packets.json").read_text())["packets"]
    touched = {"nsgablack/catalog/examples_ui.py", "nsgablack/catalog/curation_ui.py"}
    assert not any(item.get("path") in touched for packet in packets.values() for item in packet.get("evidence", ()))
    categories = material["material_categories"]
    snapshot = curation_ui.knowledge_snapshot()
    assert snapshot.get("available")
    calls = {"model": 0, "unit": 0, "solver": 0, "knowledge_write": 0}

    def forbidden(kind):
        def reject(*args, **kwargs):
            calls[kind] += 1
            raise AssertionError("catalog_status_read_crossed_" + kind)
        return reject

    reports, profiles = [], {}
    with ExitStack() as stack:
        for name in ("generate", "review", "_complete"):
            stack.enter_context(patch.object(DeepSeekGenerator, name, forbidden("model")))
        stack.enter_context(patch.object(UnitBinding, "build", forbidden("unit")))
        stack.enter_context(patch.object(SolverBase, "run", forbidden("solver")))
        stack.enter_context(patch.object(CatalogKnowledgeStore, "put", forbidden("knowledge_write")))
        for profile in ("default", "framework-core"):
            entries = facade.list_entries(profile=profile, scope="framework", source_mode="only", limit=None)
            assert catalog_entries_digest(entries) == catalog_entries_digest(get_source_catalog(profile=profile).list())
            by_key = {entry.key: entry for entry in entries}
            keys = snapshot["index"]["profiles"][profile]
            counts = Counter(curation_ui.entry_knowledge(key, snapshot)["status"] for key in keys)
            profiles[profile] = {"catalog_entries": len(entries), "ai_cache": dict(counts)}
            samples = ["adapter.composite"]
            for group in ({"migration_reference"}, {"documentation_navigation", "project_case_navigation"}):
                key = next((key for key, category in sorted(categories.items()) if category in group and key in by_key), None)
                if key:
                    samples.append(key)
            for key in dict.fromkeys(samples):
                app = AppTest.from_file(dashboard.__file__, default_timeout=90)
                app.query_params.update({"profile": profile, "scope": "framework", "kind": "all",
                                         "query": key, "selected": key, "detail_tab": "overview"})
                app.run()
                assert not app.exception, "status_page_exception"
                assert app.session_state["catalog_ui_source_mode"] == "only"
                assert app.session_state["catalog_ui_selected"] == key
                assert not app.get("progress"), "cache_must_not_look_like_completion_progress"
                _verify_material_caption(app, categories)
                maintenance = [item for item in app.sidebar.expander if item.label == "资料维护详情"]
                assert len(maintenance) == 1 and maintenance[0].proto.expanded is False
                text = "\n".join(item.value for item in maintenance[0].caption)
                expected = (f"AI 缓存 · 当前目录范围 {len(keys)} 项：可复用 {counts['current']} · "
                            f"已过期 {counts['stale']} · 未生成 {counts['missing']} · 校验未通过 {counts['invalid']}")
                assert expected in text, "maintenance_counts_do_not_match_live_cache"
                assert "仍缺完整说明" not in "\n".join(item.value for item in app.caption)
                reports.append({"profile": profile, "entry_key": key, "material_category": categories[key]})
    assert not any(calls.values())
    assert profiles["default"]["ai_cache"] == overlay["previous_ai_cache"]
    return {"ok": True, "pages": reports, "profiles": profiles,
            "material_categories": dict(Counter(categories.values())), "execution_calls": calls,
            "preserved_artifacts": overlay["preserved_artifacts"], "base_example_publication": publication,
            "preserved_example_sources": source_summary, "model_calls": 0,
            "desktop_or_browser_actions": 0}


def main():
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = verify()
        code = 0
    except Exception as exc:
        result, code = {"ok": False, "error_type": type(exc).__name__}, 1
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
