"""Global online declarations stay distinct from current instance selection."""
from copy import deepcopy
import json

from nsgablack.catalog import lab_assembly
from nsgablack.catalog.lab_assistant import (
    PROMPT_VERSION, SYSTEM_PROMPT, assistant_messages, build_assistant_packet,
)


def test_ga_only_selection_does_not_hide_available_algorithms_or_orchestration():
    packet = build_assistant_packet(lab_assembly.assembly_from_recipe("ga"), instruction="只讨论方向精修和返回竞争。")
    current = packet["online_options"]
    available = packet["online_capabilities"]
    assert len(current) == 1 and current[0]["component"] == "adapter.nsga2"
    assert {row["component"] for row in available["adapters"]} == {
        row["key"] for row in packet["assembly_catalog"]["components"]["adapters"]}
    assert {"adapter.moead", "adapter.vns"} <= {row["component"] for row in available["adapters"]}
    assert {"serial", "multi", "repeat"} <= set(available["plan_kinds"])
    assert available["pool_input"] == packet["assembly_catalog"]["document_shape"]["node"]["input"]
    assert available["return_from"] == packet["assembly_catalog"]["document_shape"]["node"]["return_from"]
    assert available["evidence_level"] == "declaration_not_execution"
    assert available["scope"] == "available_bindings_not_current_instances"
    assert any("nested views require a view source" in rule for rule in available["assembly_rules"])
    user = json.loads(assistant_messages(packet)[1]["content"])
    assert user["online_capabilities"] == available
    assert len(json.dumps({"messages": assistant_messages(packet)}, ensure_ascii=False).encode("utf-8")) < 127 * 1024


def test_bias_description_preserves_declared_norm_meaning_without_risk_alias():
    packet = build_assistant_packet(lab_assembly.assembly_from_recipe("ga"), instruction="预测风险软评分和BO有什么区别？")
    original = next(row for row in packet["assembly_catalog"]["components"]["biases"] if row["key"] == "bias.l2_preference")
    summary = next(row for row in packet["online_capabilities"]["biases"] if row["component"] == "bias.l2_preference")
    assert summary["label"] == original["label"] and "范数" in summary["label"]
    assert summary["notes"] == original["notes"] and "L2" in summary["notes"]
    assert "risk" not in json.dumps(summary).lower() and "风险" not in json.dumps(summary, ensure_ascii=False)
    assert "不能为能运行而擅自替换风险含义" in SYSTEM_PROMPT
    assert "仅仅需要模型或外部预测源，不表示超出 Bias 职责" in SYSTEM_PROMPT
    assert PROMPT_VERSION == packet["prompt_version"] == "catalog-framework-design-zh-v8"


def test_summary_cannot_invent_options_omitted_from_current_service_table(monkeypatch):
    spec = lab_assembly.assembly_from_recipe("ga")
    narrow = deepcopy(lab_assembly.assembly_catalog())
    narrow["components"]["adapters"] = [row for row in narrow["components"]["adapters"] if row["key"] == "adapter.nsga2"]
    narrow["components"]["biases"] = []
    narrow["plan_kinds"] = ["stage"]
    narrow["document_shape"]["node"]["input"]["source"] = ["main"]
    narrow["document_shape"]["node"].pop("return_from")
    monkeypatch.setattr(lab_assembly, "assembly_catalog", lambda: deepcopy(narrow))
    packet = build_assistant_packet(spec, instruction="当前表到底有哪些可选绑定？")
    available = packet["online_capabilities"]
    assert [row["component"] for row in available["adapters"]] == ["adapter.nsga2"]
    assert available["biases"] == [] and available["plan_kinds"] == ["stage"]
    assert available["pool_input"]["source"] == ["main"] and "return_from" not in available


def test_capability_projection_is_detached_and_does_not_change_worker_catalog():
    before = lab_assembly.assembly_catalog()
    packet = build_assistant_packet(lab_assembly.assembly_from_recipe("ga"), instruction="查看装配选择")
    packet["online_capabilities"]["adapters"][0]["operations"].clear()
    packet["online_capabilities"]["plan_kinds"].clear()
    packet["online_capabilities"]["biases"][0]["notes"] = "modified local copy"
    assert packet["assembly_catalog"] == before == lab_assembly.assembly_catalog()
