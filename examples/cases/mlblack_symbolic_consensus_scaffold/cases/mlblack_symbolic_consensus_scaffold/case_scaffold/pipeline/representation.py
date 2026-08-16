# -*- coding: utf-8 -*-
"""Representation pipeline assembly for the outer symbolic consensus genome."""

from __future__ import annotations

import argparse

import numpy as np

from nsgablack.representation import RepresentationPipeline
from nsgablack.representation.continuous import ClipRepair, ContextGaussianMutation, UniformInitializer


def build_representation_pipeline(problem, args: argparse.Namespace) -> RepresentationPipeline:
    lows = np.array([problem.bounds[f"x{i}"][0] for i in range(problem.dimension)], dtype=float)
    highs = np.array([problem.bounds[f"x{i}"][1] for i in range(problem.dimension)], dtype=float)
    return RepresentationPipeline(
        initializer=UniformInitializer(low=lows, high=highs),
        mutator=ContextGaussianMutation(
            base_sigma=float(args.vns_base_sigma),
            sigma_key="mutation_sigma",
            low=lows,
            high=highs,
        ),
        repair=ClipRepair(low=lows, high=highs),
    )
