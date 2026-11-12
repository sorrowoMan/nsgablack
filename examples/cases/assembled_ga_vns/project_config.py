"""Project 管跨 Case 执行及唯一 L0 授权；算法阶段位于 Case 的 Adapter。"""
L0 = {
    "namespace": "assembled_ga_vns",
    "offer": {"threads": 1, "gpus": 0, "backend": "local", "device_tokens": []},
    "policy": {"mode": "strict", "gpu_sharing": "exclusive", "cpu_oversubscribe": False},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto", "execution_backend": "local",
}
ELITE_DEMO_CONFIG = {"population_size": 24, "ga_steps": 2, "local_steps": 2,
                     "local_batch": 1, "refinement_source": "elite", "elite_count": 20,
                     "evaluation_budget": 128}
PLAN_DEMO_CONFIG = {"schedule": "plan", "rounds": 2,
                    "population_size": 6, "ga_steps": 2, "local_steps": 2,
                    "local_batch": 1, "refinement_source": "elite", "elite_count": 2}
STAGES = [{"name": "search", "cases": ["hybrid_search"], "policy": "serial",
           "resource_requests": {"hybrid_search": {"threads": 1, "gpus": 0, "backend": "local"}}},
          {"name": "elite_refinement", "cases": ["hybrid_search"], "policy": "serial",
           "component_overrides": {"hybrid_search": {"config": ELITE_DEMO_CONFIG}},
           "resource_requests": {"hybrid_search": {"threads": 1, "gpus": 0, "backend": "local"}}},
          {"name": "plan_refinement", "cases": ["hybrid_search"], "policy": "serial",
           "component_overrides": {"hybrid_search": {"config": PLAN_DEMO_CONFIG}},
           "resource_requests": {"hybrid_search": {"threads": 1, "gpus": 0, "backend": "local"}}}]
GROUPS = {"default": {"stages": ["search"]}, "elite": {"stages": ["elite_refinement"]},
          "plan": {"stages": ["plan_refinement"]}}
