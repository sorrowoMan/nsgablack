"""Canonical pipeline entry for production scheduling."""

from .schedule_pipeline import build_schedule_pipeline


def build_pipeline(*args, **kwargs):
    """Build the production-scheduling representation pipeline."""

    return build_schedule_pipeline(*args, **kwargs)


__all__ = ["build_pipeline", "build_schedule_pipeline"]
