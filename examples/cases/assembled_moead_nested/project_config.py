"""Project 只负责 Case 编排和唯一 L0 授权；算法阶段由 Case 内 Router 管理。"""
L0 = {
    "namespace": "assembled_moead_nested",
    "offer": {"threads": 1, "gpus": 0, "backend": "local", "device_tokens": []},
    "policy": {"mode": "strict", "gpu_sharing": "exclusive", "cpu_oversubscribe": False},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto", "execution_backend": "local",
}
STAGES = [{"name": "search", "cases": ["direction_refinement"], "policy": "serial",
           "resource_requests": {"direction_refinement": {"threads": 1, "gpus": 0, "backend": "local"}}}]
GROUPS = {"default": {"stages": ["search"]}}
