# -*- coding: utf-8 -*-
"""Example pipeline: init + mutate + repair for continuous vectors."""

from __future__ import annotations

from nsgablack.representation import RepresentationPipeline

from .config import PipelineConfig, _build_pipeline_from_config


def build_pipeline(cfg: PipelineConfig | None = None) -> RepresentationPipeline:
    return _build_pipeline_from_config(cfg)
