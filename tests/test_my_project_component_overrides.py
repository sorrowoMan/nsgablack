from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT / "my_project"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import build_solver as project_build_solver  # type: ignore  # noqa: E402


def test_my_project_scaffold_component_overrides_apply_to_bias_and_plugin() -> None:
    solver = project_build_solver.build_solver(
        run_id="component_override_smoke",
        bias_key="default",
        ops_plugin_keys=("example_plugin",),
        component_overrides={
            "bias.default": {
                "enable_bias": True,
                "diversity_weight": 0.33,
                "diversity_metric": "manhattan",
            },
            "ops_plugin.example_plugin": {
                "interval": 1,
                "verbose": False,
            },
        },
    )

    bias = getattr(solver, "bias_module", None).get_bias("diversity")
    assert bias is not None
    assert abs(float(getattr(bias, "weight", 0.0)) - 0.33) < 1.0e-12
    assert str(getattr(bias, "metric", "")) == "manhattan"

    plugin_manager = getattr(solver, "plugin_manager", None)
    plugins = tuple(plugin_manager.list_plugins(enabled_only=False))
    example_plugin = next((p for p in plugins if str(getattr(p, "name", "")) == "project_example_plugin"), None)
    assert example_plugin is not None
    assert int(getattr(example_plugin, "interval", 0)) == 1
    assert bool(getattr(example_plugin, "verbose", True)) is False

    solver.pop_size = 10
    solver.max_generations = 2
    solver.enable_progress_log = False
    result = solver.run(return_dict=True)
    payload = dict(result.get("example_project_plugin", {}) or {})
    assert int(payload.get("interval", 0)) == 1
    assert int(payload.get("hit_count", 0)) >= 1
