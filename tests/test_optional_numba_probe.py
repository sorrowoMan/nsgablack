from __future__ import annotations

import builtins

from nsgablack.core.interfaces import has_numba


def test_has_numba_handles_non_importerror_failures(monkeypatch):
    original_import = builtins.__import__

    def broken_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "numba":
            raise RuntimeError("simulated numba import failure")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", broken_import)
    assert has_numba() is False
