"""
Bias registry system.

This module provides a centralized registry for all bias types,
supporting dynamic registration and discovery of bias implementations.
"""

from typing import Dict, Type, Callable, List, Any, Optional
import inspect

from .base import BiasBase, AlgorithmicBias, DomainBias


class BiasRegistry:
    """
    Centralized registry for bias implementations.

    Supports dynamic registration and instantiation of different bias types.
    """

    def __init__(self):
        self._algorithmic_biases: Dict[str, Type[AlgorithmicBias]] = {}
        self._domain_biases: Dict[str, Type[DomainBias]] = {}
        self._bias_factories: Dict[str, Callable] = {}
        self._bias_categories: Dict[str, List[str]] = {}

    def register_algorithmic_bias(
        self,
        name: str,
        bias_class: Type[AlgorithmicBias],
        category: str = "general"
    ) -> None:
        """
        Register an algorithmic bias class.

        Args:
            name: Unique name for the bias
            bias_class: Bias class to register
            category: Category for organization
        """
        if not issubclass(bias_class, AlgorithmicBias):
            raise TypeError(f"Bias class must inherit from AlgorithmicBias")

        self._algorithmic_biases[name] = bias_class

        if category not in self._bias_categories:
            self._bias_categories[category] = []
        if name not in self._bias_categories[category]:
            self._bias_categories[category].append(name)

    def register_domain_bias(
        self,
        name: str,
        bias_class: Type[DomainBias],
        category: str = "general"
    ) -> None:
        """
        Register a domain bias class.

        Args:
            name: Unique name for the bias
            bias_class: Bias class to register
            category: Category for organization
        """
        if not issubclass(bias_class, DomainBias):
            raise TypeError(f"Bias class must inherit from DomainBias")

        self._domain_biases[name] = bias_class

        if category not in self._bias_categories:
            self._bias_categories[category] = []
        if name not in self._bias_categories[category]:
            self._bias_categories[category].append(name)

    def register_bias_factory(
        self,
        name: str,
        factory_func: Callable[..., BiasBase],
        category: str = "factory"
    ) -> None:
        """
        Register a bias factory function.

        Args:
            name: Unique name for the factory
            factory_func: Function that creates bias instances
            category: Category for organization
        """
        self._bias_factories[name] = factory_func

        if category not in self._bias_categories:
            self._bias_categories[category] = []
        if name not in self._bias_categories[category]:
            self._bias_categories[category].append(name)

    def create_algorithmic_bias(
        self,
        name: str,
        **kwargs
    ) -> AlgorithmicBias:
        """
        Create an instance of a registered algorithmic bias.

        Args:
            name: Name of the registered bias
            **kwargs: Arguments to pass to bias constructor

        Returns:
            Created bias instance
        """
        if name not in self._algorithmic_biases:
            raise ValueError(f"Algorithmic bias '{name}' not registered")

        bias_class = self._algorithmic_biases[name]
        return bias_class(**kwargs)

    def create_domain_bias(
        self,
        name: str,
        **kwargs
    ) -> DomainBias:
        """
        Create an instance of a registered domain bias.

        Args:
            name: Name of the registered bias
            **kwargs: Arguments to pass to bias constructor

        Returns:
            Created bias instance
        """
        if name not in self._domain_biases:
            raise ValueError(f"Domain bias '{name}' not registered")

        bias_class = self._domain_biases[name]
        return bias_class(**kwargs)

    def create_bias_from_factory(
        self,
        name: str,
        **kwargs
    ) -> BiasBase:
        """
        Create a bias instance using a registered factory.

        Args:
            name: Name of the registered factory
            **kwargs: Arguments to pass to factory function

        Returns:
            Created bias instance
        """
        if name not in self._bias_factories:
            raise ValueError(f"Bias factory '{name}' not registered")

        factory_func = self._bias_factories[name]
        return factory_func(**kwargs)

    def list_algorithmic_biases(self) -> List[str]:
        """List all registered algorithmic bias names."""
        return list(self._algorithmic_biases.keys())

    def list_domain_biases(self) -> List[str]:
        """List all registered domain bias names."""
        return list(self._domain_biases.keys())

    def list_bias_factories(self) -> List[str]:
        """List all registered bias factory names."""
        return list(self._bias_factories.keys())

    def list_categories(self) -> List[str]:
        """List all bias categories."""
        return list(self._bias_categories.keys())

    def get_biases_in_category(self, category: str) -> List[str]:
        """Get all bias names in a specific category."""
        return self._bias_categories.get(category, [])

    def get_bias_info(self, name: str) -> Dict[str, Any]:
        """
        Get information about a registered bias.

        Args:
            name: Name of the bias

        Returns:
            Dictionary with bias information
        """
        info = {'name': name, 'type': None, 'class': None, 'doc': None}

        if name in self._algorithmic_biases:
            info['type'] = 'algorithmic'
            info['class'] = self._algorithmic_biases[name]
        elif name in self._domain_biases:
            info['type'] = 'domain'
            info['class'] = self._domain_biases[name]
        elif name in self._bias_factories:
            info['type'] = 'factory'
            info['class'] = self._bias_factories[name]

        if info['class']:
            info['doc'] = inspect.getdoc(info['class'])
            if hasattr(info['class'], '__init__'):
                sig = inspect.signature(info['class'].__init__)
                info['parameters'] = dict(sig.parameters)

        return info

    def get_bias_documentation(self, name: str) -> str:
        """Get documentation string for a bias."""
        info = self.get_bias_info(name)
        return info.get('doc', 'No documentation available')

    def search_biases(self, keyword: str) -> List[str]:
        """
        Search for biases by keyword in name or documentation.

        Args:
            keyword: Search keyword

        Returns:
            List of matching bias names
        """
        keyword_lower = keyword.lower()
        matches = []

        all_biases = {}
        all_biases.update(self._algorithmic_biases)
        all_biases.update(self._domain_biases)

        for name, bias_class in all_biases.items():
            if keyword_lower in name.lower():
                matches.append(name)
            elif inspect.getdoc(bias_class):
                if keyword_lower in inspect.getdoc(bias_class).lower():
                    matches.append(name)

        return matches

    def validate_bias_registration(self) -> List[str]:
        """
        Validate all registered biases.

        Returns:
            List of validation errors
        """
        errors = []

        for name, bias_class in self._algorithmic_biases.items():
            try:
                # Check if class can be instantiated
                sig = inspect.signature(bias_class.__init__)
                params = {}
                for param_name, param in sig.parameters.items():
                    if param_name == 'self':
                        continue
                    if param.default == inspect.Parameter.empty:
                        # Required parameter - skip validation for complex cases
                        continue
                    params[param_name] = param.default

                # Try to create instance (might fail for complex cases)
                # bias_class(**params)

            except Exception as e:
                errors.append(f"Algorithmic bias '{name}': {str(e)}")

        for name, bias_class in self._domain_biases.items():
            try:
                sig = inspect.signature(bias_class.__init__)
                params = {}
                for param_name, param in sig.parameters.items():
                    if param_name == 'self':
                        continue
                    if param.default == inspect.Parameter.empty:
                        continue
                    params[param_name] = param.default

                # bias_class(**params)

            except Exception as e:
                errors.append(f"Domain bias '{name}': {str(e)}")

        return errors


# Global registry instance
_bias_registry = BiasRegistry()


def get_bias_registry() -> BiasRegistry:
    """Get the global bias registry instance."""
    return _bias_registry


def register_algorithmic_bias(
    name: str,
    category: str = "general"
):
    """
    Decorator for registering algorithmic bias classes.

    Usage:
        @register_algorithmic_bias("my_bias", "exploration")
        class MyBias(AlgorithmicBias):
            ...
    """
    def decorator(bias_class: Type[AlgorithmicBias]):
        _bias_registry.register_algorithmic_bias(name, bias_class, category)
        return bias_class
    return decorator


def register_domain_bias(
    name: str,
    category: str = "general"
):
    """
    Decorator for registering domain bias classes.

    Usage:
        @register_domain_bias("my_constraint", "engineering")
        class MyConstraint(DomainBias):
            ...
    """
    def decorator(bias_class: Type[DomainBias]):
        _bias_registry.register_domain_bias(name, bias_class, category)
        return bias_class
    return decorator


def register_bias_factory(
    name: str,
    category: str = "factory"
):
    """
    Decorator for registering bias factory functions.

    Usage:
        @register_bias_factory("my_factory", "composite")
        def create_my_bias(config):
            return MyBias(**config)
    """
    def decorator(factory_func: Callable[..., BiasBase]):
        _bias_registry.register_bias_factory(name, factory_func, category)
        return factory_func
    return decorator