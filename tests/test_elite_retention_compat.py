from __future__ import annotations

import numpy as np
import pytest

from nsgablack.adapters import AlgorithmAdapter, EliteRetentionAdapter


class _Inner(AlgorithmAdapter):
    def __init__(self) -> None:
        super().__init__("inner")
        self.setup_count = 0

    def setup(self, control) -> None:
        del control
        self.setup_count += 1

    def propose(self, control, context):
        del control, context
        return (np.asarray([1.0]),)

    def update(self, control, candidates, feedback, context):
        del control, candidates, feedback, context


class _Solver:
    def __init__(self, adapter=None) -> None:
        self.adapter = adapter

    def set_adapter(self, adapter) -> None:
        self.adapter = adapter

    def fork_rng(self, name):
        del name
        return np.random.default_rng(11)


def _assert_policy_warning(records, old_symbol: str) -> None:
    message = "\n".join(str(item.message) for item in records)
    assert f"old={old_symbol}" in message
    assert "new=nsgablack.adapters.EliteRetentionAdapter" in message
    assert "remove_in=1.0.0" in message


def test_old_import_paths_resolve_to_the_compatibility_classes() -> None:
    from nsgablack.plugins import BasicElitePlugin, HistoricalElitePlugin
    from nsgablack.plugins.runtime.elite_retention import (
        BasicElitePlugin as RuntimeBasicElitePlugin,
        HistoricalElitePlugin as RuntimeHistoricalElitePlugin,
    )
    from nsgablack.utils.compat import (
        BasicElitePlugin as CompatBasicElitePlugin,
        HistoricalElitePlugin as CompatHistoricalElitePlugin,
    )

    assert BasicElitePlugin is RuntimeBasicElitePlugin is CompatBasicElitePlugin
    assert HistoricalElitePlugin is RuntimeHistoricalElitePlugin is CompatHistoricalElitePlugin


def test_basic_compat_wraps_adapter_before_plugin_without_population_write() -> None:
    from nsgablack.plugins import BasicElitePlugin

    inner = _Inner()
    solver = _Solver(inner)
    with pytest.warns(DeprecationWarning) as constructed:
        plugin = BasicElitePlugin(retention_prob=0.7, retention_ratio=0.25)
    _assert_policy_warning(constructed, "nsgablack.plugins.BasicElitePlugin")

    with pytest.warns(DeprecationWarning) as attached:
        plugin.attach(solver)
    _assert_policy_warning(attached, "nsgablack.plugins.BasicElitePlugin.attach")

    assert isinstance(solver.adapter, EliteRetentionAdapter)
    assert solver.adapter.inner is inner
    assert solver.adapter.config.retention_probability == 0.7
    assert solver.adapter.config.retention_ratio == 0.25
    with pytest.raises(RuntimeError, match="Plugins cannot commit population authority"):
        plugin.commit_population_snapshot([[1.0]], [[1.0]], [0.0], solver)


def test_historical_compat_wraps_plugin_before_adapter_without_double_setup() -> None:
    from nsgablack.plugins import HistoricalElitePlugin

    solver = _Solver()
    with pytest.warns(DeprecationWarning) as constructed:
        plugin = HistoricalElitePlugin(
            history_size=7,
            replacement_prob=0.4,
            replacement_ratio=0.2,
        )
    _assert_policy_warning(constructed, "nsgablack.plugins.HistoricalElitePlugin")
    with pytest.warns(DeprecationWarning) as attached:
        plugin.attach(solver)
    _assert_policy_warning(attached, "nsgablack.plugins.HistoricalElitePlugin.attach")
    assert solver.adapter is None

    inner = _Inner()
    solver.set_adapter(inner)
    inner.setup(solver)  # Solver.setup() runs before Plugin.on_solver_init().
    plugin.on_solver_init(solver)

    assert isinstance(solver.adapter, EliteRetentionAdapter)
    assert solver.adapter.inner is inner
    assert inner.setup_count == 1
    assert solver.adapter.config.history_size == 7
    assert solver.adapter.config.retention_probability == 0.4
    assert solver.adapter.config.retention_ratio == 0.2


def test_deprecated_catalog_entry_loads_and_points_to_canonical_adapter() -> None:
    from nsgablack.catalog import get_catalog
    from nsgablack.plugins import BasicElitePlugin

    entry = get_catalog(refresh=True).get("plugin.elite")

    assert entry is not None
    assert "deprecated" in set(entry.tags)
    assert "adapter.elite_retention" in set(entry.required_companions)
    assert entry.load() is BasicElitePlugin


@pytest.mark.parametrize("key", ("basic_elite", "historical_elite"))
def test_legacy_project_config_keys_build_compatibility_plugins(key: str) -> None:
    from my_project.plugins.config import (
        FlowPluginRegistry,
        PluginSpec,
        build_flow_plugins,
    )

    registry = FlowPluginRegistry(registry=(PluginSpec(key=key),))
    with pytest.warns(DeprecationWarning, match="remove_in=1.0.0"):
        built = build_flow_plugins(registry, (key,))

    assert len(built) == 1
    assert built[0].name == key
