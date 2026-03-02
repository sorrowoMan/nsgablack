from nsgablack.project import init_project, run_project_doctor


def test_init_project_creates_component_registration_guide(tmp_path):
    root = init_project(tmp_path / "demo_project")
    guide = root / "COMPONENT_REGISTRATION.md"
    marker = root / ".nsgablack-project"
    assert guide.is_file()
    assert marker.is_file()
    text = guide.read_text(encoding="utf-8")
    assert "Why register components" in text
    assert "project_registry.py" in text


def test_project_doctor_warns_when_registration_guide_missing(tmp_path):
    root = init_project(tmp_path / "demo_project")
    guide = root / "COMPONENT_REGISTRATION.md"
    guide.unlink()

    report = run_project_doctor(root, instantiate_solver=False)
    codes = {d.code for d in report.diagnostics}
    assert "missing-component-registration-guide" in codes


def test_project_doctor_skips_scaffold_checks_for_non_scaffold_folder(tmp_path):
    report = run_project_doctor(tmp_path, instantiate_solver=False)
    assert report.error_count == 0
    codes = {d.code for d in report.diagnostics}
    assert "structure-skip" in codes
    assert "registry-skip" in codes
    assert "doctor-common-misuse-hints" in codes


def test_project_doctor_parses_utf8_sig_python_source(tmp_path):
    adapter_dir = tmp_path / "adapter"
    adapter_dir.mkdir(parents=True)
    source = "\ufeffclass ExampleAdapter:\n    pass\n"
    (adapter_dir / "example.py").write_text(source, encoding="utf-8")

    report = run_project_doctor(tmp_path, instantiate_solver=False)
    codes = [d.code for d in report.diagnostics]
    assert "source-parse-failed" not in codes


def test_project_doctor_strict_escalates_missing_contract_to_error(tmp_path):
    adapter_dir = tmp_path / "adapter"
    adapter_dir.mkdir(parents=True)
    source = "class DemoAdapter:\n    pass\n"
    (adapter_dir / "demo_adapter.py").write_text(source, encoding="utf-8")

    report = run_project_doctor(tmp_path, instantiate_solver=False, strict=True)
    rows = [d for d in report.diagnostics if d.code == "class-contract-missing"]
    assert rows
    assert all(d.level == "error" for d in rows)


def test_project_doctor_warns_when_core_contract_keys_missing(tmp_path):
    adapter_dir = tmp_path / "adapter"
    adapter_dir.mkdir(parents=True)
    source = (
        "class DemoAdapter:\n"
        "    context_notes = ('demo',)\n"
        "    def propose(self, solver, context):\n"
        "        return []\n"
    )
    (adapter_dir / "demo_adapter.py").write_text(source, encoding="utf-8")

    report = run_project_doctor(tmp_path, instantiate_solver=False, strict=True)
    rows = [d for d in report.diagnostics if d.code == "class-contract-core-missing"]
    assert rows
    assert all(d.level == "warn" for d in rows)


def test_project_doctor_strict_blocks_template_not_implemented(tmp_path):
    bias_dir = tmp_path / "bias"
    bias_dir.mkdir(parents=True)
    source = (
        "class DemoBias:\n"
        "    context_requires = ()\n"
        "    context_provides = ()\n"
        "    context_mutates = ()\n"
        "    context_cache = ()\n"
        "    context_notes = ('demo',)\n"
        "    def compute(self, x, context):\n"
        "        raise NotImplementedError\n"
    )
    (bias_dir / "demo_bias.py").write_text(source, encoding="utf-8")

    report = run_project_doctor(tmp_path, instantiate_solver=False, strict=True)
    rows = [d for d in report.diagnostics if d.code == "template-not-implemented"]
    assert rows
    assert all(d.level == "error" for d in rows)


def test_project_doctor_strict_blocks_solver_mirror_writes(tmp_path):
    adapter_dir = tmp_path / "adapter"
    adapter_dir.mkdir(parents=True)
    source = (
        "class DemoAdapter:\n"
        "    context_requires = ()\n"
        "    context_provides = ()\n"
        "    context_mutates = ()\n"
        "    context_cache = ()\n"
        "    context_notes = 'ok'\n"
        "    def update(self, solver):\n"
        "        solver.shared_state = {}\n"
    )
    (adapter_dir / "demo_adapter.py").write_text(source, encoding="utf-8")

    report = run_project_doctor(tmp_path, instantiate_solver=False, strict=True)
    rows = [d for d in report.diagnostics if d.code == "solver-mirror-write"]
    assert rows
    assert all(d.level == "error" for d in rows)


def test_project_doctor_non_strict_warns_solver_mirror_writes(tmp_path):
    adapter_dir = tmp_path / "adapter"
    adapter_dir.mkdir(parents=True)
    source = (
        "class DemoAdapter:\n"
        "    context_requires = ()\n"
        "    context_provides = ()\n"
        "    context_mutates = ()\n"
        "    context_cache = ()\n"
        "    context_notes = 'ok'\n"
        "    def update(self, solver):\n"
        "        solver.shared_state = {}\n"
    )
    (adapter_dir / "demo_adapter.py").write_text(source, encoding="utf-8")

    report = run_project_doctor(tmp_path, instantiate_solver=False, strict=False)
    rows = [d for d in report.diagnostics if d.code == "solver-mirror-write"]
    assert rows
    assert all(d.level == "warn" for d in rows)


def test_project_doctor_strict_blocks_runtime_bypass_writes(tmp_path):
    adapter_dir = tmp_path / "adapter"
    adapter_dir.mkdir(parents=True)
    source = (
        "class DemoAdapter:\n"
        "    context_requires = ()\n"
        "    context_provides = ()\n"
        "    context_mutates = ()\n"
        "    context_cache = ()\n"
        "    context_notes = 'ok'\n"
        "    def update(self, solver):\n"
        "        solver.best_objective = 1.0\n"
    )
    (adapter_dir / "demo_adapter.py").write_text(source, encoding="utf-8")

    report = run_project_doctor(tmp_path, instantiate_solver=False, strict=True)
    rows = [d for d in report.diagnostics if d.code == "runtime-bypass-write"]
    assert rows
    assert all(d.level == "error" for d in rows)


def test_project_doctor_strict_allows_runtime_api_calls(tmp_path):
    adapter_dir = tmp_path / "adapter"
    adapter_dir.mkdir(parents=True)
    source = (
        "class DemoAdapter:\n"
        "    context_requires = ()\n"
        "    context_provides = ()\n"
        "    context_mutates = ()\n"
        "    context_cache = ()\n"
        "    context_notes = 'ok'\n"
        "    def update(self, solver):\n"
        "        solver.write_population_snapshot([[0.0]], [[0.0]], [0.0])\n"
    )
    (adapter_dir / "demo_adapter_ok.py").write_text(source, encoding="utf-8")

    report = run_project_doctor(tmp_path, instantiate_solver=False, strict=True)
    rows = [d for d in report.diagnostics if d.code == "runtime-bypass-write"]
    assert not rows


def test_project_doctor_strict_blocks_plugin_direct_solver_state_access(tmp_path):
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir(parents=True)
    source = (
        "class DemoPlugin:\n"
        "    context_requires = ()\n"
        "    context_provides = ()\n"
        "    context_mutates = ()\n"
        "    context_cache = ()\n"
        "    context_notes = 'ok'\n"
        "    def on_generation_end(self):\n"
        "        x = self.solver.population\n"
        "        self.solver.objectives[0] = x[0]\n"
    )
    (plugins_dir / "demo_plugin.py").write_text(source, encoding="utf-8")

    report = run_project_doctor(tmp_path, instantiate_solver=False, strict=True)
    rows = [d for d in report.diagnostics if d.code == "plugin-direct-solver-state-access"]
    assert rows
    assert all(d.level == "error" for d in rows)


def test_project_doctor_strict_blocks_examples_direct_solver_control_writes(tmp_path):
    examples_dir = tmp_path / "examples"
    examples_dir.mkdir(parents=True)
    source = (
        "def run_demo(solver):\n"
        "    solver.max_steps = 12\n"
        "    solver.adapter = object()\n"
    )
    (examples_dir / "demo.py").write_text(source, encoding="utf-8")

    report = run_project_doctor(tmp_path, instantiate_solver=False, strict=True)
    rows = [d for d in report.diagnostics if d.code == "examples-suites-direct-solver-control-write"]
    assert rows
    assert all(d.level == "error" for d in rows)


def test_project_doctor_accepts_examples_using_solver_control_plane_methods(tmp_path):
    examples_dir = tmp_path / "examples"
    examples_dir.mkdir(parents=True)
    source = (
        "def run_demo(solver):\n"
        "    solver.set_max_steps(12)\n"
        "    solver.set_adapter(object())\n"
        "    solver.set_solver_hyperparams(pop_size=16)\n"
    )
    (examples_dir / "demo_ok.py").write_text(source, encoding="utf-8")

    report = run_project_doctor(tmp_path, instantiate_solver=False, strict=True)
    rows = [d for d in report.diagnostics if d.code == "examples-suites-direct-solver-control-write"]
    assert not rows


def test_project_doctor_strict_blocks_missing_metrics_provider(tmp_path):
    root = init_project(tmp_path / "metrics_project")
    (root / "build_solver.py").write_text(
        "from types import SimpleNamespace\n"
        "\n"
        "class DemoMetricsConsumer:\n"
        "    context_requires = ()\n"
        "    context_provides = ()\n"
        "    context_mutates = ()\n"
        "    context_cache = ()\n"
        "    context_notes = 'demo metrics consumer'\n"
        "    requires_metrics = ('foo',)\n"
        "    missing_metrics_policy = 'error'\n"
        "    def get_context_contract(self):\n"
        "        return {\n"
        "            'requires': ('metrics.foo',),\n"
        "            'provides': (),\n"
        "            'mutates': (),\n"
        "            'cache': (),\n"
        "            'notes': 'no fallback',\n"
        "        }\n"
        "\n"
        "def build_solver():\n"
        "    return SimpleNamespace(\n"
        "        representation_pipeline=None,\n"
        "        bias_module=DemoMetricsConsumer(),\n"
        "        adapter=None,\n"
        "        plugin_manager=None,\n"
        "    )\n",
        encoding="utf-8",
    )

    report = run_project_doctor(root, instantiate_solver=True, strict=True)
    rows = [d for d in report.diagnostics if d.code == "metrics-provider-missing"]
    assert rows
    assert all(d.level == "error" for d in rows)


def test_project_doctor_allows_requires_metrics_with_explicit_fallback(tmp_path):
    root = init_project(tmp_path / "metrics_fallback_project")
    (root / "build_solver.py").write_text(
        "from types import SimpleNamespace\n"
        "\n"
        "class DemoMetricsConsumer:\n"
        "    context_requires = ()\n"
        "    context_provides = ()\n"
        "    context_mutates = ()\n"
        "    context_cache = ()\n"
        "    context_notes = 'demo metrics consumer'\n"
        "    requires_metrics = ('foo',)\n"
        "    missing_metrics_policy = 'error'\n"
        "    metrics_fallback = 'default'\n"
        "    def get_context_contract(self):\n"
        "        return {\n"
        "            'requires': ('metrics.foo',),\n"
            "            'provides': (),\n"
            "            'mutates': (),\n"
            "            'cache': (),\n"
        "            'notes': 'fallback is explicit in metrics_fallback',\n"
        "        }\n"
        "\n"
        "def build_solver():\n"
        "    return SimpleNamespace(\n"
        "        representation_pipeline=None,\n"
        "        bias_module=DemoMetricsConsumer(),\n"
        "        adapter=None,\n"
        "        plugin_manager=None,\n"
        "    )\n",
        encoding="utf-8",
    )

    report = run_project_doctor(root, instantiate_solver=True, strict=True)
    assert not [d for d in report.diagnostics if d.code == "metrics-provider-missing"]


def test_project_doctor_does_not_treat_notes_as_metrics_fallback(tmp_path):
    root = init_project(tmp_path / "metrics_notes_only_project")
    (root / "build_solver.py").write_text(
        "from types import SimpleNamespace\n"
        "\n"
        "class DemoMetricsConsumer:\n"
        "    context_requires = ()\n"
        "    context_provides = ()\n"
        "    context_mutates = ()\n"
        "    context_cache = ()\n"
        "    context_notes = 'demo metrics consumer'\n"
        "    requires_metrics = ('foo',)\n"
        "    missing_metrics_policy = 'error'\n"
        "    def get_context_contract(self):\n"
        "        return {\n"
        "            'requires': ('metrics.foo',),\n"
        "            'provides': (),\n"
        "            'mutates': (),\n"
        "            'cache': (),\n"
        "            'notes': 'fallback from notes only',\n"
        "        }\n"
        "\n"
        "def build_solver():\n"
        "    return SimpleNamespace(\n"
        "        representation_pipeline=None,\n"
        "        bias_module=DemoMetricsConsumer(),\n"
        "        adapter=None,\n"
        "        plugin_manager=None,\n"
        "    )\n",
        encoding="utf-8",
    )

    report = run_project_doctor(root, instantiate_solver=True, strict=True)
    rows = [d for d in report.diagnostics if d.code == "metrics-provider-missing"]
    assert rows
    assert all(d.level == "error" for d in rows)


def test_project_doctor_strict_blocks_invalid_metrics_fallback_literal(tmp_path):
    bias_dir = tmp_path / "bias"
    bias_dir.mkdir(parents=True)
    source = (
        "class DemoBias:\n"
        "    context_requires = ()\n"
        "    context_provides = ()\n"
        "    context_mutates = ()\n"
        "    context_cache = ()\n"
        "    context_notes = 'ok'\n"
        "    metrics_fallback = 'bad_mode'\n"
    )
    (bias_dir / "demo_bias.py").write_text(source, encoding="utf-8")

    report = run_project_doctor(tmp_path, instantiate_solver=False, strict=True)
    rows = [d for d in report.diagnostics if d.code == "metrics-fallback-invalid"]
    assert rows
    assert all(d.level == "error" for d in rows)


def test_project_doctor_strict_blocks_nonliteral_metrics_fallback(tmp_path):
    bias_dir = tmp_path / "bias"
    bias_dir.mkdir(parents=True)
    source = (
        "class DemoBias:\n"
        "    context_requires = ()\n"
        "    context_provides = ()\n"
        "    context_mutates = ()\n"
        "    context_cache = ()\n"
        "    context_notes = 'ok'\n"
        "    metrics_fallback = FALLBACK_MODE\n"
    )
    (bias_dir / "demo_bias.py").write_text(source, encoding="utf-8")

    report = run_project_doctor(tmp_path, instantiate_solver=False, strict=True)
    rows = [d for d in report.diagnostics if d.code == "metrics-fallback-nonliteral"]
    assert rows
    assert all(d.level == "error" for d in rows)


def test_project_doctor_strict_blocks_invalid_metrics_fallback_in_build_solver(tmp_path):
    root = init_project(tmp_path / "metrics_bad_fallback_project")
    (root / "build_solver.py").write_text(
        "from types import SimpleNamespace\n"
        "\n"
        "class DemoMetricsConsumer:\n"
        "    context_requires = ()\n"
        "    context_provides = ()\n"
        "    context_mutates = ()\n"
        "    context_cache = ()\n"
        "    context_notes = 'demo metrics consumer'\n"
        "    requires_metrics = ('foo',)\n"
        "    missing_metrics_policy = 'error'\n"
        "    metrics_fallback = 'bad_mode'\n"
        "    def get_context_contract(self):\n"
        "        return {\n"
        "            'requires': ('metrics.foo',),\n"
        "            'provides': (),\n"
        "            'mutates': (),\n"
        "            'cache': (),\n"
        "            'notes': 'invalid fallback enum value',\n"
        "        }\n"
        "\n"
        "def build_solver():\n"
        "    return SimpleNamespace(\n"
        "        representation_pipeline=None,\n"
        "        bias_module=DemoMetricsConsumer(),\n"
        "        adapter=None,\n"
        "        plugin_manager=None,\n"
        "    )\n",
        encoding="utf-8",
    )

    report = run_project_doctor(root, instantiate_solver=True, strict=True)
    rows = [d for d in report.diagnostics if d.code == "metrics-fallback-invalid"]
    assert rows
    assert all(d.level == "error" for d in rows)


def test_project_doctor_strict_blocks_process_like_algorithm_as_bias(tmp_path):
    root = init_project(tmp_path / "process_like_bias_project")
    (root / "build_solver.py").write_text(
        "from types import SimpleNamespace\n"
        "\n"
        "class NSGA2Bias:\n"
        "    context_requires = ()\n"
        "    context_provides = ()\n"
        "    context_mutates = ()\n"
        "    context_cache = ()\n"
        "    context_notes = 'demo'\n"
        "NSGA2Bias.__module__ = 'nsgablack.bias.algorithmic.nsga2'\n"
        "\n"
        "class FakeBiasModule:\n"
        "    def __init__(self, manager):\n"
        "        self._manager = manager\n"
        "    def get_context_contract(self):\n"
        "        return {\n"
        "            'requires': (),\n"
        "            'provides': (),\n"
        "            'mutates': (),\n"
        "            'cache': (),\n"
        "            'notes': 'fake',\n"
        "        }\n"
        "\n"
        "def build_solver():\n"
        "    fake_mgr = SimpleNamespace(\n"
        "        algorithmic_manager=SimpleNamespace(biases={'nsga2': NSGA2Bias()}),\n"
        "        domain_manager=SimpleNamespace(biases={}),\n"
        "    )\n"
        "    fake_bias_module = FakeBiasModule(fake_mgr)\n"
        "    return SimpleNamespace(\n"
        "        representation_pipeline=None,\n"
        "        bias_module=fake_bias_module,\n"
        "        adapter=None,\n"
        "        plugin_manager=None,\n"
        "    )\n",
        encoding="utf-8",
    )

    report = run_project_doctor(root, instantiate_solver=True, strict=True)
    rows = [d for d in report.diagnostics if d.code == "algorithm-as-bias"]
    assert rows
    assert all(d.level == "error" for d in rows)


def test_project_doctor_does_not_flag_normal_bias_as_process_like(tmp_path):
    root = init_project(tmp_path / "normal_bias_project")
    (root / "build_solver.py").write_text(
        "from types import SimpleNamespace\n"
        "\n"
        "class ConvergenceBias:\n"
        "    context_requires = ()\n"
        "    context_provides = ()\n"
        "    context_mutates = ()\n"
        "    context_cache = ()\n"
        "    context_notes = 'demo'\n"
        "\n"
        "class FakeBiasModule:\n"
        "    def __init__(self, manager):\n"
        "        self._manager = manager\n"
        "    def get_context_contract(self):\n"
        "        return {\n"
        "            'requires': (),\n"
        "            'provides': (),\n"
        "            'mutates': (),\n"
        "            'cache': (),\n"
        "            'notes': 'fake',\n"
        "        }\n"
        "\n"
        "def build_solver():\n"
        "    fake_mgr = SimpleNamespace(\n"
        "        algorithmic_manager=SimpleNamespace(biases={'conv': ConvergenceBias()}),\n"
        "        domain_manager=SimpleNamespace(biases={}),\n"
        "    )\n"
        "    fake_bias_module = FakeBiasModule(fake_mgr)\n"
        "    return SimpleNamespace(\n"
        "        representation_pipeline=None,\n"
        "        bias_module=fake_bias_module,\n"
        "        adapter=None,\n"
        "        plugin_manager=None,\n"
        "    )\n",
        encoding="utf-8",
    )

    report = run_project_doctor(root, instantiate_solver=True, strict=True)
    assert not [d for d in report.diagnostics if d.code == "algorithm-as-bias"]


def test_project_doctor_strict_blocks_redis_key_prefix_without_project_token(tmp_path):
    root = init_project(tmp_path / "redis_guard_project")
    (root / "build_solver.py").write_text(
        "from types import SimpleNamespace\n"
        "\n"
        "def build_solver():\n"
        "    return SimpleNamespace(\n"
        "        representation_pipeline=None,\n"
        "        bias_module=None,\n"
        "        adapter=None,\n"
        "        plugin_manager=None,\n"
        "        context_store_backend='redis',\n"
        "        context_store_key_prefix='ctx',\n"
        "        context_store_ttl_seconds=120,\n"
        "    )\n",
        encoding="utf-8",
    )
    report = run_project_doctor(root, instantiate_solver=True, strict=True)
    codes = {d.code for d in report.diagnostics if d.level == "error"}
    assert "redis-key-prefix-too-short" in codes
    assert "redis-key-prefix-missing-project-name" in codes


def test_project_doctor_warns_when_redis_ttl_policy_is_implicit(tmp_path):
    root = init_project(tmp_path / "redis_ttl_policy_project")
    (root / "build_solver.py").write_text(
        "from types import SimpleNamespace\n"
        "\n"
        "def build_solver():\n"
        "    return SimpleNamespace(\n"
        "        representation_pipeline=None,\n"
        "        bias_module=None,\n"
        "        adapter=None,\n"
        "        plugin_manager=None,\n"
        "        context_store_backend='redis',\n"
        "        context_store_key_prefix='nsgablack:redis_ttl_policy_project',\n"
        "        context_store_ttl_seconds=None,\n"
        "    )\n",
        encoding="utf-8",
    )
    report = run_project_doctor(root, instantiate_solver=True, strict=True)
    rows = [d for d in report.diagnostics if d.code == "redis-ttl-policy-implicit"]
    assert rows
    assert all(d.level == "warn" for d in rows)


def test_project_doctor_strict_blocks_framework_component_missing_catalog_entry(tmp_path):
    root = init_project(tmp_path / "framework_catalog_guard_project")
    (root / "build_solver.py").write_text(
        "from types import SimpleNamespace\n"
        "\n"
        "class MissingFrameworkAdapter:\n"
        "    context_requires = ()\n"
        "    context_provides = ()\n"
        "    context_mutates = ()\n"
        "    context_cache = ()\n"
        "    context_notes = ('demo',)\n"
        "MissingFrameworkAdapter.__module__ = 'nsgablack.core.adapters.__missing__'\n"
        "\n"
        "def build_solver():\n"
        "    return SimpleNamespace(\n"
        "        representation_pipeline=None,\n"
        "        bias_module=None,\n"
        "        adapter=MissingFrameworkAdapter(),\n"
        "        plugin_manager=None,\n"
        "    )\n",
        encoding="utf-8",
    )
    report = run_project_doctor(root, instantiate_solver=True, strict=True)
    rows = [d for d in report.diagnostics if d.code == "framework-component-not-in-catalog"]
    assert rows
    assert all(d.level == "error" for d in rows)


def test_project_doctor_reports_unregistered_project_components_as_info(tmp_path):
    root = init_project(tmp_path / "project_unregistered_component_info")
    (root / "build_solver.py").write_text(
        "from types import SimpleNamespace\n"
        "\n"
        "class LocalAdapter:\n"
        "    context_requires = ()\n"
        "    context_provides = ()\n"
        "    context_mutates = ()\n"
        "    context_cache = ()\n"
        "    context_notes = ('demo',)\n"
        "LocalAdapter.__module__ = 'my_project.adapter.local_adapter'\n"
        "\n"
        "def build_solver():\n"
        "    return SimpleNamespace(\n"
        "        representation_pipeline=None,\n"
        "        bias_module=None,\n"
        "        adapter=LocalAdapter(),\n"
        "        plugin_manager=None,\n"
        "    )\n",
        encoding="utf-8",
    )
    report = run_project_doctor(root, instantiate_solver=True, strict=True)
    rows = [d for d in report.diagnostics if d.code == "project-component-unregistered"]
    assert rows
    assert all(d.level == "info" for d in rows)


def test_project_doctor_warns_unknown_contract_keys(tmp_path):
    adapter_dir = tmp_path / "adapter"
    adapter_dir.mkdir(parents=True)
    source = (
        "class DemoAdapter:\n"
        "    context_requires = ('phase_id', 'unknown_feature_flag')\n"
        "    context_provides = ('metrics.custom_score',)\n"
        "    context_mutates = ()\n"
        "    context_cache = ()\n"
        "    context_notes = 'ok'\n"
    )
    (adapter_dir / "demo_adapter.py").write_text(source, encoding="utf-8")

    report = run_project_doctor(tmp_path, instantiate_solver=False, strict=True)
    rows = [d for d in report.diagnostics if d.code == "contract-key-unknown"]
    assert rows
    assert all(d.level == "warn" for d in rows)
    assert any("unknown_feature_flag" in d.message for d in rows)


def test_project_doctor_warns_contract_impl_mismatch(tmp_path):
    adapter_dir = tmp_path / "adapter"
    adapter_dir.mkdir(parents=True)
    source = (
        "class DemoAdapter:\n"
        "    context_requires = ('generation',)\n"
        "    context_provides = ()\n"
        "    context_mutates = ()\n"
        "    context_cache = ()\n"
        "    context_notes = 'ok'\n"
        "    def run(self, context):\n"
        "        _ = context['phase_id']\n"
        "        context['dynamic'] = {'a': 1}\n"
        "        return _\n"
    )
    (adapter_dir / "demo_adapter.py").write_text(source, encoding="utf-8")

    report = run_project_doctor(tmp_path, instantiate_solver=False, strict=True)
    rows = [d for d in report.diagnostics if d.code == "contract-impl-mismatch"]
    assert rows
    assert all(d.level == "warn" for d in rows)
    assert any("phase_id" in d.message for d in rows)
    assert any("dynamic" in d.message for d in rows)


def test_project_doctor_warns_large_object_context_write(tmp_path):
    adapter_dir = tmp_path / "adapter"
    adapter_dir.mkdir(parents=True)
    source = (
        "class DemoAdapter:\n"
        "    context_requires = ()\n"
        "    context_provides = ()\n"
        "    context_mutates = ('population',)\n"
        "    context_cache = ()\n"
        "    context_notes = 'ok'\n"
        "    def run(self, context):\n"
        "        context['population'] = [[1.0, 2.0]]\n"
    )
    (adapter_dir / "demo_adapter.py").write_text(source, encoding="utf-8")

    report = run_project_doctor(tmp_path, instantiate_solver=False, strict=True)
    rows = [d for d in report.diagnostics if d.code == "context-large-object-write"]
    assert rows
    assert all(d.level == "warn" for d in rows)


def test_project_doctor_warns_snapshot_ref_unreadable(tmp_path):
    root = init_project(tmp_path / "snapshot_ref_consistency_project")
    (root / "build_solver.py").write_text(
        "class DemoSolver:\n"
        "    def __init__(self):\n"
        "        self.population = [[0.0, 1.0]]\n"
        "        self.objectives = [[1.0]]\n"
        "        self.constraint_violations = [0.0]\n"
        "    def get_context(self):\n"
        "        return {\n"
        "            'snapshot_key': 'snap-ok',\n"
        "            'population_ref': 'snap-missing',\n"
        "            'objectives_ref': 'snap-ok',\n"
        "            'constraint_violations_ref': 'snap-ok',\n"
        "        }\n"
        "    def read_snapshot(self, key):\n"
        "        if key == 'snap-ok':\n"
        "            return {\n"
        "                'population': [[0.0, 1.0]],\n"
        "                'objectives': [[1.0]],\n"
        "                'constraint_violations': [0.0],\n"
        "            }\n"
        "        return None\n"
        "\n"
        "def build_solver():\n"
        "    return DemoSolver()\n",
        encoding="utf-8",
    )

    report = run_project_doctor(root, instantiate_solver=True, strict=True)
    rows = [d for d in report.diagnostics if d.code == "snapshot-ref-consistency"]
    assert rows
    assert any(d.level == "error" for d in rows)


def test_project_doctor_warns_snapshot_payload_shape_mismatch(tmp_path):
    root = init_project(tmp_path / "snapshot_payload_integrity_project")
    (root / "build_solver.py").write_text(
        "class DemoSolver:\n"
        "    def __init__(self):\n"
        "        self.population = [[0.0, 1.0], [2.0, 3.0]]\n"
        "        self.objectives = [[1.0], [2.0]]\n"
        "        self.constraint_violations = [0.0, 0.0]\n"
        "    def get_context(self):\n"
        "        return {\n"
        "            'snapshot_key': 'snap-bad',\n"
        "            'population_ref': 'snap-bad',\n"
        "            'objectives_ref': 'snap-bad',\n"
        "            'constraint_violations_ref': 'snap-bad',\n"
        "        }\n"
        "    def read_snapshot(self, key):\n"
        "        if key != 'snap-bad':\n"
        "            return None\n"
        "        return {\n"
        "            'population': [[0.0, 1.0]],\n"
        "            'objectives': [[1.0], [2.0]],\n"
        "            'constraint_violations': [0.0],\n"
        "        }\n"
        "\n"
        "def build_solver():\n"
        "    return DemoSolver()\n",
        encoding="utf-8",
    )

    report = run_project_doctor(root, instantiate_solver=True, strict=False)
    rows = [d for d in report.diagnostics if d.code == "snapshot-payload-integrity"]
    assert rows
    assert all(d.level == "warn" for d in rows)
