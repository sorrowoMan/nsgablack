from __future__ import annotations

from nsgablack.project import run_project_doctor


def test_doctor_flags_plugin_eval_short_circuit_in_strict(tmp_path):
    (tmp_path / "build_solver.py").write_text("def build_solver():\n    return object()\n", encoding="utf-8")
    plugins = tmp_path / "plugins"
    plugins.mkdir(parents=True, exist_ok=True)
    (plugins / "bad_eval_plugin.py").write_text(
        "from nsgablack.plugins.base import Plugin\n"
        "class BadPlugin(Plugin):\n"
        "    def __init__(self):\n"
        "        super().__init__(name='bad')\n"
        "    def evaluate_population(self, solver, population):\n"
        "        return None\n",
        encoding="utf-8",
    )
    report = run_project_doctor(tmp_path, instantiate_solver=False, strict=True)
    rows = [d for d in report.diagnostics if d.code == "plugin-eval-short-circuit-forbidden"]
    assert rows, "expected doctor to block plugin-based evaluation short-circuit"
