from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Mapping

if TYPE_CHECKING:
    from ..backend_contract import BackendSolveRequest

TemplateSolveFn = Callable[["BackendSolveRequest", Any, Mapping[str, Any]], Mapping[str, Any]]
