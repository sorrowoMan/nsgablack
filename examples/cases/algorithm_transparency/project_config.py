"""透明性 Project：L0 授权、真实双 Case 并行、正式跨 Case 调用。"""
PROJECT_NAME = "algorithm_transparency"
L0 = {
    "namespace": "algorithm_transparency",
    "offer": {"threads": 2, "workers": 2, "gpus": 0, "backend": "local", "device_tokens": []},
    "policy": {"mode": "strict", "max_workers": 2, "max_threads": 2,
               "cpu_oversubscribe": False, "gpu_sharing": "exclusive"},
    "default_request": {"threads": 1, "workers": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto", "execution_backend": "local", "lease_backend": "sqlite",
    "lease_path": ".blackbase/l0_leases.sqlite", "lease_ttl_seconds": 60,
    "lease_heartbeat_seconds": 10, "artifacts": {"path": ".blackbase/artifacts"},
}
STAGES = [
    {"name": "matrix", "cases": ["matrix"], "policy": "serial", "case_modes": {"matrix": "build"}},
    {"name": "full_matrix", "cases": ["matrix"], "policy": "serial", "case_modes": {"matrix": "build"},
     "component_overrides": {"matrix": {"config": {"names": "all", "seeds": [11, 29]}}}},
    {"name": "population_quality", "cases": ["matrix"], "policy": "serial", "case_modes": {"matrix": "build"},
     "component_overrides": {"matrix": {"config": {
         "names": ["nsga2_zdt1", "nsga3_zdt1", "nsga3_dtlz2", "spea2_zdt1", "moead_zdt1", "de_zdt1"],
         "population_size": 30, "steps": 25, "seeds": [11, 29, 47], "recovery": False}}}},
    {"name": "parallel", "cases": ["parallel_a", "parallel_b"], "policy": "parallel", "max_workers": 2,
     "case_modes": {"parallel_a": "build", "parallel_b": "build"}},
    {"name": "nested", "cases": ["bare_inner", "nested_outer"], "policy": "serial",
     "case_modes": {"bare_inner": "build", "nested_outer": "build"}},
]
GROUPS = {
    "default": {"stages": ["matrix", "parallel", "nested"]},
    "matrix": {"stages": ["matrix"]}, "full": {"stages": ["full_matrix"]},
    "quality": {"stages": ["population_quality"]},
    "parallel": {"stages": ["parallel"]}, "nested": {"stages": ["nested"]},
}

STAGES.append({"name": "cost_ladder", "cases": ["matrix"], "policy": "serial",
    "case_modes": {"matrix": "build"}, "component_overrides": {"matrix": {"config": {
        "mode": "costs", "population_size": 8, "steps": 8, "seeds": [11, 29],
        "cpu_ms": [0, 1, 10, 50], "wait_ms": [10], "production": True}}}})
GROUPS["costs"] = {"stages": ["cost_ladder"]}
STAGES.append({"name":"modification_tasks","cases":["matrix"],"policy":"serial",
    "case_modes":{"matrix":"build"},"component_overrides":{"matrix":{"config":{"mode":"modification_tasks"}}}})
GROUPS["modifications"]={"stages":["modification_tasks"]}
STAGES.append({"name":"independent_algorithms","cases":["matrix"],"policy":"serial",
    "case_modes":{"matrix":"build"},"component_overrides":{"matrix":{"config":{
        "mode":"classical_quality","population_size":20,"steps":20,"seeds":[11,29]}}}})
GROUPS["classical"]={"stages":["independent_algorithms"]}

# Self-contained quality / fusion / single-objective benchmark suites (no pymoo),
# exposed through the same standard Project/Case scaffold. Config mirrors the
# CLI defaults in `python -m benchmarks.<suite>`.
STAGES.append({"name":"quality_benchmark","cases":["matrix"],"policy":"serial",
    "case_modes":{"matrix":"build"},"component_overrides":{"matrix":{"config":{
        "mode":"quality","problems":["zdt1","dtlz2_3"],
        "algorithms":["nsga2","nsga3","spea2","moead"],
        "seeds":[11,29],"population_size":40,"steps":40,"nsga3_divisions":4}}}})
GROUPS["quality"]={"stages":["quality_benchmark"]}

STAGES.append({"name":"fusion_benchmark","cases":["matrix"],"policy":"serial",
    "case_modes":{"matrix":"build"},"component_overrides":{"matrix":{"config":{
        "mode":"fusion","pairs":[["nsga2","moead"],["nsga2","spea2"]],
        "problems":["zdt1","dtlz2_3"],"seeds":[11,29],
        "population_size":40,"total_steps":40}}}})
GROUPS["fusion"]={"stages":["fusion_benchmark"]}

STAGES.append({"name":"single_objective_benchmark","cases":["matrix"],"policy":"serial",
    "case_modes":{"matrix":"build"},"component_overrides":{"matrix":{"config":{
        "mode":"single_objective","problems":["sphere","rosenbrock","rastrigin","ackley"],
        "seeds":[11,29],"n_var":10,"steps":120}}}})
GROUPS["single_objective"]={"stages":["single_objective_benchmark"]}

# Standalone Case CLIs use these ordinary single-Case Project stages. Existing
# execution groups retain their original stages and behavior.
for _case_name in ("parallel_a", "parallel_b", "bare_inner", "nested_outer"):
    _stage_name = f"case_{_case_name}"
    STAGES.append({"name": _stage_name, "cases": [_case_name], "policy": "serial",
                   "case_modes": {_case_name: "build"}})
    GROUPS[_stage_name] = {"stages": [_stage_name]}
