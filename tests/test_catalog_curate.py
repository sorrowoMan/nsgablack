import json
from pathlib import Path

import pytest

from nsgablack.catalog.curate import build_sources, curate_packets, load_packets, PACKETS_SCHEMA
from nsgablack.catalog.curation import prepare_packet
from nsgablack.catalog.registry import CatalogEntry


def packet(tmp_path):
    source = tmp_path / "component.py"
    source.write_text('class Example:\n    """An example component."""\n    def act(self):\n        return 1\n')
    entry = CatalogEntry(key="tool.example", title="Example", kind="tool", import_path="sample.component:Example")
    return prepare_packet(entry, [entry], {"sample": tmp_path})


class Store:
    def __init__(self):
        self.records = {}
    def get(self, key, digest, *, model, prompt_version):
        return self.records.get((key, digest, model, prompt_version))
    def put(self, record):
        identity = tuple(record[k] for k in ("entry_key", "source_digest", "model", "prompt_version"))
        assert identity not in self.records
        self.records[identity] = record
        return record


class Generator:
    def __init__(self, *, invalid=False):
        self.calls = 0
        self.invalid = invalid
    def generate(self, value):
        self.calls += 1
        note = {"summary": "示例组件", "inputs_outputs": "输入与输出由来源声明确定。", "use_when": ["查看静态组件"],
                "assembly_steps": [], "pitfalls": [], "related_keys": [], "missing_information": ["尚需运行证据"],
                "evidence_ids": [value["evidence"][0]["id"]]}
        if self.invalid:
            note["related_keys"] = ["invented.component"]
        return {"note": note, "usage": {"total_tokens": 20}, "actual_model": "test-model"}


def test_incremental_curation_reuses_exact_identity_and_regenerates_changed_source(tmp_path):
    initial = packet(tmp_path)
    store, generator = Store(), Generator()
    result = curate_packets({initial["entry_key"]: initial}, store, generator, model="test-model")
    assert result["ok"] and result["generated"] == 1
    again = curate_packets({initial["entry_key"]: initial}, store, generator, model="test-model")
    assert again["generated"] == 0 and again["cached"] == 1 and generator.calls == 1
    source = tmp_path / "component.py"
    source.write_text(source.read_text() + '\n# changed implementation\n')
    entry = CatalogEntry(key="tool.example", title="Example", kind="tool", import_path="sample.component:Example")
    changed = prepare_packet(entry, [entry], {"sample": tmp_path})
    assert changed["source_digest"] != initial["source_digest"]
    final = curate_packets({changed["entry_key"]: changed}, store, generator, model="test-model")
    assert final["generated"] == 1 and generator.calls == 2 and len(store.records) == 2


def test_invalid_generated_links_never_publish_a_record(tmp_path):
    value = packet(tmp_path)
    store = Store()
    result = curate_packets({value["entry_key"]: value}, store, Generator(invalid=True), model="test-model")
    assert not result["ok"] and result["generated"] == 0
    assert result["results"][0]["error"] == "note_evidence_validation_failed"
    assert not store.records


def test_incomplete_provider_diagnostics_explain_failure_without_publishing(tmp_path):
    from nsgablack.catalog.curation_provider import CurationProviderError
    value, store = packet(tmp_path), Store()

    class IncompleteGenerator:
        def generate(self, request):
            raise CurationProviderError("ai_response_incomplete", diagnostics={
                "finish_reason": "length", "completion_tokens": 12288,
                "content_chars": 27000, "raw_content": "private source draft",
            })

    result = curate_packets({value["entry_key"]: value}, store, IncompleteGenerator(), model="test-model")
    assert result["generated"] == 0 and not store.records
    row = result["results"][0]
    assert row["error"] == "ai_response_incomplete"
    assert row["provider_phase"] == "generate"
    assert row["provider_diagnostics"] == {
        "finish_reason": "length", "completion_tokens": 12288, "content_chars": 27000,
    }
    assert "private source draft" not in json.dumps(result)


def test_one_format_repair_keeps_original_evidence_and_counts_both_responses(tmp_path):
    value = packet(tmp_path)
    store = Store()
    class RepairingGenerator(Generator):
        def generate(self, request):
            self.invalid = self.calls == 0
            if self.calls:
                assert request["source_digest"] == value["source_digest"]
                assert "editor_feedback" in request
                assert request["evidence"] == value["evidence"]
                feedback = request["editor_feedback"]
                assert feedback["validation_issue"] == feedback["issue"]
                assert "source_review" in feedback and "previous_tutorial" in feedback
                assert "完整九字段" not in feedback["instruction"]
                assert "当前生成器系统指定的输出格式" in feedback["instruction"]
            return super().generate(request)
    generator = RepairingGenerator()
    result = curate_packets({value["entry_key"]: value}, store, generator, model="test-model")
    assert result["ok"] and result["generated"] == 1 and generator.calls == 2
    assert result["results"][0]["usage"]["total_tokens"] == 40
    assert result["results"][0]["usage"]["format_repairs"] == 1


def test_unknown_keys_and_unbounded_batches_are_refused_before_model_call(tmp_path):
    value, generator = packet(tmp_path), Generator()
    with pytest.raises(ValueError):
        curate_packets({value["entry_key"]: value}, Store(), generator, model="test-model", keys=("invented",))
    with pytest.raises(ValueError):
        curate_packets({value["entry_key"]: value}, Store(), generator, model="test-model", limit=101)
    assert generator.calls == 0


def test_packets_reject_an_unmatched_deployment_index(tmp_path):
    source = tmp_path / "packets.json"
    source.write_text(json.dumps({"schema": PACKETS_SCHEMA, "packets": {}}))
    index = tmp_path / "index.json"
    index.write_text(json.dumps({"schema": "nsgablack.catalog.knowledge_sources/v1", "packets_sha256": "0" * 64}))
    with pytest.raises(ValueError, match="does not match"):
        load_packets(source, index_path=index)


def test_build_sources_prioritizes_the_page_guide_then_a_formal_case_beyond_the_first_two_manifests(tmp_path, monkeypatch):
    import hashlib
    from nsgablack.catalog import registry

    (tmp_path / "component.py").write_text("raise RuntimeError('never import component')\nclass Engine:\n    enabled = True\n", encoding="utf-8")
    entry = CatalogEntry(key="tool.engine", title="Engine", kind="tool", import_path="sample.component:Engine")

    class Catalog:
        def list(self):
            return [entry]

    monkeypatch.setattr(registry, "get_source_catalog", lambda **kwargs: Catalog())
    base = ("**先准备什么：** 保留本Case输入。\n\n**放在哪：** build_solver工厂。\n\n"
            "**接入步骤：** 由Project调用。\n\n```python\ndef build_solver():\n    return 'baseline'\n```\n\n"
            "**怎样判断接对：** 读取正式结果。\n")
    sources = {"old": ("old.md", base), "case": ("run_project.py", "raise RuntimeError('never run Case')\n"),
               "application": ("application.md", base + "\n### 变体一\n完整消费变化。\n```python\nvalue = 'variation'\n```\n")}
    examples = {}
    for identifier, (name, text) in sources.items():
        source = tmp_path / name
        source.write_text(text, encoding="utf-8")
        examples[identifier] = {"id": identifier, "origin": "manifest", "binding": "focused",
                                "kind": "project" if identifier == "case" else "documentation",
                                "title": identifier, "verification": {"status": "source_checked"},
                                "snippets": [{"path": "sample/" + name, "start_line": 1,
                                              "end_line": len(text.splitlines()), "text": text,
                                              "file_sha256": hashlib.sha256(source.read_bytes()).hexdigest()}]}
    examples_index = {"examples": examples, "entries": {entry.key: ["old", "case", "application"]}}
    index_path, packets_path = tmp_path / "knowledge.json", tmp_path / "packets.json"
    assert build_sources({"sample": tmp_path}, index_path, packets_path, examples_index=examples_index)["ok"]
    packet = load_packets(packets_path, index_path=index_path)[entry.key]
    assert [guide["title"] for guide in packet["usage_examples"]] == ["application", "case"]
    paths = {item["path"] for item in packet["evidence"]}
    assert "sample/application.md" in paths and "sample/run_project.py" in paths and "sample/old.md" not in paths
    examples_index["entries"][entry.key] = ["case", "application", "old"]
    build_sources({"sample": tmp_path}, index_path, packets_path, examples_index=examples_index)
    assert load_packets(packets_path)[entry.key]["source_digest"] == packet["source_digest"]


class DetailedGenerator(Generator):
    requires_tutorial = True
    requires_source_review = True

    def __init__(self, *, code="def adjusted(value):\n    return value + 1", language="python", placement="独立数值函数"):
        super().__init__()
        self.code, self.language, self.placement = code, language, placement
        self.reviews = 0

    def generate(self, request):
        result = super().generate(request)
        ids = result["note"]["evidence_ids"]
        result["note"]["tutorial"] = {
            "scenario": "通过明确输入调用数值工具。", "preparation": ["调用方提供输入值。"],
            "placement": self.placement, "code": self.code, "language": self.language,
            "execution_flow": ["输入交给函数，返回值由调用方接收。"], "result_checks": ["检查返回的数值。"],
            "extensions": [{"title": "显式偏移", "purpose": "由调用方选择偏移。", "placement": "替换独立函数。",
                "code": "def adjusted(value, offset):\n    return value + offset", "language": "python",
                "effect": "偏移来自调用参数。", "limits": ["调用方须提供偏移值。"], "evidence_ids": ids}],
            "evidence_ids": ids}
        return result

    def review(self, packet, note):
        self.reviews += 1
        return {"note": {"decision": "publish", "issues": [],
            "checks": ["输入来自显式参数。", "返回值由调用方消费。", "变体保留明确偏移输入。"],
            "evidence_ids": note["evidence_ids"]}}


@pytest.mark.parametrize("language,code", [("bash", "python run_project.py --group default"),
                                           ("text", "Read the selected document, then follow its actual entry.")])
def test_non_python_tutorial_is_not_sent_to_python_api_parser_and_still_needs_review(tmp_path, language, code):
    value, store = packet(tmp_path), Store()
    generator = DetailedGenerator(code=code, language=language, placement="文档导航入口")
    result = curate_packets({value["entry_key"]: value}, store, generator, model="test-model", workers=1)
    assert result["ok"] and generator.reviews == 1 and len(store.records) == 1
    assert result["results"][0]["usage"]["api_non_python_snippets"] == 1


def test_formal_case_signature_check_cannot_be_bypassed_by_omitting_source_roots(tmp_path):
    value, store = packet(tmp_path), Store()
    generator = DetailedGenerator(code="def build_solver():\n    return object()", placement="cases/search/build_solver.py")
    result = curate_packets({value["entry_key"]: value}, store, generator, model="test-model", workers=1)
    assert not result["ok"] and not store.records and generator.reviews == 0
    assert generator.calls == 2
    assert "Formal Case builder must explicitly accept" in result["results"][0]["validation_issue"]


def test_leaf_unknown_external_call_is_not_mistaken_for_a_case_or_verified_api(tmp_path):
    value, store = packet(tmp_path), Store()
    generator = DetailedGenerator(code="from math import sqrt\ndef root(value):\n    return sqrt(value)")
    result = curate_packets({value["entry_key"]: value}, store, generator, model="test-model", workers=1)
    assert result["ok"] and generator.reviews == 1
    assert result["results"][0]["usage"]["api_unknown_calls"] == 1
    assert result["results"][0]["usage"]["api_checked_calls"] == 0


def test_failure_feedback_does_not_pair_prior_review_with_a_different_invalid_draft(tmp_path):
    value, store = packet(tmp_path), Store()
    class Drafts(DetailedGenerator):
        def generate(self, request):
            if self.calls:
                assert request["editor_feedback"]["source_review"]["decision"] == "revise"
            result = super().generate(request)
            if self.calls == 2:
                result["note"]["tutorial"]["code"] = "def broken("
            return result

        def review(self, packet, note):
            self.reviews += 1
            return {"note": {"decision": "revise", "issues": [{"location": "code", "problem": "First draft needs correction",
                "required_change": "Use the actual operation", "evidence_ids": note["evidence_ids"]}],
                "checks": ["First draft inspected"], "evidence_ids": note["evidence_ids"]}}
    generator = Drafts()
    result = curate_packets({value["entry_key"]: value}, store, generator, model="test-model", workers=1,
                            include_failed_tutorial=True)
    row = result["results"][0]
    assert not result["ok"] and generator.reviews == 1 and not store.records
    assert row["previous_tutorial"]["code"] == "def broken("
    assert "source_review" not in row


def test_exhausted_review_format_error_does_not_rewrite_the_tutorial(tmp_path):
    from nsgablack.catalog.curation_provider import CurationProviderError
    value, store = packet(tmp_path), Store()
    class InvalidReview(DetailedGenerator):
        def review(self, packet, note):
            self.reviews += 1
            raise CurationProviderError("ai_review_format_invalid")
    generator = InvalidReview()
    result = curate_packets({value["entry_key"]: value}, store, generator, model="test-model", workers=1)
    assert not result["ok"] and not store.records
    assert generator.calls == generator.reviews == 1
    assert result["results"][0]["provider_phase"] == "review"


def test_cli_run_forwards_explicit_trusted_roots_to_the_api_gate(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from nsgablack.catalog import curate
    class CliStore(Store):
        def ensure_schema(self):
            return None
    monkeypatch.setattr(curate, "load_packets", lambda *args, **kwargs: {"mlblack.test": {}})
    monkeypatch.setattr(curate, "load_deepseek_config", lambda *args: SimpleNamespace(model="test-model"))
    monkeypatch.setattr(curate, "resolve_knowledge_store", lambda **kwargs: CliStore())
    def generator(config, *, allow_paid_requests=False):
        assert allow_paid_requests is True
        return object()
    monkeypatch.setattr(curate, "DeepSeekGenerator", generator)
    def capture(*args, **kwargs):
        assert kwargs["source_roots"] == {"mlblack": tmp_path}
        return {"ok": True}
    monkeypatch.setattr(curate, "curate_packets", capture)
    assert curate.main(["run", "--index", "index.json", "--packets", "packets.json", "--config", "private.json",
                        "--execute", "--keys", "mlblack.test", "--root", "mlblack=" + str(tmp_path)]) == 0


@pytest.mark.parametrize("flags", [[], ["--keys", "tool.example"], ["--execute"], ["--execute", "--keys", " , "]])
def test_cli_refuses_unscoped_or_implicit_paid_work_before_loading_anything(monkeypatch, flags):
    from nsgablack.catalog import curate
    monkeypatch.setattr(curate, "load_packets", lambda *a, **kw: pytest.fail("Denied command must not load inputs"))
    monkeypatch.setattr(curate, "load_deepseek_config", lambda *a: pytest.fail("Denied command must not read credentials"))
    with pytest.raises(SystemExit) as error:
        curate.main(["run", "--index", "index.json", "--packets", "packets.json", "--config", "private.json", *flags])
    assert error.value.code == 2


def test_cli_unknown_keys_stop_before_provider_or_writer(monkeypatch):
    from nsgablack.catalog import curate
    monkeypatch.setattr(curate, "load_packets", lambda *a, **kw: {"tool.present": {}})
    monkeypatch.setattr(curate, "load_deepseek_config", lambda *a: pytest.fail("Unknown keys must not read credentials"))
    monkeypatch.setattr(curate, "resolve_knowledge_store", lambda **kw: pytest.fail("Unknown keys must not initialize writer"))
    assert curate.main(["run", "--index", "index.json", "--packets", "packets.json", "--config", "private.json",
                        "--execute", "--keys", "tool.unknown"]) == 1
