"""默认三个独立Case，另设partition分组；Project拥有唯一L0授权。"""
L0 = {
    "namespace": "pool_workflow_pilot",
    "offer": {"threads": 1, "gpus": 0, "backend": "local", "device_tokens": []},
    "policy": {"mode": "strict", "gpu_sharing": "exclusive", "cpu_oversubscribe": False},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto", "execution_backend": "local",
}
STAGES = [{"name": "search", "cases": ["vns_search", "moead_search", "ga_search"], "policy": "serial",
           "resource_requests": {name: {"threads": 1, "gpus": 0, "backend": "local"}
                                 for name in ("vns_search", "moead_search", "ga_search")}},
          {"name": "partition", "cases": ["ga_partition"], "policy": "serial",
           "resource_requests": {"ga_partition": {"threads": 1, "gpus": 0, "backend": "local"}}}]
GROUPS = {"default": {"stages": ["search"]}, "partition": {"stages": ["partition"]}}

STAGES.append({"name": "parallel_archive", "cases": ["ga_search"], "policy": "serial",
    "case_modes": {"ga_search": "build"},
    "resource_requests": {"ga_search": {"threads": 1, "gpus": 0, "backend": "local"}},
    "component_overrides": {"ga_search": {"config": {
        "parallel_archive": True, "archive_source": "members", "max_steps": 4}}}})
GROUPS["parallel_archive"] = {"stages": ["parallel_archive"]}
