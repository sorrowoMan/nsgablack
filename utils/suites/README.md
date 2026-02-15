# utils/suites

## Purpose
Standardized assembly suites (authoritative combinations).

## Trigger Timing
Called by build_solver/example entry at assembly time.

## Input
- Problem object, component config, strategy choice.

## Output
- Runnable solver composition.

## Side Effects
Injects default components/params.

## Failure Policy
Missing components should fail with direct replacement hints.

## Directory Contents
- See source files in this directory.

