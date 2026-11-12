"""Explicit three-call co-design probe; default readiness never calls a model."""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
import time


def verify_framework_grounding():
    """Exercise packaged v8 evidence without contacting either model backend."""
    from nsgablack.catalog.lab_assistant import (
        PROMPT_VERSION, assistant_messages, build_assistant_packet,
    )
    from nsgablack.catalog.lab_assembly import assembly_from_recipe
    from nsgablack.catalog.lab_framework import verify_framework_sources
    from nsgablack.catalog.lab_guide import read_guide
    assert PROMPT_VERSION == "catalog-framework-design-zh-v8"
    assert read_guide()["metadata"]["version"] == "4"
    scenarios = (
        ("冻结的嵌套投影子池父视图删除后，同名视图重新创建，旧任务如何继续？",
         {"contract.pool_nested_views", "contract.pool_view_address"}),
        ("跨 Case 用 SolutionRef 暖启动，内层 GPU 不够，能自行扩大 L0 grant 吗？",
         {"contract.cross_case_resources", "contract.cross_case_input"}),
        ("恢复 event_ready 与 decision_ready，deferred 和 abandoned 有什么区别？",
         {"contract.recovery_classification", "contract.recovery_readonly"}),
        ("贝叶斯 BO 采集决定下一批候选，和软风险 Bias 是同一个角色吗？",
         {"contract.bo_semantics"}),
        ("成员自适应 sigma 在部分接纳后，PopulationChange 索引和提案索引是否相同？",
         {"contract.unit_member_scope"}),
        ("MOEA/D 方向投影 VNS 精修返回时，原始反馈、冻结规则和当前竞争如何处理？",
         {"contract.moead_projection", "contract.pool_projection_once"}),
    )
    checked = []
    for instruction, expected in scenarios:
        packet = build_assistant_packet(assembly_from_recipe("ga"), instruction=instruction)
        facts = packet["framework_context"]
        verify_framework_sources(facts)
        assert not any(value.startswith("source_unavailable:") for value in facts["limitations"])
        assert len(facts["contracts"]) <= 8 and len(facts["components"]) <= 6
        assert expected <= {row["id"] for row in facts["contracts"]}
        messages = assistant_messages(packet)
        assert len(messages) == 2 and messages[0]["role"] == "system"
        assert json.loads(messages[1]["content"]) == packet
        checked.append({"expected_contracts": sorted(expected),
                        "packet_sha256": hashlib.sha256(messages[1]["content"].encode()).hexdigest(),
                        "source_count": len(facts["contracts"]) + len(facts["components"])})
    return {"prompt_version": PROMPT_VERSION, "guide_version": "4", "cases": checked,
            "verified_source_hashes_and_excerpts": True, "model_calls": 0}


def verify(*, live=False, request_id=None):
    from runtime import configure_reader
    from nsgablack.catalog import lab_client
    from nsgablack.catalog.lab_assembly import assembly_from_recipe
    from nsgablack.catalog.lab_design import (apply_design_notes, export_workspace,
                                             import_workspace, notes_digest)
    from nsgablack.catalog.lab_guide import build_guide_context, read_guide
    from nsgablack.catalog.lab_jobs import LabJobError, spec_digest
    assert configure_reader(os.environ) == "only"
    caps = lab_client.assistant_capabilities()
    assert caps["enabled"] and caps["guide"] == read_guide()["metadata"]
    assert caps["guide"]["version"] == read_guide()["metadata"]["version"]
    assert caps["limits"]["requests_per_utc_day"] is None
    assert caps["quota"]["remaining"] is None and caps["quota"]["resets_at"] is None
    assert caps["prompt_version"] == "catalog-framework-design-zh-v8"
    value = {"ok": True, "model_calls": 0, "guide": caps["guide"], "quota": caps["quota"],
             "framework_grounding": verify_framework_grounding()}
    if not live:
        return value
    assert request_id and len(request_id) == 32, "persist_request_identity_before_live_probe"
    spec = assembly_from_recipe("ga")
    original_digest = spec_digest(spec)
    notes = "沿用GA，候选含义和种群关系不变。旧AI曾说网页change只有native，这句话尚未核实。"
    history, turns = [], []
    instructions = [
        "我想先讨论算法，问题公式还没想好。我沿用GA，只想更换交叉：两个父代交换一部分变量，候选含义和种群成员关系不变。"
        "请依据本次框架资料说明复用哪些结构、改变哪个接口，核对旧笔记中关于网页选项的判断，并区分当前选择与全部可用能力。只讨论，不修改装配，draft=null、changes=[]。"
        "给一份简短完整的design_notes建议，明确用户意图、建议和待实现项。",
        "继续前面的交叉设计，现在每个个体还要保存自适应步长，成功后缩小，失败后放大；生存选择和成员替换时跟随对应个体。"
        "请保留之前已确认笔记，依据真实Unit接口解释何时复用、何时扩展、成员字段和恢复需要维护什么。"
        "只读讨论，不修改装配，draft=null、changes=[]，给更新的完整design_notes建议；不要求我先补Problem公式。",
        "继续前面的设计。我还想保存历史避免重复探索，但还没决定是仅降低重复解评分，还是完全禁止它；另外需要日志和checkpoint。"
        "请分清Pool、Bias、搜索选择规则、Plugin的职责，指出当前最关键的澄清，保留交叉与每成员步长的既有设计。"
        "只讨论，draft=null、changes=[]，给完整简短的design_notes建议，不宣称已经实现或运行。",
    ]
    for index, instruction in enumerate(instructions):
        context = build_guide_context(spec, stage="problem" if index == 0 else "assembly",
                                      design_notes=notes, history=history)
        identity = hashlib.sha256((request_id + ":" + str(index)).encode()).hexdigest()[:32]
        job = lab_client.assistant_submit(spec, instruction, request_id=identity, guide_context=context)
        again = lab_client.assistant_submit(spec, instruction, request_id=identity, guide_context=context)
        assert again["job_id"] == job["job_id"]
        deadline = time.monotonic() + 80
        while job["status"] in {"queued", "running"} and time.monotonic() < deadline:
            time.sleep(.3)
            job = lab_client.assistant_poll(job["job_id"])
        assert job["status"] == "succeeded", "co_design_failed:" + str((job.get("error") or {}).get("code", "timeout"))
        result = job["result"]
        assert result["draft"] is None and result["changes"] == []
        assert result["base_digest"] == original_digest and result["verification_status"] == "not_run"
        assert result["design_base_digest"] == notes_digest(notes)
        assert result["online_options"][0]["current_change"] == "native"
        assert result["online_options"][0]["available_changes"] == ["native", "ga_mask", "ga_blend"]
        facts = result["framework_evidence"]
        assert facts["evidence_level"] == "static_source" and facts["contracts"]
        keys = {row["id"] for row in facts["contracts"] + facts["components"]}
        assert keys.intersection(result["evidence_keys"]), "discussion_requires_actual_source_reference"
        for row in facts["contracts"] + facts["components"]:
            assert row["source"]["line"] > 0 and len(row["source"]["sha256"]) == 64
        proposed = apply_design_notes(notes, result)  # explicit test confirmation
        try:
            apply_design_notes(notes + "\n用户另有手动修改", result)
        except LabJobError as exc:
            assert exc.code == "stale_design"
        else:
            raise AssertionError("stale_design_overwrite")
        turns.append({"turn": index + 1, "job_id": job["job_id"], "explanation": result["explanation"],
                      "questions": result["questions"], "design_notes": proposed,
                      "evidence_keys": result["evidence_keys"], "notes_digest": notes_digest(proposed)})
        notes = proposed
        history = [*history, {"role": "user", "content": instruction[:600]},
                   {"role": "assistant", "content": result["explanation"][:600]}][-6:]
    restored = import_workspace(export_workspace(spec, design_notes=notes, history=history))
    assert restored["assembly"] == spec and restored["design_notes"] == notes and restored["history"] == history
    after = lab_client.assistant_capabilities()["quota"]
    assert after["reserved_today"] == caps["quota"]["reserved_today"] + 3
    value.update(model_calls=3, quota=after, turns=turns, assembly_unchanged=True,
                 workspace_roundtrip=True, stale_notes_rejected=True)
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--request-id")
    args = parser.parse_args()
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        value = verify(live=args.live, request_id=args.request_id)
    print(json.dumps(value, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
