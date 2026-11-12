"""正式供排联合求解；外层供应提案逐个调用隔离生产 Case。"""
from __future__ import annotations

import os
import re
import json
from pathlib import Path

PROJECT_NAME = "supply_adjustment_nested"
NAMESPACE = os.environ.get("BLACKBASE_JOINT_NAMESPACE", "examples.supply_joint").strip()
if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9:_.-]{0,119}", NAMESPACE):
    raise ValueError("invalid joint namespace")
REDIS_URL = os.environ.get("BLACKBASE_JOINT_REDIS_URL", "").strip()
CLOUD = bool(REDIS_URL)
CAPABILITIES = ["production_inner", "nested_eval"] + (["supplyjoint:data", "supplyjoint:full"] if CLOUD else [])
L0 = {
    "namespace": NAMESPACE,
    "offer": {"threads": 1, "workers": 1, "gpus": 0, "backend": "local", "metadata": {"memory_mb": 3072}},
    "policy": {"mode": "strict", "max_workers": 1, "max_threads": 1,
               "max_gpus": 0, "max_memory_mb": 3072, "cpu_oversubscribe": False},
    "default_request": {"workers": 1, "threads": 1, "gpus": 0, "memory_mb": 3072, "capabilities": CAPABILITIES},
    "lease_backend": "redis" if CLOUD else "sqlite", "lease_redis_url_env": "BLACKBASE_JOINT_REDIS_URL",
    "lease_path": ".blackbase/leases.sqlite", "lease_ttl_seconds": 30, "lease_heartbeat_seconds": 10,
    "control_active_ttl_seconds": 90, "control_heartbeat_seconds": 10,
    "budgets": {"evaluations": 20000, "audit_evaluations": 100},
    "artifacts": {"path": ".blackbase/artifacts", "allow_unsafe_serializers": False},
    "termination": {"mode": "cooperative_then_terminate", "grace_seconds": 3,
                    "kill_grace_seconds": 1, "poll_interval_seconds": .1},
}


def stage(name, *, evaluation_only=False, seed=42, validation=False, from_search=False):
    argv = ["--machines", "22", "--materials", "157", "--days", "31", "--seed", "42",
            "--inner-seed", str(seed), "--pop-size", "4", "--generations", "1", "--max-evaluations", "8",
            "--inner-pop-size", "16" if validation else "8",
            "--inner-generations", "24" if validation else "7",
            "--inner-max-evaluations", "512" if validation else "192",
            "--inner-memory-mb", "2048", "--nested-task-timeout-seconds", "900",
            "--no-decision-trace", "--no-profiler"]
    if evaluation_only:
        argv.append("--evaluation-only")
    result = {"name": name, "cases": ["supply_adjustment_nested"], "mode": "build",
              "policy": "external" if CLOUD else "serial", "timeout_seconds": 1800,
              "component_overrides": {"supply_adjustment_nested": {"argv": argv}}}
    if from_search:
        result["input_artifacts"] = {"supply_adjustment_nested": {
            "candidate_plan": "search.supply_adjustment_nested.joint_summary"}}
    if CLOUD:
        result["external"] = {"backend": "redis", "redis_url": REDIS_URL,
            "namespace": NAMESPACE + ":tasks", "queue_timeout_seconds": 120,
            "poll_interval_seconds": .5, "max_retries": 0}
    return result


STAGES = [stage("baseline", evaluation_only=True), stage("search")]
for seed in (42, 43, 44):
    STAGES += [stage(f"zero_s{seed}", evaluation_only=True, seed=seed, validation=True),
               stage(f"selected_s{seed}", evaluation_only=True, seed=seed, validation=True, from_search=True)]
GROUPS = {"default": {"stages": ["baseline"]},
          "pilot": {"stages": ["baseline", "search"]},
          "joint_acceptance": {"stages": [item["name"] for item in STAGES]},
          **{item["name"]: {"stages": [item["name"]]} for item in STAGES if not item["name"].startswith("selected_")}}

# Case-local CLI delegates execution to this same Project/L0 path.
_direct_argv = json.loads(os.environ.get("NSGABLACK_SUPPLY_CASE_ARGV", "[]"))
if not isinstance(_direct_argv, list) or any(not isinstance(arg, str) for arg in _direct_argv):
    raise ValueError("NSGABLACK_SUPPLY_CASE_ARGV must be a JSON list of CLI arguments")
_direct = stage("direct")
_direct["component_overrides"]["supply_adjustment_nested"]["argv"] += _direct_argv
STAGES.append(_direct)
GROUPS["direct"] = {"stages": ["direct"]}


def delivery_stage(node):
    case = "artifact_delivery_check"
    result = {"name": "delivery_" + node, "cases": [case], "mode": "build",
              "policy": "external" if CLOUD else "serial", "timeout_seconds": 60,
              "termination": {"mode": "cooperative"},
              "resource_requests": {case: {"workers": 1, "threads": 1, "memory_mb": 128,
                  "capabilities": ["supplyjoint:" + node, "supplyjoint:micro"] if CLOUD else []}},
              "component_overrides": {case: {"expected_node": node if CLOUD else None}},
              "input_artifacts": {case: {"joint_plan": "baseline.supply_adjustment_nested.joint_summary"}}}
    if CLOUD:
        result["external"] = {"backend": "redis", "redis_url": REDIS_URL,
            "namespace": NAMESPACE + ":tasks", "queue_timeout_seconds": 120,
            "poll_interval_seconds": .5, "max_retries": 0}
    return result


STAGES += [delivery_stage(node) for node in ("risk", "local")]
GROUPS["delivery"] = {"stages": ["baseline", "delivery_risk", "delivery_local"]}
GROUPS["joint_acceptance"]["stages"][1:1] = ["delivery_risk", "delivery_local"]


# Expanded independent-event comparison: import only the prior decision vector,
# then recompute all outputs under this run's production configuration.
_prior_path = Path(__file__).resolve().parent / "prior_plan_binding.json"
_PRIOR = json.loads(_prior_path.read_text(encoding="utf-8")) if _prior_path.is_file() else None
_import = stage("import_prior")
_import["cases"] = ["supply_plan_import"]
_import["termination"] = {"mode": "cooperative"}
_import["timeout_seconds"] = 120
_import["component_overrides"] = {"supply_plan_import": ({
    "old_authority": _PRIOR["authority"], "old_binding": _PRIOR["binding"]} if _PRIOR else {})}
_extended = stage("search_events")
_extended["timeout_seconds"] = 3600
_extended["component_overrides"]["supply_adjustment_nested"]["argv"] += [
    "--pop-size", "12", "--generations", "5", "--max-evaluations", "72"]
STAGES += [_import, _extended]
_event_stages = ["import_prior", "search_events"]
for _seed in (42, 43, 44):
    for _which in ("zero", "prior", "selected"):
        _name = f"event_{_which}_s{_seed}"
        _item = stage(_name, evaluation_only=True, seed=_seed, validation=True)
        if _which != "zero":
            _key = ("import_prior.supply_plan_import.candidate_plan" if _which == "prior"
                    else "search_events.supply_adjustment_nested.joint_summary")
            _item["input_artifacts"] = {"supply_adjustment_nested": {"candidate_plan": _key}}
        STAGES.append(_item)
        _event_stages.append(_name)
GROUPS["event_comparison"] = {"stages": _event_stages}
GROUPS["event_search"] = {"stages": ["search_events"]}
for _event_stage in STAGES:
    if _event_stage["name"] in _event_stages:
        _event_case = _event_stage["cases"][0]
        _event_stage["resource_requests"] = {_event_case: {
            **L0["default_request"],
            "capabilities": ["production_inner", "nested_eval"] + (
                ["supplyevent:data", "supplyevent:full"] if CLOUD else [])}}


# Continue from a completed, sealed search whose large transport reply failed.
# This creates a new Project run; the original failure is never rewritten.
_recovered_path = Path(__file__).resolve().parent / "recovered_plan_binding.json"
_RECOVERED = json.loads(_recovered_path.read_text(encoding="utf-8")) if _recovered_path.is_file() else None
_import_selected = stage("import_selected")
_import_selected.update(cases=["supply_plan_import"], timeout_seconds=120,
                        termination={"mode": "cooperative"})
_import_selected["component_overrides"] = {"supply_plan_import": ({
    "old_authority": _RECOVERED["authority"], "old_binding": _RECOVERED["binding"]} if _RECOVERED else {})}
_import_selected["resource_requests"] = _import["resource_requests"]
STAGES.append(_import_selected)
_recovery_stages = ["import_prior", "import_selected"]
for _seed in (42, 43, 44):
    for _which in ("zero", "prior", "selected"):
        _name = f"review_{_which}_s{_seed}"
        _item = stage(_name, evaluation_only=True, seed=_seed, validation=True)
        _item["resource_requests"] = {"supply_adjustment_nested": {
            **L0["default_request"],
            "capabilities": ["production_inner", "nested_eval"] + (
                ["supplyevent:data", "supplyevent:full"] if CLOUD else [])}}
        if _which != "zero":
            _producer = "import_prior" if _which == "prior" else "import_selected"
            _item["input_artifacts"] = {"supply_adjustment_nested": {
                "candidate_plan": f"{_producer}.supply_plan_import.candidate_plan"}}
        STAGES.append(_item)
        _recovery_stages.append(_name)
GROUPS["event_recovery_comparison"] = {"stages": _recovery_stages}


# Opt-in portable inputs: publish exact source bytes before the search Case.
# Worker placement stays in Project L0.nested_execution; this group does not
# create a private runner or infer remote services from local filenames.
_sources_stage = stage("publish_sources", evaluation_only=True)
_sources_stage["cases"] = ["production_sources"]
_sources_stage["component_overrides"] = {"production_sources": {}}
_sources_stage["timeout_seconds"] = 120
_portable_stage = stage("portable", evaluation_only=True)
_portable_stage["component_overrides"]["supply_adjustment_nested"]["argv"] += ["--portable-inputs"]
_portable_stage["input_artifacts"] = {"supply_adjustment_nested": {
    "bom": "publish_sources.production_sources.bom", "supply": "publish_sources.production_sources.supply"}}
STAGES += [_sources_stage, _portable_stage]
GROUPS["portable"] = {"stages": ["publish_sources", "portable"]}


# Explicit deployment input enables a bounded capacity probe. The old groups
# keep their configuration when this profile is absent. All probe controllers
# must use the SAME aggregate offer and namespace; node placement is enforced
# by the stage request and the physical external WorkerDescriptor.
_CAPACITY_NODE_LIMITS = {
    "local": {"threads": 8, "parent_memory_mb": 1536, "inner_memory_mb": 1024},
    "risk": {"threads": 2, "parent_memory_mb": 2048},
    "data": {"threads": 1, "parent_memory_mb": 3072},
}
_CAPACITY_SCHEMA = "supply_adjustment_nested.capacity_profile/v1"


def _load_capacity_profile():
    inline = os.environ.get("NSGABLACK_SUPPLY_CAPACITY_PROFILE_JSON", "").strip()
    filename = os.environ.get("NSGABLACK_SUPPLY_CAPACITY_PROFILE", "").strip()
    if inline and filename:
        raise ValueError("choose capacity profile JSON or profile file, not both")
    if not inline and not filename:
        return None
    if filename:
        profile_path = Path(filename).expanduser()
        if not profile_path.is_absolute():
            profile_path = Path(__file__).resolve().parent / profile_path
        inline = profile_path.read_text(encoding="utf-8-sig")
    profile = json.loads(inline)
    required = {"schema", "node", "inner_threads", "parent_memory_mb", "inner_memory_mb"}
    if (not isinstance(profile, dict) or not required.issubset(profile)
            or set(profile).difference(required | {"capabilities"})):
        raise ValueError("capacity profile requires schema/node/inner_threads/parent_memory_mb/inner_memory_mb")
    if (profile["schema"] != _CAPACITY_SCHEMA or not isinstance(profile["node"], str)
            or profile["node"] not in _CAPACITY_NODE_LIMITS):
        raise ValueError("invalid capacity profile schema or node")
    limits = _CAPACITY_NODE_LIMITS[profile["node"]]
    for field in ("inner_threads", "parent_memory_mb", "inner_memory_mb"):
        if type(profile[field]) is not int or profile[field] <= 0:
            raise ValueError(f"capacity profile {field} must be a positive integer")
    if profile["inner_threads"] > limits["threads"]:
        raise ValueError("capacity profile exceeds the physical node thread limit")
    if (profile["parent_memory_mb"] > limits["parent_memory_mb"]
            or profile["inner_memory_mb"] > limits.get("inner_memory_mb", limits["parent_memory_mb"])
            or profile["parent_memory_mb"] < profile["inner_memory_mb"] + 256):
        raise ValueError("capacity profile exceeds node memory or lacks 256 MiB coordinator headroom")
    caps = profile.get("capabilities", ["production_inner", "nested_eval",
        "supplycapacity:" + profile["node"], "supplycapacity:probe"])
    needed_caps = {"production_inner", "nested_eval", "supplycapacity:" + profile["node"], "supplycapacity:probe"}
    if (not isinstance(caps, list) or any(not isinstance(cap, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9:_.-]{0,119}", cap) for cap in caps)
            or len(caps) != len(set(caps)) or not needed_caps.issubset(caps)):
        raise ValueError("capacity profile capabilities must include the declared node and formal production roles")
    if not os.environ.get("BLACKBASE_JOINT_NAMESPACE", "").strip():
        raise ValueError("capacity probes require an explicit shared BLACKBASE_JOINT_NAMESPACE")
    return {**profile, "capabilities": list(caps)}


CAPACITY_PROBE_PROFILE = _load_capacity_profile()
if CAPACITY_PROBE_PROFILE is not None:
    _probe = CAPACITY_PROBE_PROFILE
    _probe_request = {"workers": 1, "threads": _probe["inner_threads"], "gpus": 0,
        "memory_mb": _probe["parent_memory_mb"], "capabilities": _probe["capabilities"],
        "metadata": {"capacity_profile": _probe, "capacity_boundary": "independent_project_per_node"}}
    L0["offer"] = {"threads": 11, "workers": 3, "gpus": 0, "backend": "local",
        "metadata": {"memory_mb": 6656, "scope": "cluster_aggregate",
            "node_limits": _CAPACITY_NODE_LIMITS}}
    L0["policy"] = {"mode": "strict", "max_workers": 3, "max_threads": 11, "max_gpus": 0,
        "max_memory_mb": 6656, "cpu_oversubscribe": False}
    L0["default_request"] = _probe_request
    L0["budgets"] = {"evaluations": 1026, "audit_evaluations": 2}
    _capacity_stage = stage("capacity_probe")
    _capacity_stage["timeout_seconds"] = 1500
    _capacity_stage["resource_requests"] = {"supply_adjustment_nested": _probe_request}
    _capacity_stage["component_overrides"] = {"supply_adjustment_nested": {"argv": [
        "--machines", "22", "--materials", "157", "--days", "31",
        "--seed", "42", "--inner-seed", "42",
        "--pop-size", "200", "--generations", "100", "--max-evaluations", "2",
        "--inner-pop-size", "200", "--inner-generations", "100", "--inner-max-evaluations", "512",
        "--parallel", "--outer-parallel-workers", "1", "--inner-parallel-workers", str(_probe["inner_threads"]),
        "--inner-memory-mb", str(_probe["inner_memory_mb"]), "--nested-task-timeout-seconds", "600",
        "--no-decision-trace", "--no-profiler"]}}
    STAGES.append(_capacity_stage)
    GROUPS["capacity_probe"] = {"stages": ["capacity_probe"]}
