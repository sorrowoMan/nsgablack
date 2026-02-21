"""
偏置系统便利函数

提供快速创建和配置偏置系统的辅助函数。
"""

from typing import Dict, Any, Optional
from ..core.manager import UniversalBiasManager


def create_universal_bias_manager():
    """
    Create a pre-configured universal bias manager with common biases.

    Returns:
        UniversalBiasManager: Configured bias manager
    """
    from .. import (
        DiversityBias,
        ConvergenceBias,
        PrecisionBias,
        ConstraintBias
    )

    manager = UniversalBiasManager()

    # Add common algorithmic biases
    try:
        manager.add_algorithmic_bias(DiversityBias(weight=0.1))
        manager.add_algorithmic_bias(ConvergenceBias(weight=0.05))
        manager.add_algorithmic_bias(PrecisionBias(weight=0.05))
    except Exception as e:
        print(f"Warning: Could not add standard biases: {e}")

    # Add basic domain bias (users can add specific constraints)
    try:
        manager.add_domain_bias(ConstraintBias(weight=1.0))
    except Exception as e:
        print(f"Warning: Could not add constraint bias: {e}")

    return manager


def quick_bias_setup(
    problem_type: str = "general",
    add_constraints: bool = True,
    add_adaptive: bool = True
):
    """
    Quick bias setup for different problem types.

    Args:
        problem_type: Type of problem ('general', 'engineering', 'scheduling', 'constrained')
        add_constraints: Whether to add constraint bias
        add_adaptive: Whether to add adaptive manager

    Returns:
        UniversalBiasManager: Configured bias manager
    """
    from .. import (
        DiversityBias,
        ConvergenceBias,
        ConstraintBias,
        AdaptiveDiversityBias,
        PrecisionBias,
        EngineeringPrecisionBias,
        EngineeringConstraintBias
    )

    manager = UniversalBiasManager()

    # Problem-specific bias configurations
    try:
        if problem_type == "general":
            manager.add_algorithmic_bias(DiversityBias(weight=0.1))
            manager.add_algorithmic_bias(ConvergenceBias(weight=0.05))

        elif problem_type == "engineering":
            # 使用专门的工程应用偏置
            if EngineeringPrecisionBias is not None:
                manager.add_algorithmic_bias(EngineeringPrecisionBias(weight=0.15))
            elif PrecisionBias is not None:
                manager.add_algorithmic_bias(PrecisionBias(weight=0.15))

            if AdaptiveDiversityBias is not None:
                manager.add_algorithmic_bias(AdaptiveDiversityBias(weight=0.1))

            # 添加工程约束偏置（强制性的）
            if EngineeringConstraintBias is not None:
                manager.add_domain_bias(EngineeringConstraintBias(safety_factor=1.5))
            elif ConstraintBias is not None:
                manager.add_domain_bias(ConstraintBias(weight=1.0, penalty_factor=15.0))

        elif problem_type == "scheduling":
            manager.add_algorithmic_bias(DiversityBias(weight=0.15))
            manager.add_algorithmic_bias(PrecisionBias(weight=0.15))

        elif problem_type == "constrained":
            if AdaptiveDiversityBias is not None:
                manager.add_algorithmic_bias(AdaptiveDiversityBias(weight=0.2))

        # Add constraint bias if requested
        if add_constraints and ConstraintBias is not None:
            manager.add_domain_bias(ConstraintBias(weight=0.5, penalty_factor=20.0))

    except Exception as e:
        print(f"Warning: Could not configure biases for problem type '{problem_type}': {e}")

    return manager


def get_bias_system_info() -> dict:
    """
    Get information about the bias system.

    Returns:
        dict: System information
    """
    from .. import __version__, get_bias_registry, NEW_STRUCTURE_AVAILABLE

    info = {
        'version': __version__,
        'new_structure_available': NEW_STRUCTURE_AVAILABLE,
    }

    if NEW_STRUCTURE_AVAILABLE:
        try:
            registry = get_bias_registry()
            info.update({
                'algorithmic_biases': registry.list_algorithmic_biases(),
                'domain_biases': registry.list_domain_biases(),
                'bias_factories': registry.list_bias_factories(),
                'categories': registry.list_categories()
            })
        except Exception as e:
            info['registry_error'] = str(e)

    return info
