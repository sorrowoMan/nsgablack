"""
CLI signal provider for dynamic switching.

Usage:
    type lines like:
      weather=bad
      risk=0.8
      {"weather": "good", "risk": 0.2}
"""

from __future__ import annotations

import json
import threading
from typing import Any, Dict

from .switch import SignalProviderBase


class CLISignalProvider(SignalProviderBase):
    """
    Read signals from stdin in a background thread.

    Input formats:
    - JSON object: {"key": "value", "x": 1}
    - key=value pairs (one or many in a line): weather=bad risk=0.8
    """

    def __init__(self) -> None:
        self._latest: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def read(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._latest)

    def _loop(self) -> None:
        while True:
            try:
                line = input().strip()
            except Exception:
                break
            if not line:
                continue
            payload = self._parse_line(line)
            if not payload:
                continue
            with self._lock:
                self._latest.update(payload)

    def _parse_line(self, line: str) -> Dict[str, Any]:
        if line.startswith("{") and line.endswith("}"):
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    return obj
            except Exception:
                return {}
            return {}
        out: Dict[str, Any] = {}
        for part in line.split():
            if "=" not in part:
                continue
            k, v = part.split("=", 1)
            k = k.strip()
            v = v.strip()
            if not k:
                continue
            # try to parse numbers/bool/null
            val: Any = v
            if v.lower() in ("true", "false"):
                val = v.lower() == "true"
            elif v.lower() in ("null", "none"):
                val = None
            else:
                try:
                    if "." in v:
                        val = float(v)
                    else:
                        val = int(v)
                except Exception:
                    val = v
            out[k] = val
        return out
