"""Call-local pool donor declarations for ordinary change functions.

These scopes carry no shared context keys and own no runtime state. A task's
frozen input references remain usable, while additional named pools and the
mother pool require an explicit declaration at every enclosing task boundary.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from nsgablack.core.state.solution_pool import SolutionRef


@dataclass(frozen=True)
class ChangeAccess:
    seed_refs: tuple[SolutionRef, ...] = ()
    subpools: tuple[str, ...] = ()
    allow_main: bool = False

    def __post_init__(self):
        if (not isinstance(self.seed_refs, tuple)
                or any(not isinstance(ref, SolutionRef) for ref in self.seed_refs)):
            raise TypeError("change access seed_refs must be a tuple of SolutionRef")
        if (not isinstance(self.subpools, tuple)
                or any(not isinstance(name, str) or not name.strip() for name in self.subpools)
                or len(set(self.subpools)) != len(self.subpools)):
            raise ValueError("change access subpools must be distinct nonempty names")
        if type(self.allow_main) is not bool:
            raise TypeError("change access allow_main must be a boolean")


_change_access: ContextVar[ChangeAccess | None] = ContextVar("nsgablack.change_access", default=None)


def current_change_access() -> ChangeAccess | None:
    """Return this synchronous proposal call's effective donor declaration."""
    return _change_access.get()


@contextmanager
def scoped_change_access(seed_refs, *, subpools=(), allow_main=False):
    """Restrict nested donor names without losing their exact frozen seeds.

    Inner tasks may introduce their own explicit input references. This does
    not grant access to the rest of those references' pools or to other views.
    Named donors and mother-pool access must be allowed by every enclosing
    scope. The token is restored even if proposal generation raises.
    """
    declared = ChangeAccess(tuple(dict.fromkeys(seed_refs)), subpools, allow_main)
    parent = current_change_access()
    if parent is not None:
        declared = ChangeAccess(
            tuple(dict.fromkeys((*parent.seed_refs, *declared.seed_refs))),
            tuple(name for name in declared.subpools if name in parent.subpools),
            parent.allow_main and declared.allow_main,
        )
    token = _change_access.set(declared)
    try:
        yield declared
    finally:
        _change_access.reset(token)


__all__ = ["ChangeAccess", "current_change_access", "scoped_change_access"]
