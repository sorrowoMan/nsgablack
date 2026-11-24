"""Project L0 owns the grant; algorithm phases belong to the Case Adapter."""
L0 = {
    "namespace": "assembled_pool_recovery",
    "offer": {"threads": 1, "gpus": 0, "backend": "local", "device_tokens": []},
    "policy": {"mode": "strict", "gpu_sharing": "exclusive", "cpu_oversubscribe": False},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto", "execution_backend": "local",
}
STAGES = [{"name": "recovery_demo", "cases": ["pool_recovery"], "policy": "serial",
           "resource_requests": {"pool_recovery": {"threads": 1, "gpus": 0, "backend": "local"}}}]
GROUPS = {"default": {"stages": ["recovery_demo"]}}
