"""Canonical pipeline entry for ETF lane outer search."""

from .representation import build_representation_pipeline


def build_pipeline(*args, **kwargs):
    """Build the Case representation pipeline."""

    return build_representation_pipeline(*args, **kwargs)


__all__ = ["build_pipeline", "build_representation_pipeline"]
