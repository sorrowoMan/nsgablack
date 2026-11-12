"""Verify guided Problem creation and result interpretation with two real calls.

The paid probe is separate from ordinary Catalog/worker readiness. It applies
the returned draft explicitly, then submits a separate formal Project trial.
No credential, prompt, raw provider reply or grant is printed.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
import io
import hashlib
import json
import os
import time


def _wait(job, poll, seconds=80):
    deadline = time.monotonic() + seconds
    while job["status"] in {"queued", "running"} and time.monotonic() < deadline:
        time.sleep(.3)
        job = poll(job["job_id"])
    assert job["status"] == "succeeded", "editor_or_trial_failed:" + str(job.get("error", {}).get("code", "timeout"))
    return job


def verify(*, live=False, request_id=None):
    from runtime import configure_reader
    from nsgablack.catalog import lab_client
    from nsgablack.catalog.lab_assembly import assembly_from_recipe, normalize_assembly
    from nsgablack.catalog.lab_assistant import apply_draft
    from nsgablack.catalog.lab_jobs import spec_digest
    from nsgablack.catalog.lab_guide import build_guide_context, read_guide
    from nsgablack.catalog.lab_problem import evaluate_problem
    assert configure_reader(os.environ) == "only"
    caps = lab_client.assistant_capabilities()
    assert caps["enabled"] and caps["mode"] == "remote" and caps["drafts_only"]
    assert caps["limits"]["requests_per_utc_day"] is None and caps["limits"]["parallel"] == 1
    assert caps["quota"]["remaining"] is None and caps["quota"]["resets_at"] is None
    assert caps["guide"] == read_guide()["metadata"]
    assert lab_client.get_capabilities()["enabled"]
    value = {"ok": True, "model_calls": 0, "drafts_only": True, "quota": caps["quota"]}
    if not live:
        return value
    spec = assembly_from_recipe("ga")
    spec["initial_count"], spec["max_steps"] = 8, 3
    spec["nodes"][0]["parameters"].update(population_size=4, offspring_size=4)
    spec["nodes"][0]["input"]["count"] = 4
    spec["plan"]["steps"] = 3
    spec = normalize_assembly(spec)
    instruction = ("请根据以下描述生成可编辑的问题定义，保留已有算法和运行计划。"
        "只有一个连续变量amount，范围0到10；最大化利润8*amount-amount**2；"
        "硬约束amount<=6，绝对容差0。请使用problem.expression，同步dimension=1，"
        "初始化按变量边界。其它所有装配和预算保持不变，输出完整草案。")
    assert request_id and len(request_id) == 32, "live_probe_requires_persisted_request_identity"
    context = build_guide_context(spec, stage="problem")
    job = lab_client.assistant_submit(spec, instruction, request_id=request_id, guide_context=context)
    duplicate = lab_client.assistant_submit(spec, instruction, request_id=request_id, guide_context=context)
    assert duplicate["job_id"] == job["job_id"]
    job = _wait(job, lab_client.assistant_poll)
    result = job["result"]
    assert result["base_digest"] == spec_digest(spec) and result["verification_status"] == "not_run"
    draft = apply_draft(spec, result)  # explicit gate, never implicit in poll/submit
    assert draft["problem"]["component"] == "problem.expression" and draft["dimension"] == 1
    assert draft["nodes"] == spec["nodes"] and draft["plan"] == spec["plan"]
    assert draft["max_steps"] == 3 and draft["initial_count"] == 8
    params = draft["problem"]["parameters"]
    assert len(params["variables"]) == len(params["objectives"]) == len(params["constraints"]) == 1
    assert params["variables"][0] == {"name":"amount","low":0.,"high":10.,"type":"continuous"}
    assert params["objectives"][0]["direction"] == "max"
    for amount in (0., 3., 6., 7., 10.):
        objectives, violation = evaluate_problem(draft["problem"], [amount])
        assert abs(objectives[0] + (8 * amount - amount ** 2)) < 1e-10
        assert abs(violation - max(amount - 6, 0)) < 1e-10
    trial = _wait(lab_client.submit(draft), lab_client.poll)
    report = trial["result"]
    assert report["status"] == "succeeded" and report["plan_completed"]
    assert report["resource_binding"]["current"] and report["steps"] > 0
    after = lab_client.assistant_capabilities()["quota"]
    assert after["reserved_today"] == caps["quota"]["reserved_today"] + 1
    results_context = build_guide_context(draft, stage="results", history=[
        {"role":"user","content":"我希望最大化利润，并且amount不得超过6。"},
        {"role":"assistant","content":"已交付问题草案，用户显式应用后独立试跑。"}], job=trial)
    interpretation_id = hashlib.sha256((request_id + ':results').encode()).hexdigest()[:32]
    diagnosis = _wait(lab_client.assistant_submit(draft,
        "根据页面提供的试跑摘要，用中文简短解释当前结果和一项下一步建议。只读解释，不修改问题或算法，draft必须为null且changes为空。不要声称全局最优或数学正确。",
        request_id=interpretation_id, guide_context=results_context), lab_client.assistant_poll)
    advice = diagnosis["result"]
    assert advice["draft"] is None and advice["changes"] == [] and advice["explanation"]
    assert advice["verification_status"] == "not_run"
    after = lab_client.assistant_capabilities()["quota"]
    assert after["reserved_today"] == caps["quota"]["reserved_today"] + 2
    value.update(model_calls=2, quota=after, request_id=request_id,
                 request_digest=spec_digest(spec), draft_digest=spec_digest(draft),
                 editor_job_id=job["job_id"], trial_job_id=trial["job_id"],
                 component="problem.expression", max_direction=True, hard_constraint=True,
                 read_only_results_advice=True, guide=caps["guide"], stale_apply_rejected=False,
                 steps=report["steps"], evaluations=report["evaluations"],
                 plan_completed=True, resource_current=True)
    changed = json.loads(json.dumps(spec))
    changed["seed"] += 1
    try:
        apply_draft(changed, result)
    except Exception as exc:
        assert getattr(exc, "code", "") == "stale_draft"
        value["stale_apply_rejected"] = True
    assert value["stale_apply_rejected"]
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--request-id")
    args = parser.parse_args()
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        result = verify(live=args.live, request_id=args.request_id)
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
