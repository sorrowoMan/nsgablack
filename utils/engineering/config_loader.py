"""Configuration loading and validation helpers."""

from __future__ import annotations

import json
from dataclasses import fields, is_dataclass, replace
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple, Union

try:
    import tomllib  # Python 3.11+
except Exception:  # pragma: no cover - optional dependency
    tomllib = None


ConfigSource = Union[str, Path, Mapping[str, Any]]


class ConfigError(ValueError):
    """Raised when configuration cannot be parsed or validated."""


def load_config(source: Optional[ConfigSource], *, allow_missing: bool = False) -> Dict[str, Any]:
    """Load configuration from dict or JSON/TOML/YAML file."""
    if source is None:
        return {}

    if isinstance(source, Mapping):
        return dict(source)

    path = Path(source)
    if not path.exists():
        if allow_missing:
            return {}
        raise ConfigError(f"Config file not found: {path}")

    suffix = path.suffix.lower()
    if suffix in {".json"}:
        return json.loads(path.read_text(encoding="utf-8"))
    if suffix in {".toml"}:
        if tomllib is None:
            try:  # pragma: no cover - optional dependency
                import tomli as tomllib_fallback
            except Exception as exc:  # pragma: no cover
                raise ConfigError("TOML support requires Python 3.11+ or tomli") from exc
            return tomllib_fallback.loads(path.read_text(encoding="utf-8"))
        return tomllib.loads(path.read_text(encoding="utf-8"))
    if suffix in {".yml", ".yaml"}:
        try:  # pragma: no cover - optional dependency
            import yaml
        except Exception as exc:  # pragma: no cover
            raise ConfigError("YAML support requires PyYAML") from exc
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    raise ConfigError(f"Unsupported config format: {suffix}")


def merge_dicts(base: Mapping[str, Any], override: Mapping[str, Any]) -> Dict[str, Any]:
    """Deep merge dictionaries (override wins)."""
    merged: Dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def select_section(config: Mapping[str, Any], section: Optional[str]) -> Dict[str, Any]:
    """Return a config subsection if present."""
    if section and isinstance(config.get(section), Mapping):
        return dict(config[section])
    return dict(config)


def apply_config(
    target: Any,
    config: Optional[ConfigSource],
    *,
    allow_unknown: bool = False,
    section: Optional[str] = None,
) -> Iterable[str]:
    """Apply a config mapping to an object by setting matching attributes."""
    config_data = load_config(config)
    config_data = select_section(config_data, section)
    unknown = []
    for key, value in config_data.items():
        if hasattr(target, key):
            current = getattr(target, key)
            if isinstance(current, Mapping) and isinstance(value, Mapping):
                setattr(target, key, merge_dicts(current, value))
            else:
                setattr(target, key, value)
        else:
            unknown.append(key)
    if unknown and not allow_unknown:
        raise ConfigError(f"Unknown config keys: {', '.join(sorted(unknown))}")
    return unknown


def build_dataclass_config(
    dataclass_type: Any,
    config: Optional[ConfigSource],
    *,
    base: Optional[Any] = None,
    strict: bool = False,
) -> Tuple[Any, Iterable[str]]:
    """Build a dataclass instance from a config mapping."""
    if base is not None and not is_dataclass(base):
        raise ConfigError("Base config must be a dataclass instance")
    if base is None and not is_dataclass(dataclass_type):
        raise ConfigError("dataclass_type must be a dataclass")

    config_data = load_config(config)
    instance = replace(base) if base is not None else dataclass_type()

    valid_fields = {field.name for field in fields(instance)}
    unknown = [key for key in config_data.keys() if key not in valid_fields]
    if unknown and strict:
        raise ConfigError(f"Unknown config keys: {', '.join(sorted(unknown))}")

    for key in valid_fields:
        if key in config_data:
            setattr(instance, key, config_data[key])

    return instance, unknown
