"""Bounded fresh-session checks using the existing two assistant entry points.

The tasks are development acceptance prompts, not a training corpus or a blind
benchmark. Protocol checks and independent semantic review are kept separate.
No Case is run, no source patch is applied, and no reference answer is sent.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from .assistant_evaluation import content_digest, model_configuration_metadata
from .lab_assistant import AssistantProviderError, build_assistant_packet, assistant_messages, validate_draft
from .lab_assembly import assembly_from_recipe
from .lab_model_provider import complete_project_turn, create_assistant_generator, load_assistant_model_config
from .lab_project_assistant import ProjectAssistantRuntime
from .lab_project_sources import ProjectSourceRegistry


SCHEMA = "nsgablack.assistant_session_acceptance/v1"
CONFIRMED_DESIGN = """# 已确认的教学工程设计

- 原问题和约束保持当前定义；本次只讨论搜索结构，尚未采用新代码或启动试跑。
- 使用原来的 GA 实例及其 Unit，保留原生生存选择规则。
- 希望从每轮最终留下的成员中挑选精英，分别交给 VNS，再返回同一个 GA 竞争。
- 精英池只引用候选，不复制可写的算法排名；每个起点的精修额度单独设置。
- 父代来源、成员附加字段和 MOEA/D 方向试验均为待讨论事项，不是已完成的改动。
"""

CASES = (
    {"id": "ga_final_members", "history": "fresh",
     "instruction": "我想保留当前 GA 的生存规则，每轮从它最终留下的成员挑几个精英，分别用 VNS 精修，再交回原 GA。结合当前内容告诉我改哪些位置、哪些机制能直接复用；先讨论方案。",
     "review_points": ["区分原生最终成员与整批硬接纳候选，精英维护不要求复制 NSGA 排序。",
                       "Pool 交付精确候选，GA 和 VNS 保留各自 Unit，并返回同一 GA 竞争。",
                       "明确现有入口支持范围与需写代码的扩展，未执行不声称效果。"]},
    {"id": "ga_second_parent", "history": "ga_final_members",
     "instruction": "刚才的精修和返回逻辑保留。我现在只想把交叉的第二个父代改成从共享 elite 池里挑，第一个父代和交叉公式不变。这里该改哪里，是否需要重做 Unit？请深入到接口和代码位置。",
     "review_points": ["保留精修和返回决定，父代选择与交叉数学分别解释。",
                       "不因更改父代来源就要求新建 Unit；说明来源权限及精确引用。",
                       "给出有依据的接口或文件落点，承认当前入口没有源码写权限，不伪造已应用。"]},
    {"id": "member_cooldown", "history": "fresh",
     "instruction": "另一个想法：每个种群成员加一个 cooldown 整数字段，旧成员经历一次生存选择仍留下就加一，新加入者归零。GA 选择规则不动。请结合当前工程说明结构、更新和恢复怎么接，尤其淘汰、重排和部分接纳后怎样保持对应。",
     "review_points": ["把每成员状态放入 Unit 的显式成员字段及维护钩子，而非共享 context 或 Plugin。",
                       "按成员变更的准确旧位置或来源维护，区分成员选择坐标与原始提案接纳坐标。",
                       "复用现有 builder/codec、惰性创建与事务恢复，不宣称只声明字段就自动解决全部语义。"]},
    {"id": "direction_coarse_fine", "history": "fresh",
     "instruction": "我还想另开一个 MOEA/D 试验：挑两个方向，各自先用较粗 VNS 再用较细 VNS 精修，最后把找到的解送回 MOEA/D。这个流程里每层究竟比较什么，哪些结果和状态应该保留？现有机制能承接到哪一步？",
     "review_points": ["方向来源属于具体 MOEA/D 实例，任务冻结方向权重和参考点。",
                       "起点及后续邻域消费同一投影，递归细精修不重复投影，不覆盖原始目标。",
                       "交回当前任务最终候选而非累计历史，MOEA/D 依当前规则竞争；不夸大在线绑定或运行证据。"]},
)


class RequestBudget:
    def __init__(self, maximum=20, *, already_used=0):
        if type(maximum) is not int or not 1 <= maximum <= 20:
            raise ValueError("invalid_acceptance_request_limit")
        if type(already_used) is not int or not 0 <= already_used <= maximum:
            raise ValueError("invalid_acceptance_prior_requests")
        self.maximum, self.used, self.already_used = maximum, already_used, already_used

    def reserve(self):
        if self.used >= self.maximum:
            raise AssistantProviderError("acceptance_request_limit")
        self.used += 1


def create_teaching_project(directory: Path) -> tuple[ProjectSourceRegistry, str]:
    """Copy an existing formal teaching Project, without importing any Case."""
    source = Path(__file__).resolve().parents[1] / "examples/cases/assembled_ga_vns"
    target = Path(directory) / "session_design"
    shutil.copytree(source, target, ignore=shutil.ignore_patterns(
        ".blackbase", "results", "__pycache__", "checkpoints", "*.pyc"))
    (target / "DESIGN.md").write_text(CONFIRMED_DESIGN, encoding="utf-8")
    return ProjectSourceRegistry({"acceptance": Path(directory)}), "acceptance:session_design"


def _history(parent, limit):
    if parent is None or parent.get("protocol") != "passed":
        return []
    return [{"role": "user", "content": parent["instruction"][:limit]},
            {"role": "assistant", "content": parent["answer"]["explanation"][:limit]}]


def _summary(rows, budget):
    return {"total": len(rows), "http_requests": budget.used,
            "new_http_requests": budget.used - budget.already_used,
            "protocol_passed": sum(row["protocol"] == "passed" for row in rows),
            "semantic_passed": sum(row["semantic_review"] == "pass" for row in rows),
            "semantic_failed": sum(row["semantic_review"] == "fail" for row in rows),
            "semantic_pending": sum(row["semantic_review"] in {"pending", "needs_more_evidence"} for row in rows)}


def _record_input(row, packet):
    row["input"] = {"base_digest": packet["base_digest"],
        "framework_basics": deepcopy(packet.get("framework_basics")),
        "framework_context": deepcopy(packet.get("framework_context")),
        "project_state": deepcopy(packet.get("project_state")),
        "guide_metadata": deepcopy(packet.get("guide_metadata")),
        "confirmed_notes_sha256": content_digest(CONFIRMED_DESIGN)}
    row["packet_sha256"] = content_digest(packet)


def run_acceptance(generator, *, sources, project_id, maximum_requests=20, already_used=0,
                   entries=("assembly", "project"), case_ids=None,
                   source_report_sha256=None, project_model_calls=4, project_complete=None, progress=None):
    """Bounded deliveries, with fresh model state for independent scenarios.

    Selecting a subset or consuming a previous run's remaining budget is a
    development followup. It cannot turn earlier failures into blind success.
    """
    entries = tuple(entries)
    if not entries or len(set(entries)) != len(entries) or set(entries).difference(("assembly", "project")):
        raise ValueError("invalid_acceptance_entries")
    selected_ids = {case["id"] for case in CASES} if case_ids is None else set(case_ids)
    if not selected_ids or selected_ids.difference(case["id"] for case in CASES):
        raise ValueError("invalid_acceptance_cases")
    cases = tuple(case for case in CASES if case["id"] in selected_ids)
    if any(case["history"] != "fresh" and case["history"] not in selected_ids for case in cases):
        raise ValueError("acceptance_followup_requires_parent_case")
    if source_report_sha256 is not None and (not isinstance(source_report_sha256, str)
            or len(source_report_sha256) != 64 or any(c not in "0123456789abcdef" for c in source_report_sha256)):
        raise ValueError("invalid_acceptance_source_report")
    if type(project_model_calls) is not int or not 1 <= project_model_calls <= 4:
        raise ValueError("invalid_acceptance_project_model_limit")
    budget = RequestBudget(maximum_requests, already_used=already_used)
    transport = project_complete or complete_project_turn
    request_records = []
    active_case = {"id": None}

    def complete(owner, messages, tools):
        budget.reserve()
        record = {"entry": "project", "case_id": active_case["id"], "request": budget.used,
                  "messages_sha256": content_digest(messages)}
        request_records.append(record)
        turn = transport(owner, messages, tools)
        # Keep visible output for protocol-failure diagnosis. Private reasoning
        # is deliberately excluded, as in the ordinary assistant UI.
        content = turn.get("message", {}).get("content")
        if isinstance(content, str):
            record["assistant_content"] = content
            record["assistant_content_sha256"] = content_digest(content)
            record["assistant_content_length"] = len(content)
        record["message_keys"] = sorted(key for key in turn.get("message", {}) if key != "reasoning_content")
        record["finish_reason"] = turn.get("finish_reason")
        record["model"] = turn.get("model")
        return turn

    runtime = ProjectAssistantRuntime(sources, complete=complete,
                                      max_model_calls=project_model_calls, max_tool_calls=6)
    rows = []
    config = getattr(generator, "config", None)
    configuration = model_configuration_metadata(config) if config is not None else None
    followup = already_used != 0 or entries != ("assembly", "project") or len(cases) != len(CASES)
    report = {"schema": SCHEMA, "created_at": datetime.now(timezone.utc).isoformat(),
              "kind": "development_followup" if followup else "development_acceptance",
              "source_report_sha256": source_report_sha256, "already_used_http_requests": already_used,
              "project_limits": {"model_calls_per_delivery": project_model_calls, "tool_calls_per_delivery": 6},
              "model_configuration": configuration,
              "project_id": project_id, "maximum_http_requests": budget.maximum,
              "cases": rows, "request_records": request_records,
              "limitations": ["开发验收问题，未声明严格盲测或广泛泛化能力。",
                              "未训练模型；自动提供框架基础不等于模型权重已经内化框架。",
                              "协议通过不证明语义正确；语义需按回答摘要绑定后独立核对。",
                              "两个正式入口的原操作权限保留；本验收不运行Case或应用源码补丁。",
                              "每次传输使用现有Provider，验收器不自动重试。"]}
    if followup:
        report["limitations"].append("本轮为显式开发复测；原问题与回答已有诊断，不声明未见盲测。")
    for entry in entries:
        previous = {}
        for case in cases:
            active_case["id"] = entry + "." + case["id"]
            parent = None if case["history"] == "fresh" else previous.get(case["history"])
            history = _history(parent, 600 if entry == "assembly" else 2000)
            row = {"id": entry + "." + case["id"], "entry": entry,
                   "instruction": case["instruction"], "history_messages": len(history),
                   "continuation_of": None if parent is None else parent["id"],
                   "protocol": "failed", "semantic_review": "pending",
                   "review_points": list(case["review_points"]), "response_sha256": None}
            start_count = budget.used
            try:
                if case["history"] != "fresh" and (parent is None or parent["protocol"] != "passed"):
                    raise AssistantProviderError("acceptance_parent_delivery_unavailable")
                if entry == "assembly":
                    packet = build_assistant_packet(assembly_from_recipe("ga_vns"), instruction=case["instruction"],
                        guide_context={"history": history, "design_notes": CONFIRMED_DESIGN})
                    messages = assistant_messages(packet)
                    _record_input(row, packet)
                    budget.reserve()
                    request_records.append({"entry": entry, "request": budget.used,
                                            "messages_sha256": content_digest(messages)})
                    answer = generator.generate(packet)
                    validate_draft(answer, base_digest=packet["base_digest"], catalog=packet["assembly_catalog"],
                                   framework_context=packet["framework_context"])
                else:
                    packet = runtime.prepare({"project_id": project_id, "instruction": case["instruction"],
                                              "history": history})
                    _record_input(row, packet)
                    answer = runtime.generate(packet, generator)
                row.update(protocol="passed", answer=deepcopy(answer), response_sha256=content_digest(answer))
            except AssistantProviderError as exc:
                row["error"] = str(exc) if str(exc).startswith(("ai_", "acceptance_")) else "provider_or_protocol_failure"
            except Exception:
                row["error"] = "acceptance_preparation_or_validation_failed"
            row["http_requests"] = budget.used - start_count
            rows.append(row)
            previous[case["id"]] = row
            report["summary"] = _summary(rows, budget)
            if progress is not None:
                progress(deepcopy(report))
    return report


def attach_reviews(report, reviews, *, reviewer):
    """Bind source-and-answer review to actual response bytes; no keyword grade."""
    if report.get("schema") != SCHEMA or not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("invalid_acceptance_review")
    result = deepcopy(report)
    rows = {row["id"]: row for row in result["cases"]}
    if not isinstance(reviews, dict) or set(reviews).difference(rows):
        raise ValueError("unknown_acceptance_review")
    for identity, review in reviews.items():
        row = rows[identity]
        if (not isinstance(review, dict) or set(review) != {"response_sha256", "decision", "reason"}
                or row["response_sha256"] is None or review["response_sha256"] != row["response_sha256"]
                or review["decision"] not in {"pass", "fail", "needs_more_evidence"}
                or not isinstance(review["reason"], str) or not review["reason"].strip()):
            raise ValueError("acceptance_review_mismatch")
        row.update(semantic_review=review["decision"], reviewer=reviewer, review_reason=review["reason"])
    budget = RequestBudget(result["maximum_http_requests"], already_used=result.get("already_used_http_requests", 0))
    budget.used = result["summary"]["http_requests"]
    result["summary"] = _summary(result["cases"], budget)
    return result


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def main(argv=None):
    parser = argparse.ArgumentParser(description="用两个正式AI入口做有界新会话验收；语义单独审阅")
    parser.add_argument("--model-config", type=Path)
    parser.add_argument("--allow-paid", action="store_true")
    parser.add_argument("--maximum-requests", type=int, default=20)
    parser.add_argument("--already-used", type=int, default=0)
    parser.add_argument("--project-model-calls", type=int, default=4, choices=(1, 2, 3, 4))
    parser.add_argument("--entries", nargs="+", choices=("assembly", "project"), default=["assembly", "project"])
    parser.add_argument("--cases", nargs="+", choices=[case["id"] for case in CASES])
    parser.add_argument("--prior-report", type=Path, help="开发复测绑定原报告，并沿用其已消耗HTTP次数")
    parser.add_argument("--report", type=Path, help="只读取已有报告并附加审阅，不调用模型")
    parser.add_argument("--reviews", type=Path)
    parser.add_argument("--reviewer")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.report:
        if args.model_config or args.allow_paid or not args.reviews or not args.reviewer:
            parser.error("审阅模式只接受已有report、reviews和reviewer")
        report = attach_reviews(json.loads(args.report.read_text(encoding="utf-8")),
                                json.loads(args.reviews.read_text(encoding="utf-8")), reviewer=args.reviewer)
    else:
        if not args.model_config or not args.allow_paid or args.reviews or args.reviewer:
            parser.error("实际模型验收须显式提供 --model-config 与 --allow-paid")
        config = load_assistant_model_config(args.model_config)
        generator = create_assistant_generator(config)
        source_report = None
        if args.prior_report:
            raw = args.prior_report.read_bytes()
            prior = json.loads(raw)
            if prior.get("schema") != SCHEMA:
                parser.error("原报告不是会话验收记录")
            prior_used = prior["summary"]["http_requests"]
            if args.already_used not in (0, prior_used):
                parser.error("already-used与原报告不一致")
            args.already_used = prior_used
            source_report = hashlib.sha256(raw).hexdigest()
        with tempfile.TemporaryDirectory(prefix="framework-ai-session-") as directory:
            sources, project_id = create_teaching_project(Path(directory))
            report = run_acceptance(generator, sources=sources, project_id=project_id,
                maximum_requests=args.maximum_requests, already_used=args.already_used,
                entries=args.entries, case_ids=args.cases, source_report_sha256=source_report,
                project_model_calls=args.project_model_calls,
                progress=lambda value: _write(args.out, value))
    _write(args.out, report)
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0 if report["summary"]["protocol_passed"] == report["summary"]["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
