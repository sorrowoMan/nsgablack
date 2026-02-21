"""
nsgablack: A decomposed optimization system with pipelines, biases, adapters, plugins

Core Focus:
- Representation Pipeline: Flexible encoding, initialization, mutation, and repair
- Bias System: Modular integration of domain knowledge and algorithmic guidance
"""

from __future__ import annotations

from pathlib import Path
from pkgutil import extend_path

# Allow this package to discover the existing top-level modules (core/, bias/, etc.)
__path__ = extend_path(__path__, __name__)
_PARENT = Path(__file__).resolve().parent.parent
if str(_PARENT) not in __path__:
    __path__.append(str(_PARENT))

# Version is managed by setuptools_scm (pyproject.toml: dynamic = ["version"]).
# For editable installs, importlib.metadata provides the resolved version.
try:
    from importlib.metadata import PackageNotFoundError, version as _pkg_version

    try:
        __version__ = _pkg_version("nsgablack")
    except PackageNotFoundError:  # pragma: no cover
        __version__ = "0+unknown"
except Exception:  # pragma: no cover
    __version__ = "0+unknown"

__author__ = "SorrowoMan"
__email__ = "sorrowo@foxmail.com"

from .catalog import (
    CatalogEntry,
    get_catalog,
    search_catalog,
    list_catalog,
    get_entry,
    reload_catalog,
)

__all__ = [
    # Version info
    "__version__",

    # Discoverability (recommended entry point)
    "CatalogEntry",
    "get_catalog",
    "search_catalog",
    "list_catalog",
    "get_entry",
    "reload_catalog",
]

# Package metadata
_PACKAGE_INFO = {
    "name": "nsgablack",
    "description": "A decomposed optimization system with pipelines, biases, adapters, plugins",
    "long_description": """
    nsgablack is a powerful multi-objective optimization framework featuring:

    CORE INNOVATIONS:
    - Representation Pipeline: Flexible encoding, initialization, mutation, and repair
    - Bias System: Modular integration of domain knowledge and algorithmic guidance

    ADDITIONAL FEATURES:
    - Adapter ecosystem (VNS / SA / MOEA-D / multi-strategy cooperation)
    - Parallel evaluation utilities
    - Benchmark harness (unified experiment protocol)
    - Memory optimization + visualization tools

    The framework excels at handling complex optimization problems through:
    1. Customizable representation for integers, permutations, binary, graphs, matrices
    2. Algorithmic biases (diversity, convergence, exploration)
    3. Domain biases (constraints, preferences, objectives)
    """,
    "url": "https://github.com/sorrowoMan/nsgablack",
    "author": "SorrowoMan",
    "author_email": "sorrowo@foxmail.com",
    "license": "MIT",
    "python_requires": ">=3.8",
    "classifiers": [
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Scientific/Engineering :: Mathematics",
    ],
    "keywords": [
        "optimization",
        "multi-objective",
        "nsga-ii",
        "representation-pipeline",
        "bias-system",
        "evolutionary-algorithms",
        "domain-knowledge",
        "integer-optimization",
        "permutation-optimization",
    ],
}


def get_version():
    """Get package version."""
    return __version__


def get_package_info():
    """Get package metadata."""
    return _PACKAGE_INFO.copy()


def get_available_features():
    """Get information about available optional features."""

    def _has_mod(mod: str) -> bool:
        try:
            __import__(mod)
            return True
        except Exception:
            return False

    return {
        "representation_pipeline": True,  # CORE feature
        "bias_system": _has_mod("nsgablack.bias"),  # CORE feature
        "machine_learning": False,  # out of scope for the core promise
        "parallel_computation": True,
        "visualization": _has_mod("matplotlib"),
        "memory_optimization": True,
    }
