"""Three independent semantic cases; Project L0 owns all resource grants."""

PROJECT_NAME = "algorithm_semantics"
CASES = ("synchronous_bo", "cmaes_distribution", "map_elites_archive")
REQUEST = {"threads": 1, "workers": 1, "gpus": 0, "backend": "local"}
L0 = {
    "namespace": PROJECT_NAME,
    "offer": {"threads": 3, "workers": 3, "gpus": 0,
              "backend": "local", "device_tokens": []},
    "policy": {"mode": "strict", "max_workers": 3, "max_threads": 3,
               "gpu_sharing": "exclusive", "cpu_oversubscribe": False},
    "default_request": REQUEST,
    "compute_backend": "auto", "execution_backend": "local",
    "lease_backend": "sqlite", "lease_path": ".blackbase/l0_leases.sqlite",
    "lease_ttl_seconds": 30, "lease_heartbeat_seconds": 10,
    "artifacts": {"path": ".blackbase/artifacts", "allow_unsafe_serializers": False},
    "budgets": {"evaluations": 256},
}

STAGES = [
    {"name": "semantics", "policy": "serial", "cases": list(CASES),
     "case_modes": {name: "build" for name in CASES},
     "resource_requests": {name: dict(REQUEST) for name in CASES}},
    {"name": "independent", "policy": "parallel", "max_workers": 3,
     "cases": list(CASES), "case_modes": {name: "build" for name in CASES},
     "resource_requests": {name: dict(REQUEST) for name in CASES}},
    *({"name": name, "policy": "serial", "cases": [name],
       "case_modes": {name: "build"}, "resource_requests": {name: dict(REQUEST)}}
      for name in CASES),
]
GROUPS = {
    "default": {"stages": ["semantics"]},
    "parallel": {"stages": ["independent"]},
    **{name: {"stages": [name]} for name in CASES},
}
