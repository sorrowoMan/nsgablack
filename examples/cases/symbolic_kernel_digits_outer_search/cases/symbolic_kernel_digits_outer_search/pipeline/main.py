"""Canonical pipeline entry for symbolic-kernel digit search."""

try:
    from case_scaffold.pipeline import build_representation_pipeline
except ImportError:  # package import through cases.<name>
    from ..case_scaffold.pipeline import build_representation_pipeline


def build_pipeline(*args, **kwargs):
    """Build the outer-search representation pipeline."""

    return build_representation_pipeline(*args, **kwargs)


__all__ = ["build_pipeline", "build_representation_pipeline"]
