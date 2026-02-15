# plugins/models

## Purpose
Model/subspace plugins for surrogate-style workflows.

## Trigger Timing
Usually at generation end or phase switch.

## Input
- Sample data (X/F/V) and model configuration.

## Output
- Model state, basis state, optional model report.

## Side Effects
May train/update model caches.

## Failure Policy
Prefer degrade-to-observe mode; avoid breaking optimization flow.

## Directory Contents
- `mas_model.py`
- `subspace_basis.py`

