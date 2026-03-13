from __future__ import annotations

from nsgablack.project import run_project_doctor


def _build_solver_header() -> str:
    return (
        "class _DummyPlugin:\n"
        "    def __init__(self, name='dummy', priority=0):\n"
        "        self.name = name\n"
        "        self.priority = priority\n"
        "\n"
        "class _DummySolver:\n"
        "    def add_plugin(self, plugin, **kwargs):\n"
        "        return None\n"
        "    def set_plugin_order(self, plugin_name, **kwargs):\n"
        "        return None\n"
        "\n"
        "def build_solver():\n"
        "    solver = _DummySolver()\n"
    )


def test_doctor_component_order_unknown_reference_strict_error(tmp_path):
    (tmp_path / "build_solver.py").write_text(
        _build_solver_header()
        + "    solver.add_plugin(_DummyPlugin(name='companion', priority=1), after=('pareto_archive',))\n"
        + "    return solver\n",
        encoding="utf-8",
    )

    report = run_project_doctor(tmp_path, instantiate_solver=False, strict=True)
    rows = [d for d in report.diagnostics if d.code == "component-order-unknown-ref"]
    assert rows
    assert all(d.level == "error" for d in rows)


def test_doctor_component_order_cycle_strict_error(tmp_path):
    (tmp_path / "build_solver.py").write_text(
        _build_solver_header()
        + "    solver.add_plugin(_DummyPlugin(name='A', priority=0))\n"
        + "    solver.add_plugin(_DummyPlugin(name='B', priority=0), after=('A',))\n"
        + "    solver.set_plugin_order('A', after=('B',))\n"
        + "    return solver\n",
        encoding="utf-8",
    )

    report = run_project_doctor(tmp_path, instantiate_solver=False, strict=True)
    rows = [d for d in report.diagnostics if d.code == "component-order-cycle"]
    assert rows
    assert all(d.level == "error" for d in rows)


def test_doctor_component_order_priority_conflict_strict_error(tmp_path):
    (tmp_path / "build_solver.py").write_text(
        _build_solver_header()
        + "    solver.add_plugin(_DummyPlugin(name='pareto_archive', priority=10))\n"
        + "    solver.add_plugin(_DummyPlugin(name='companion', priority=1), after=('pareto_archive',))\n"
        + "    return solver\n",
        encoding="utf-8",
    )

    report = run_project_doctor(tmp_path, instantiate_solver=False, strict=True)
    rows = [d for d in report.diagnostics if d.code == "component-order-priority-conflict"]
    assert rows
    assert all(d.level == "error" for d in rows)


def test_doctor_component_order_non_strict_warn(tmp_path):
    (tmp_path / "build_solver.py").write_text(
        _build_solver_header()
        + "    solver.add_plugin(_DummyPlugin(name='companion', priority=1), after=('pareto_archive',))\n"
        + "    return solver\n",
        encoding="utf-8",
    )

    report = run_project_doctor(tmp_path, instantiate_solver=False, strict=False)
    rows = [d for d in report.diagnostics if d.code == "component-order-unknown-ref"]
    assert rows
    assert all(d.level == "warn" for d in rows)


def test_doctor_component_order_plugin_class_cycle_strict_error(tmp_path):
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "build_solver.py").write_text("def build_solver():\n    return object()\n", encoding="utf-8")
    (plugins_dir / "cycle_plugins.py").write_text(
        "from nsgablack.plugins.base import Plugin\n"
        "\n"
        "class APlugin(Plugin):\n"
        "    after_plugins = ('BPlugin',)\n"
        "    def __init__(self):\n"
        "        super().__init__(name='a', priority=0)\n"
        "\n"
        "class BPlugin(Plugin):\n"
        "    after_plugins = ('APlugin',)\n"
        "    def __init__(self):\n"
        "        super().__init__(name='b', priority=0)\n",
        encoding="utf-8",
    )

    report = run_project_doctor(tmp_path, instantiate_solver=False, strict=True)
    rows = [d for d in report.diagnostics if d.code == "component-order-cycle"]
    assert rows
    assert all(d.level == "error" for d in rows)


def test_doctor_component_order_plugin_class_priority_conflict_strict_error(tmp_path):
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "build_solver.py").write_text("def build_solver():\n    return object()\n", encoding="utf-8")
    (plugins_dir / "priority_plugins.py").write_text(
        "from nsgablack.plugins.base import Plugin\n"
        "\n"
        "class HighPlugin(Plugin):\n"
        "    after_plugins = ('low',)\n"
        "    def __init__(self):\n"
        "        super().__init__(name='high', priority=0)\n"
        "\n"
        "class LowPlugin(Plugin):\n"
        "    def __init__(self):\n"
        "        super().__init__(name='low', priority=10)\n",
        encoding="utf-8",
    )

    report = run_project_doctor(tmp_path, instantiate_solver=False, strict=True)
    rows = [d for d in report.diagnostics if d.code == "component-order-priority-conflict"]
    assert rows
    assert all(d.level == "error" for d in rows)
