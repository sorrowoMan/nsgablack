"""Temporary compatibility bridges for deprecated public APIs."""

from .deprecation import warn_deprecated
from .elite_retention import BasicElitePlugin, HistoricalElitePlugin

__all__ = ["warn_deprecated", "BasicElitePlugin", "HistoricalElitePlugin"]
