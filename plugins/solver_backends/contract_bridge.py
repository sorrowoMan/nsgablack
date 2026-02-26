from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

from ..base import Plugin


TransformFn = Callable[[Any], Any]


@dataclass
class BridgeRule:
    source_key: str
    target_key: str
    target_layer: str = "L1"
    transform: Optional[TransformFn] = None


class ContractBridgePlugin(Plugin):
    """Map inner-result fields across layer contracts."""

    is_algorithmic = False
    context_requires = ()
    context_provides = ()
    context_mutates = ("metadata.layers",)
    context_cache = ()
    context_notes = (
        "Consumes on_inner_result packets and writes mapped keys into "
        "solver-level layer contexts.",
    )

    def __init__(
        self,
        name: str = "contract_bridge",
        *,
        rules: Optional[Sequence[BridgeRule]] = None,
        allow_overwrite: bool = True,
        priority: int = 10,
    ) -> None:
        super().__init__(name=name, priority=priority)
        self.rules: List[BridgeRule] = list(rules or [])
        self.allow_overwrite = bool(allow_overwrite)
        self.stats: Dict[str, float] = {"packets": 0.0, "writes": 0.0, "dropped": 0.0}

    def _ensure_layers(self, solver) -> Dict[str, Dict[str, Any]]:
        layers = getattr(solver, "_layer_contexts", None)
        if not isinstance(layers, dict):
            layers = {}
            setattr(solver, "_layer_contexts", layers)
        return layers

    def _ensure_log(self, solver) -> List[Dict[str, Any]]:
        log = getattr(solver, "_bridge_log", None)
        if not isinstance(log, list):
            log = []
            setattr(solver, "_bridge_log", log)
        return log

    def on_inner_result(self, solver, packet: Mapping[str, Any]):
        if not isinstance(packet, Mapping):
            return None
        self.stats["packets"] += 1.0

        layers = self._ensure_layers(solver)
        bridge_log = self._ensure_log(solver)
        result = packet.get("result", {})
        if not isinstance(result, Mapping):
            result = {}
        source_layer = str(packet.get("source_layer", "L2"))

        writes: List[Dict[str, Any]] = []
        if self.rules:
            for rule in self.rules:
                if rule.source_key not in result:
                    continue
                value = result.get(rule.source_key)
                if callable(rule.transform):
                    try:
                        value = rule.transform(value)
                    except Exception:
                        self.stats["dropped"] += 1.0
                        continue
                target_layer = str(rule.target_layer)
                layer_ctx = layers.setdefault(target_layer, {})
                if (not self.allow_overwrite) and (rule.target_key in layer_ctx):
                    self.stats["dropped"] += 1.0
                    continue
                layer_ctx[rule.target_key] = value
                self.stats["writes"] += 1.0
                writes.append(
                    {
                        "source_layer": source_layer,
                        "target_layer": target_layer,
                        "source_key": rule.source_key,
                        "target_key": rule.target_key,
                    }
                )
        else:
            target_layer = str(packet.get("target_layer", "L1"))
            layer_ctx = layers.setdefault(target_layer, {})
            layer_ctx[f"{source_layer}.last_result"] = dict(result)
            self.stats["writes"] += 1.0
            writes.append(
                {
                    "source_layer": source_layer,
                    "target_layer": target_layer,
                    "source_key": "*",
                    "target_key": f"{source_layer}.last_result",
                }
            )

        if writes:
            bridge_log.append(
                {
                    "generation": int(packet.get("generation", 0)),
                    "candidate_id": int(packet.get("candidate_id", 0)),
                    "writes": writes,
                }
            )
        return None

    def get_report(self) -> Optional[Dict[str, Any]]:
        out = super().get_report() or {}
        out["stats"] = dict(self.stats)
        out["rules"] = [
            {
                "source_key": r.source_key,
                "target_key": r.target_key,
                "target_layer": r.target_layer,
                "has_transform": bool(callable(r.transform)),
            }
            for r in self.rules
        ]
        return out
