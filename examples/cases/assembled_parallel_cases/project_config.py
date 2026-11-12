"""两个独立 Case 的并发属于 Project，唯一 L0 在此授权。"""
L0 = {
    "namespace": "assembled_parallel_cases",
    "offer": {"threads": 2, "gpus": 0, "backend": "local", "device_tokens": []},
    "policy": {"mode": "strict", "max_workers": 2, "gpu_sharing": "exclusive", "cpu_oversubscribe": False},
    "default_request": {"threads": 1, "workers": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto", "execution_backend": "local",
}
STAGES = [{
    "name": "independent_searches", "cases": ["de_bowl", "sa_valley"],
    "policy": "parallel", "max_workers": 2,
    "case_modes": {"de_bowl": "build", "sa_valley": "build"},
    "resource_requests": {
        "de_bowl": {"threads": 1, "workers": 1, "gpus": 0, "backend": "local"},
        "sa_valley": {"threads": 1, "workers": 1, "gpus": 0, "backend": "local"},
    },
}]
GROUPS = {"default": {"stages": ["independent_searches"]}}
