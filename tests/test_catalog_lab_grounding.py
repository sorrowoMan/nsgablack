"""Current runtime contracts reach both production and short-model inputs."""
import hashlib
import json

import pytest

from nsgablack.catalog import lab_framework as framework
from nsgablack.catalog.lab_assembly import assembly_catalog, assembly_from_recipe
from nsgablack.catalog.lab_assistant import (
    AssistantProviderError, PROMPT_VERSION, assistant_messages, build_assistant_packet,
)


@pytest.mark.parametrize("query,expected,clauses", [
    ("SolutionRef 读取同值候选、派生新提案和 repair 的身份版本区别",
     {"contract.pool_identity"}, ("读取已有解", "建立新 token", "repair 保留提案 token")),
    ("MOEA/D 子池的子池嵌套，父视图删除，投影是不是再次应用",
     {"contract.pool_nested_views"}, ("不递归标量化", "不级联删除", "view_id/revision")),
    ("跨 Case 使用 SolutionRef 和 ResourceContext，L0 GPU grant 如何传递",
     {"contract.cross_case_resources", "contract.cross_case_input"},
     ("不能各自复制完整父额度", "不能仅给子 Case 一个父池的 SolutionRef", "接收方建立本地地址")),
    ("durable 围栏暂时不可读时恢复应该 deferred 还是 abandoned，要不要重放？",
     {"contract.recovery_classification", "contract.recovery_readonly"},
     ("不可读或核验失败时保留 deferred", "event_ready 尚无持久处置", "不重跑 Problem")),
    ("BO 贝叶斯优化是不是软评分 Bias，真实观测与模型采集是怎么分工的",
     {"contract.bo_semantics", "contract.bias_plugin"},
     ("真实观测与候选成员分开", "硬可行性准入门")),
    ("每成员 sigma 步长经 member_fields on_members_changed 维护，UnitInputSpec 怎么传给变异",
     {"contract.unit_member_state", "contract.unit_inputs"},
     ("返回扩展字段更新", "只读 UnitInputs", "不借共享 context 隐式绑定")),
])
def test_complete_runtime_conditions_are_selected_from_current_request(query, expected, clauses):
    facts = framework.build_framework_facts(query)
    assert expected <= {row["id"] for row in facts["evidence"]}
    assert len(facts["text"]) <= 2200
    for clause in clauses:
        assert clause in facts["text"]
    for row in facts["evidence"]:
        source = row["source"]
        data = (framework._ROOT / source["path"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == source["sha256"]
        assert "\n".join(data.decode("utf-8-sig").splitlines()[
            source["line"] - 1:source["end_line"]]) == row["excerpt"]


def test_new_contracts_reach_actual_production_messages_without_extra_registry():
    packet = build_assistant_packet(assembly_from_recipe("ga"), instruction="已有持久处置暂时不可读，恢复是否重放")
    assert packet["prompt_version"] == PROMPT_VERSION == "catalog-framework-design-zh-v8"
    user = json.loads(assistant_messages(packet)[1]["content"])
    rows = {row["id"]: row for row in user["framework_context"]["contracts"]}
    assert "decision_not_durable" in rows["contract.recovery_classification"]["excerpt"]
    assert "cannot evaluate candidates" in rows["contract.recovery_readonly"]["excerpt"]


def test_nested_addressing_uses_frozen_identity_even_when_algorithm_name_is_repeated():
    facts = framework.build_framework_facts(
        "MOEA/D 方向经VNS产生派生视图；VNS开始后父视图释放又同名重建，"
        "另一个流程为同token产生新版本，应该追读最新值吗，后代按名字寻找吗？")
    assert {"contract.pool_nested_views", "contract.pool_view_address", "contract.pool_identity"} <= {
        row["id"] for row in facts["evidence"]}
    assert "同名新视图不会接管旧子树" in facts["text"]


@pytest.mark.parametrize("query", [
    "某个方向子池把费用和时间投影成一个标量，VNS 从中找到 y。"
    "ideal point 已改变，能否把标量写回原始目标并覆盖方向槽位？如果继续第二层精修，投影能再用一遍吗？",
    "MOEA/D 返回精修后的候选时按哪套分数竞争？后续精修还应再标量化已投影反馈吗？",
    "方向精修的原始目标、返回替换和 ObjectiveProjection 如何保持一致？",
])
def test_direction_refinement_includes_projection_once_in_actual_short_prompt(query):
    facts = framework.build_framework_facts(query)
    assert len(facts["text"]) <= 2200
    assert "contract.pool_projection_once" in {row["id"] for row in facts["evidence"]}
    # Assert what the model actually receives, not only a longer source_refs entry.
    assert "对本层新求值的 selection feedback 应用一次" in facts["text"]
    assert "不是先把父池标量再乘一次权重" in facts["text"]
    assert "已带 subpool_projection 的反馈再次投影会报错" in facts["text"]
    assert "母池与 Evaluation Event 始终保存原目标向量" in facts["text"]
    assert "返回时 MOEA/D 正常重评、更新 ideal" in facts["text"]


def test_catalog_evidence_retains_full_source_but_prompt_uses_only_summary():
    facts = framework.build_framework_facts("BO 贝叶斯优化是不是 Bias？")
    source = next(row for row in facts["evidence"] if row["id"] == "catalog.adapter.bayesian_optimization")
    assert "minimal_wiring =" in source["excerpt"]
    assert "minimal_wiring =" not in facts["text"]
    assert "同步单目标贝叶斯优化" in facts["text"]


def test_multiple_requested_topics_do_not_erase_lazy_unit_or_plugin_boundaries():
    packet = build_assistant_packet(assembly_from_recipe("ga"), instruction=(
        "成员 sigma 经 member_fields on_members_changed 维护，UnitInputSpec 提供只读变异输入；"
        "Unit 应懒创建，同时装配 Plugin 日志与检查点。"))
    keys = framework.evidence_keys(packet["framework_context"])
    assert {"contract.unit_member_state", "contract.unit_inputs", "contract.unit_members",
            "contract.unit_lazy", "contract.plugin_lifecycle"} <= keys
    assert len(json.dumps({"messages": assistant_messages(packet)}, ensure_ascii=False).encode("utf-8")) < 127 * 1024


def test_source_drift_after_packet_creation_blocks_transport(monkeypatch):
    packet = build_assistant_packet(assembly_from_recipe("ga"), instruction="跨 Case L0 授权")
    read = framework._read_source

    def changed(path):
        lines, digest = read(path)
        return lines, "0" * 64

    monkeypatch.setattr(framework, "_read_source", changed)
    with pytest.raises(AssistantProviderError, match="ai_framework_mismatch"):
        assistant_messages(packet)


def test_fabricated_excerpt_is_not_valid_current_evidence():
    value = framework.build_framework_context("恢复", assembly_catalog=assembly_catalog())
    value["contracts"][0]["excerpt"] = value["contracts"][0]["excerpt"].replace("Problem", "problem", 1)
    # Keep shape valid: a source hash alone does not authorize fabricated prose.
    with pytest.raises(ValueError, match="framework_evidence_stale"):
        framework.verify_framework_sources(value)


def test_missing_runtime_anchor_is_reported_without_cached_facts(monkeypatch):
    read = framework._read_source

    def without_recovery(path):
        lines, digest = read(path)
        return [line for line in lines if not line.startswith("恢复分类由 BlackBase")], digest

    monkeypatch.setattr(framework, "_read_source", without_recovery)
    facts = framework.build_framework_facts("恢复 deferred abandoned")
    assert "contract.recovery_classification" not in {row["id"] for row in facts["evidence"]}
    assert "source_unavailable:docs/architecture/RUNTIME_CONTRACTS_CN.md" in facts["limitations"]
    assert "资料不可用：docs/architecture/RUNTIME_CONTRACTS_CN.md" in facts["text"]


def test_rendering_is_deterministic_and_has_no_gold_or_rubric_input():
    first = framework.build_framework_facts("BO 与 Bias")
    assert first == framework.build_framework_facts("BO 与 Bias")
    with pytest.raises(TypeError):
        framework.build_framework_facts("BO 与 Bias", rubric="send test answer")
    changed = framework.build_framework_facts("继续", design_notes="已确认跨Case输入必须建立本地地址和L0授权")
    assert "contract.cross_case_input" in {row["id"] for row in changed["evidence"]}


@pytest.mark.parametrize("limit", [True, 0, 1199, 12001, 1.5])
def test_short_profile_limits_are_explicit(limit):
    with pytest.raises(ValueError, match="framework_facts_limit_invalid"):
        framework.build_framework_facts("Unit", max_chars=limit)
