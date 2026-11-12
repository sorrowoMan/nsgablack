"""先并行求解，再带权威 Artifact 进入真正的嵌套 Case；L0 只在 Project。"""
PROJECT_NAME = "assembly_workbench"

L0 = {
    "namespace": "assembly_workbench",
    "offer": {"threads": 4, "workers": 4, "gpus": 0, "backend": "local", "device_tokens": []},
    "policy": {"mode": "strict", "max_workers": 4, "max_threads": 4,
               "gpu_sharing": "exclusive", "cpu_oversubscribe": False},
    "default_request": {"threads": 1, "workers": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto", "execution_backend": "local",
    "lease_backend": "sqlite", "lease_path": ".blackbase/l0_leases.sqlite",
    "lease_ttl_seconds": 30, "lease_heartbeat_seconds": 10,
    "artifacts": {"path": ".blackbase/artifacts", "allow_unsafe_serializers": False},
    "budgets": {"evaluations": 256},
}

SEARCH_REQUEST = {"threads": 1, "workers": 1, "gpus": 0, "backend": "local"}
NESTED_REQUEST = {"threads": 2, "workers": 2, "gpus": 0, "backend": "local"}
BASELINE_INPUTS = {"hybrid_summary": "hybrid_search.summary", "directions_summary": "directions.summary"}

STAGES = [
    {"name": "searches", "policy": "parallel", "max_workers": 2,
     "cases": ["hybrid_search", "directions"],
     "case_modes": {"hybrid_search": "build", "directions": "build"},
     "resource_requests": {"hybrid_search": SEARCH_REQUEST, "directions": SEARCH_REQUEST}},
    {"name": "nested", "policy": "serial", "cases": ["outer_nested"],
     "case_modes": {"outer_nested": "build"},
     "input_artifacts": {"outer_nested": BASELINE_INPUTS},
     "resource_requests": {"outer_nested": NESTED_REQUEST}},
    {"name": "hybrid_only", "policy": "serial", "cases": ["hybrid_search"]},
    {"name": "provider_path", "policy": "serial", "cases": ["hybrid_search"],
     "component_overrides": {"hybrid_search": {"config": {"evaluation_mode": "provider"}}}},
    {"name": "directions_only", "policy": "serial", "cases": ["directions"]},
    {"name": "directions_random", "policy": "serial", "cases": ["directions"],
     "component_overrides": {"directions": {"config": {"direction_sample": 2}}}},
    {"name": "parallel_refinement", "policy": "serial", "cases": ["directions"],
     "component_overrides": {"directions": {"config": {"refinement_layout": "parallel"}}}},
    {"name": "inner_only", "policy": "serial", "cases": ["inner_response"]},
    {"name": "nested_only", "policy": "serial", "cases": ["outer_nested"],
     "resource_requests": {"outer_nested": NESTED_REQUEST}},
    {"name": "workflow", "policy": "dag", "max_workers": 2,
     "cases": ["hybrid_search", "directions", "outer_nested"],
     "case_modes": {name: "build" for name in ("hybrid_search", "directions", "outer_nested")},
     "input_artifacts": {"outer_nested": BASELINE_INPUTS},
     "resource_requests": {"hybrid_search": SEARCH_REQUEST,
                           "directions": SEARCH_REQUEST, "outer_nested": NESTED_REQUEST}},
]

GROUPS = {
    "default": {"stages": ["searches", "nested"]},
    "dag": {"stages": ["workflow"]},
    "hybrid": {"stages": ["hybrid_only"]},
    "provider": {"stages": ["provider_path"]},
    "directions": {"stages": ["directions_only"]},
    "random_directions": {"stages": ["directions_random"]},
    "parallel_refiners": {"stages": ["parallel_refinement"]},
    "inner": {"stages": ["inner_only"]},
    "nested": {"stages": ["nested_only"]},
}
