from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple


@dataclass(frozen=True)
class CatalogComponentContract:
    key: str
    kind: str
    title: str
    import_path: str
    summary: str
    tags: Tuple[str, ...]
    companions: Tuple[str, ...]
    source_scope: str
    source_hash: str


@dataclass(frozen=True)
class ContextContract:
    component_key: str
    requires: Tuple[str, ...]
    provides: Tuple[str, ...]
    mutates: Tuple[str, ...]
    cache: Tuple[str, ...]
    notes: Tuple[str, ...]


@dataclass(frozen=True)
class UsageContract:
    component_key: str
    use_when: Tuple[str, ...]
    minimal_wiring: Tuple[str, ...]
    required_companions: Tuple[str, ...]
    config_keys: Tuple[str, ...]
    example_entry: str


@dataclass(frozen=True)
class ParamContract:
    component_key: str
    name: str
    type: str
    default: str
    required: bool
    desc: str
    source: str
    order_index: int


@dataclass(frozen=True)
class MethodContract:
    component_key: str
    name: str
    required: bool
    implemented: bool
    signature: str
    origin: str


@dataclass(frozen=True)
class HealthContract:
    component_key: str
    import_ok: bool
    context_ok: bool
    methods_ok: bool
    params_ok: bool
    issues: Tuple[str, ...]


@dataclass(frozen=True)
class CatalogBundle:
    components: Sequence[CatalogComponentContract]
    contexts: Sequence[ContextContract]
    usages: Sequence[UsageContract]
    params: Sequence[ParamContract]
    methods: Sequence[MethodContract]
    health: Sequence[HealthContract]


@dataclass(frozen=True)
class ApiIndexEntry:
    profile: str
    module: str
    class_name: str
    method_name: str
    purpose: str
    usage: str
    lineno: int


@dataclass(frozen=True)
class ApiIndexMeta:
    profile: str
    file_count: int
    component_count: int
    method_count: int


@dataclass(frozen=True)
class ApiDocEntry:
    profile: str
    module: str
    class_name: str
    method_name: str
    params_json: str
    boundaries: str
    side_effects: str
    lifecycle: str
    notes: str
    auto_fields: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ApiDocGap:
    profile: str
    module: str
    class_name: str
    method_name: str
    missing_fields: Tuple[str, ...]
