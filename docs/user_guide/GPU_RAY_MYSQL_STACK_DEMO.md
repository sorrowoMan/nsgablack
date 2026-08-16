# GPU + Ray + MySQL Through Project L0

This page replaces the old single-script demo contract. GPU, Ray, and MySQL are no longer described as flags owned by an example file. They are project-level substrate capabilities:

- The Project declares available resources and shared service backends.
- Each Case declares a local resource request and optional runtime profile.
- `run_project.py` grants a `ResourceContext` to every Case.
- The Case consumes the grant through `build_solver(..., resource_context=...)`.

## Project Shape

```text
project_root/
  project_config.py
  run_project.py
  cases/
    optimization_case/
      build_solver.py
      config.py
      runtime/
      plugins/
```

`project_config.py` is the only place that should declare global GPU tokens, Ray settings, or database logging sinks.

```python
L0 = {
    "backend": "local",
    "resource_pool": {
        "threads": 12,
        "device_tokens": ("logical-gpu-a", "logical-gpu-b"),
    },
    "services": {
        "ray": {"enabled": False, "address": "local"},
        "mysql": {"enabled": False, "table": "nsgablack_runs"},
    },
}

resource_requests = {
    "optimization_case": {
        "threads": 4,
        "device_tokens": ("logical-gpu-a",),
        "services": ("ray", "mysql"),
    }
}
```

The token names are project-local. They may map to CUDA, ROCm, CPU simulation, a remote queue, or a managed accelerator. Case code should not assume the physical device name.

## Case Consumption

`build_solver.py` accepts the effective grant:

```python
def build_solver(config=None, *, resource_context=None, component_overrides=None):
    solver = make_solver(config)
    runtime_profile = build_runtime_profile(resource_context)
    solver.add_plugin(build_resource_audit_plugin(runtime_profile))
    solver.add_plugin(build_optional_mysql_logger(runtime_profile))
    maybe_attach_parallel_backend(solver, runtime_profile)
    return solver
```

The Case can decide whether to attach GPU acceleration, Ray parallelism, or MySQL logging, but it must derive those decisions from `resource_context` and local config. If a requested service is unavailable, the Case reports fallback explicitly.

## Run Commands

Formal run:

```powershell
python run_project.py
```

Case debug run:

```powershell
python cases\optimization_case\run_solver.py --check
```

The debug path may print the Case request, but it must say that no Project grant is active unless the caller provides one.

## Audit Requirements

Every run summary should include:

- effective `ResourceContext`
- enabled services
- backend selected by the Case
- fallback reason, if any
- artifact and run namespace

This keeps GPU, Ray, and MySQL behavior reproducible without putting machine-specific settings inside examples.
