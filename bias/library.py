"""
Compatibility bias library helpers.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Type
import inspect

from .core.base import AlgorithmicBias, DomainBias
from .core.manager import UniversalBiasManager
from . import algorithmic as _algorithmic
from . import domain as _domain


class _GenericAlgorithmicBias(AlgorithmicBias):
    """Fallback bias used when a specific algorithmic class is unavailable."""
    context_requires = ()
    requires_metrics = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Reads context fields: metrics; outputs scalar bias only."



    def compute(self, x, context) -> float:
        return 0.0


class _GenericDomainBias(DomainBias):
    """Fallback bias used when a specific domain class is unavailable."""
    context_requires = ("problem_data",)
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Reads context fields: problem_data; outputs scalar bias only."



    def compute(self, x, context) -> float:
        return 0.0


def _collect_biases(module, base_class: Type) -> Dict[str, Type]:
    biases: Dict[str, Type] = {}
    for name, obj in inspect.getmembers(module, inspect.isclass):
        if issubclass(obj, base_class) and obj is not base_class:
            biases[name] = obj
    return biases


def _filter_kwargs(target: Type, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    if not kwargs:
        return {}
    params = inspect.signature(target.__init__).parameters
    return {name: value for name, value in kwargs.items() if name in params and name != "self"}


class BiasFactory:
    """Minimal factory for docs/examples."""

    _algorithmic_biases: Optional[Dict[str, Type[AlgorithmicBias]]] = None
    _domain_biases: Optional[Dict[str, Type[DomainBias]]] = None

    _algorithmic_aliases = {
        "diversity_promotion": "DiversityBias",
        "balanced_exploration": "DiversityBias",
        "fast_convergence": "ConvergenceBias",
        "precision_search": "PrecisionBias",
    }
    _domain_aliases = {
        "financial_optimization": "PreferenceBias",
        "portfolio_optimization": "PreferenceBias",
        "supply_chain": "ConstraintBias",
    }

    @classmethod
    def _ensure_registry(cls) -> None:
        if cls._algorithmic_biases is None:
            cls._algorithmic_biases = _collect_biases(_algorithmic, AlgorithmicBias)
        if cls._domain_biases is None:
            cls._domain_biases = _collect_biases(_domain, DomainBias)

    @classmethod
    def list_available_algorithmic_biases(cls) -> Dict[str, Dict[str, str]]:
        cls._ensure_registry()
        return {
            name: {"description": inspect.getdoc(bias) or ""}
            for name, bias in cls._algorithmic_biases.items()
        }

    @classmethod
    def list_available_domain_biases(cls) -> Dict[str, Dict[str, str]]:
        cls._ensure_registry()
        return {
            name: {"description": inspect.getdoc(bias) or ""}
            for name, bias in cls._domain_biases.items()
        }

    @classmethod
    def create_algorithmic_bias(cls, name: str, **kwargs) -> AlgorithmicBias:
        cls._ensure_registry()
        resolved = cls._algorithmic_aliases.get(name, name)
        bias_class = cls._algorithmic_biases.get(resolved)
        if bias_class is None:
            weight = kwargs.pop("weight", 1.0)
            description = kwargs.pop("description", "")
            return _GenericAlgorithmicBias(name=name, weight=weight, description=description)
        filtered = _filter_kwargs(bias_class, kwargs)
        return bias_class(**filtered)

    @classmethod
    def create_domain_bias(cls, name: str, **kwargs) -> DomainBias:
        cls._ensure_registry()
        resolved = cls._domain_aliases.get(name, name)
        bias_class = cls._domain_biases.get(resolved)
        if bias_class is None:
            weight = kwargs.pop("weight", 1.0)
            description = kwargs.pop("description", "")
            return _GenericDomainBias(name=name, weight=weight, description=description)
        filtered = _filter_kwargs(bias_class, kwargs)
        return bias_class(**filtered)


class BiasComposer:
    """Small helper to build a UniversalBiasManager from configs."""

    def __init__(self) -> None:
        self._manager = UniversalBiasManager()

    def add_algorithmic_bias_from_config(self, name: str, **kwargs) -> AlgorithmicBias:
        bias = BiasFactory.create_algorithmic_bias(name, **kwargs)
        self._manager.add_algorithmic_bias(bias)
        return bias

    def add_domain_bias_from_config(self, name: str, **kwargs) -> DomainBias:
        bias = BiasFactory.create_domain_bias(name, **kwargs)
        self._manager.add_domain_bias(bias)
        return bias

    def build(self) -> UniversalBiasManager:
        return self._manager


def create_bias_manager_from_template(
    template_name: str,
    customizations: Optional[Dict[str, Any]] = None
) -> UniversalBiasManager:
    """Create a simple bias manager from a template name."""
    manager = UniversalBiasManager()
    template = (template_name or "").lower().strip()

    if template in {"basic_engineering", "engineering"}:
        manager.add_algorithmic_bias(BiasFactory.create_algorithmic_bias("DiversityBias", weight=0.1))
        manager.add_algorithmic_bias(BiasFactory.create_algorithmic_bias("ConvergenceBias", weight=0.05))
        manager.add_domain_bias(BiasFactory.create_domain_bias("ConstraintBias", weight=1.0))
    elif template in {"financial_optimization", "finance"}:
        manager.add_algorithmic_bias(BiasFactory.create_algorithmic_bias("ConvergenceBias", weight=0.1))
        manager.add_domain_bias(BiasFactory.create_domain_bias("PreferenceBias", weight=1.0))
    elif template in {"machine_learning", "ml"}:
        manager.add_algorithmic_bias(BiasFactory.create_algorithmic_bias("PrecisionBias", weight=0.1))
        manager.add_algorithmic_bias(BiasFactory.create_algorithmic_bias("DiversityBias", weight=0.1))
    else:
        manager.add_algorithmic_bias(BiasFactory.create_algorithmic_bias("DiversityBias", weight=0.1))

    if customizations:
        for bias in manager.algorithmic_manager.biases.values():
            if "algorithmic_weight" in customizations:
                bias.weight = customizations["algorithmic_weight"]
        for bias in manager.domain_manager.biases.values():
            if "domain_weight" in customizations:
                bias.weight = customizations["domain_weight"]

    return manager


def quick_engineering_bias(**kwargs) -> UniversalBiasManager:
    return create_bias_manager_from_template("engineering", customizations=kwargs)


def quick_ml_bias(**kwargs) -> UniversalBiasManager:
    return create_bias_manager_from_template("machine_learning", customizations=kwargs)


def quick_financial_bias(**kwargs) -> UniversalBiasManager:
    return create_bias_manager_from_template("financial_optimization", customizations=kwargs)


__all__ = [
    "BiasFactory",
    "BiasComposer",
    "create_bias_manager_from_template",
    "quick_engineering_bias",
    "quick_ml_bias",
    "quick_financial_bias",
]
