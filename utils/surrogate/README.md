# utils/surrogate

## Purpose
Surrogate training/inference helpers.

## Trigger Timing
Called by surrogate-related bias/plugins during train/infer.

## Input
- Samples, features, model settings.

## Output
- Predictions, uncertainty info, model objects.

## Side Effects
May cache or persist model artifacts.

## Failure Policy
Training/inference failure should degrade to raw evaluation path.

## Directory Contents
- See source files in this directory.

