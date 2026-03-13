# -*- coding: utf-8 -*-
"""Tests for plugin attach failure handling strategies."""

from __future__ import annotations

from typing import Any
import pytest

from nsgablack.core.blank_solver import SolverBase
from nsgablack.core.base import BlackBoxProblem
from nsgablack.plugins.base import Plugin
import numpy as np


class SimpleProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=2, bounds=[(-1, 1), (-1, 1)])
    
    def evaluate(self, x: np.ndarray) -> np.ndarray:
        return np.array([np.sum(x**2)])
    
    def get_num_objectives(self) -> int:
        return 1


class FaultyAttachPlugin(Plugin):
    """Plugin that always fails during attach."""
    
    def __init__(self, failure_message: str = "Simulated attach failure"):
        super().__init__("FaultyAttach")
        self.failure_message = failure_message
        self.init_called = False
    
    def attach(self, solver: Any) -> None:
        raise RuntimeError(self.failure_message)
    
    def on_solver_init(self, solver: Any) -> None:
        self.init_called = True


class WorkingPlugin(Plugin):
    """Plugin that works correctly."""
    
    def __init__(self):
        super().__init__("Working")
        self.init_called = False
        self.start_count = 0
    
    def attach(self, solver: Any) -> None:
        super().attach(solver)
        self.attached_solver = solver
    
    def on_solver_init(self, solver: Any) -> None:
        self.init_called = True
    
    def on_generation_start(self, generation: int) -> None:
        self.start_count += 1


def test_plugin_attach_failure_soft_mode():
    """Test plugin attach failure in soft mode (default)."""
    
    solver = SolverBase(problem=SimpleProblem(), plugin_strict=False)
    faulty_plugin = FaultyAttachPlugin()
    
    # Should not raise, but plugin should be marked as failed
    solver.add_plugin(faulty_plugin)
    
    # Plugin should be registered
    assert solver.plugin_manager.get("FaultyAttach") is not None
    
    # Plugin should be marked as attach_failed
    assert hasattr(faulty_plugin, "_attach_failed")
    assert faulty_plugin._attach_failed is True
    assert hasattr(faulty_plugin, "_attach_error")
    assert "Simulated attach failure" in faulty_plugin._attach_error
    
    # on_solver_init should NOT have been called
    assert faulty_plugin.init_called is False


def test_plugin_attach_failure_strict_mode():
    """Test plugin attach failure in strict mode raises exception."""
    
    solver = SolverBase(problem=SimpleProblem(), plugin_strict=True)
    faulty_plugin = FaultyAttachPlugin()
    
    # Should raise RuntimeError
    with pytest.raises(RuntimeError, match="Plugin 'FaultyAttach' attach failed"):
        solver.add_plugin(faulty_plugin)
    
    # Plugin should NOT be registered
    assert solver.plugin_manager.get("FaultyAttach") is None


def test_plugin_lifecycle_skip_failed_attach():
    """Test that plugins with attach failures are skipped during lifecycle."""
    
    solver = SolverBase(problem=SimpleProblem(), plugin_strict=False)
    
    faulty_plugin = FaultyAttachPlugin()
    working_plugin = WorkingPlugin()
    
    # Add both plugins
    solver.add_plugin(faulty_plugin)
    solver.add_plugin(working_plugin)
    
    # Trigger lifecycle events
    solver.plugin_manager.on_solver_init(solver)
    solver.plugin_manager.on_generation_start(0)
    solver.plugin_manager.on_generation_start(1)
    
    # Faulty plugin should have been skipped
    assert faulty_plugin.init_called is False
    
    # Working plugin should have been called
    assert working_plugin.init_called is True
    assert working_plugin.start_count == 2


def test_multiple_plugins_mixed_failures():
    """Test behavior when multiple plugins have mixed success/failure."""
    
    solver = SolverBase(problem=SimpleProblem(), plugin_strict=False)
    
    faulty1 = FaultyAttachPlugin(failure_message="First failure")
    faulty1.name = "FaultyAttach1"  # unique name
    working1 = WorkingPlugin()
    working1.name = "Working1"
    faulty2 = FaultyAttachPlugin(failure_message="Second failure")
    faulty2.name = "FaultyAttach2"  # unique name
    working2 = WorkingPlugin()
    working2.name = "Working2"
    
    solver.add_plugin(faulty1)
    solver.add_plugin(working1)
    solver.add_plugin(faulty2)
    solver.add_plugin(working2)
    
    # Both working plugins should be attached
    assert working1.attached_solver is solver
    assert working2.attached_solver is solver
    
    # Both faulty plugins should be marked as failed
    assert faulty1._attach_failed is True
    assert faulty2._attach_failed is True
    
    # Trigger events
    solver.plugin_manager.on_solver_init(solver)
    
    # Only working plugins should have received init
    assert working1.init_called is True
    assert working2.init_called is True
    assert faulty1.init_called is False
    assert faulty2.init_called is False


def test_plugin_attach_state_inspection():
    """Test that plugin attach state can be inspected."""
    
    solver = SolverBase(problem=SimpleProblem(), plugin_strict=False)
    
    faulty = FaultyAttachPlugin()
    working = WorkingPlugin()
    
    solver.add_plugin(faulty)
    solver.add_plugin(working)
    
    # Inspect all plugins
    all_plugins = solver.plugin_manager.plugins
    assert len(all_plugins) == 2
    
    # Identify failed plugins
    failed_plugins = [p for p in all_plugins if getattr(p, "_attach_failed", False)]
    assert len(failed_plugins) == 1
    assert failed_plugins[0] is faulty
    
    # Identify healthy plugins
    healthy_plugins = [p for p in all_plugins if not getattr(p, "_attach_failed", False)]
    assert len(healthy_plugins) == 1
    assert healthy_plugins[0] is working


def test_plugin_attach_error_message_preserved():
    """Test that attach error message is preserved for debugging."""
    
    solver = SolverBase(problem=SimpleProblem(), plugin_strict=False)
    
    custom_message = "Database connection failed: timeout after 30s"
    faulty = FaultyAttachPlugin(failure_message=custom_message)
    
    solver.add_plugin(faulty)
    
    # Error message should be preserved
    assert hasattr(faulty, "_attach_error")
    assert custom_message in faulty._attach_error


def test_plugin_method_chaining_preserved():
    """Test that add_plugin returns self for method chaining."""
    
    solver = SolverBase(problem=SimpleProblem(), plugin_strict=False)
    
    result = solver.add_plugin(WorkingPlugin())
    
    # Should return solver instance
    assert result is solver
    
    # Should support chaining (use distinct names)
    w1 = WorkingPlugin(); w1.name = "Working1"
    w2 = WorkingPlugin(); w2.name = "Working2"
    solver2 = (SolverBase(problem=SimpleProblem())
               .add_plugin(w1)
               .add_plugin(w2))
    
    assert len(solver2.plugin_manager.plugins) == 2


def test_plugin_strict_mode_prevents_registration():
    """Test that strict mode prevents failed plugins from being registered."""
    
    solver = SolverBase(problem=SimpleProblem(), plugin_strict=True)
    
    faulty = FaultyAttachPlugin()
    
    try:
        solver.add_plugin(faulty)
    except RuntimeError:
        pass
    
    # Plugin should not be in registry
    assert solver.plugin_manager.get("FaultyAttach") is None
    assert len(solver.plugin_manager.plugins) == 0
    
    # Add a working plugin afterwards
    working = WorkingPlugin()
    solver.add_plugin(working)
    
    assert len(solver.plugin_manager.plugins) == 1
    assert solver.plugin_manager.get("Working") is working


def test_plugin_soft_mode_allows_inspection():
    """Test that soft mode allows inspection of failed plugins."""
    
    solver = SolverBase(problem=SimpleProblem(), plugin_strict=False)
    
    faulty = FaultyAttachPlugin()
    solver.add_plugin(faulty)
    
    # Plugin should still be retrievable
    retrieved = solver.plugin_manager.get("FaultyAttach")
    assert retrieved is faulty
    
    # Can inspect its failure state
    assert retrieved._attach_failed is True
    
    # Can remove it if needed
    solver.plugin_manager.unregister("FaultyAttach")
    assert solver.plugin_manager.get("FaultyAttach") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
