"""A generated tutorial cannot publish after a negative source review."""
from copy import deepcopy
import json
import io
import pytest
from nsgablack.catalog.curate import curate_packets
from nsgablack.catalog.curation import prepare_packet, CurationValidationError
from nsgablack.catalog.registry import CatalogEntry
from nsgablack.catalog.tutorial_review import REVIEW_VERSION, SYSTEM_PROMPT, validate_review
from nsgablack.catalog.curation_provider import DeepSeekGenerator, DeepSeekConfig


def verdict(decision="publish"):
    return {"decision":decision,"checks":["入口实际调用该工厂。","候选由原消费者处理。","变体明确输出的来源。"],
            "issues":[] if decision=="publish" else [{"location":"baseline", "problem":"没有实际挂载入口。",
             "required_change":"接入规范build_solver。", "evidence_ids":["e1"]}], "evidence_ids":["e1"]}


@pytest.mark.parametrize("change", ["unknown_evidence", "publish_with_issues", "empty_checks", "revise_without_issue", "extra_field"])
def test_review_cannot_approve_without_consistent_findings_and_sources(change):
    value=verdict()
    if change=="unknown_evidence":value["evidence_ids"]=["invented"]
    elif change=="publish_with_issues":value["issues"]=verdict("revise")["issues"]
    elif change=="empty_checks":value["checks"]=[]
    elif change=="revise_without_issue":value["decision"]="revise"
    else:value["can_execute"]=True
    with pytest.raises(CurationValidationError):validate_review(value,evidence_ids={"e1"})


def test_provider_review_uses_independent_direct_request_without_executing_code():
    calls=[]
    class Opener:
        def open(self,request,*,timeout):
            body=json.loads(request.data);calls.append(body)
            assert body["thinking"]=={"type":"disabled"}
            assert "reasoning_effort" not in body
            assert body["messages"][0]["content"] != "generated tutorial"
            assert body["messages"][0]["content"] == SYSTEM_PROMPT
            assert "同版、来源绑定的人工完整用法指南与正式Case都是有效证据" in SYSTEM_PROMPT
            assert "不要求展开整个框架对象图" in SYSTEM_PROMPT
            assert "新变体的关键API" in SYSTEM_PROMPT and "源码冲突、编造接口" in SYSTEM_PROMPT
            assert "未执行只限制" in SYSTEM_PROMPT
            return io.BytesIO(json.dumps({"choices":[{"finish_reason":"stop","message":{"content":json.dumps(verdict())}}]}).encode())
    result=DeepSeekGenerator(DeepSeekConfig("fixture-key"),opener=Opener(),allow_paid_requests=True).review(
        {"evidence":[{"id":"e1","text":"The trusted factory source."}]},
        {"tutorial":{"code":"raise RuntimeError('never execute')"}})
    assert result["note"]["decision"]=="publish" and len(calls)==1


def test_review_v5_versions_bounded_source_judgment_without_weakening_publication_findings():
    assert REVIEW_VERSION == "catalog-tutorial-source-review-zh-v5"
    assert "Adapter局部score或objective_aggregation不是Solver incumbent scalarizer" in SYSTEM_PROMPT
    assert "教程必须给出该值或分组" in SYSTEM_PROMPT
    assert "scope结束后不得再读members.refs" in SYSTEM_PROMPT
    assert validate_review(verdict(), evidence_ids={"e1"})["version"] == REVIEW_VERSION
    rejected = verdict("insufficient_evidence")
    assert validate_review(rejected, evidence_ids={"e1"})["decision"] == "insufficient_evidence"
    rejected["decision"] = "publish"
    with pytest.raises(CurationValidationError, match="contradicts"):
        validate_review(rejected, evidence_ids={"e1"})


@pytest.mark.parametrize("repair", [False, True])
def test_publisher_only_writes_after_independent_review_and_counts_calls(tmp_path,repair):
    (tmp_path/"component.py").write_text("class Example:\n    def act(self):\n        return 1\n")
    entry=CatalogEntry(key="tool.example",title="Example",kind="tool",import_path="sample.component:Example")
    packet=prepare_packet(entry,[entry],{"sample":tmp_path})
    source_id=packet["evidence"][0]["id"]
    class Store:
        records=[]
        def get(self,*args,**kwargs):return None
        def put(self,record):self.records.append(record);return record
    class Generator:
        requires_source_review=True
        calls=0
        reviews=0
        def generate(self,request):
            self.calls+=1
            if self.calls==2:assert request["editor_feedback"]["source_review"]["decision"]=="revise"
            note={"summary":"演示组件。","inputs_outputs":"调用act返回数值。","use_when":[],"assembly_steps":[],
                  "pitfalls":[],"related_keys":[],"missing_information":[],"evidence_ids":[source_id]}
            return {"note":note,"usage":{"total_tokens":10}}
        def review(self,source,note):
            self.reviews+=1
            value=verdict("publish" if repair and self.reviews==2 else "revise")
            value["evidence_ids"]=[source_id]
            for issue in value["issues"]:issue["evidence_ids"]=[source_id]
            return {"note":value,"usage":{"total_tokens":20}}
    store,generator=Store(),Generator()
    result=curate_packets({entry.key:packet},store,generator,model="fixture")
    assert generator.calls==2 and generator.reviews==2
    assert bool(store.records)==repair and result["ok"]==repair
    if repair:
        assert store.records[0]["note"]["tutorial_review"]["decision"]=="publish"
        assert store.records[0]["usage"]["total_tokens"]==60
    else:
        assert result["results"][0]["source_review"]["issues"]
