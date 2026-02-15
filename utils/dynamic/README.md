# utils/dynamic

## Purpose
Dynamic switching foundations (signal providers and switch base).

## Trigger Timing
Called by runtime dynamic switch plugins at configured intervals.

## Input
- External signals, solver state, switch config.

## Output
- Switch context and phase state transitions.

## Side Effects
May update solver dynamic fields.

## Failure Policy
Signal failures should degrade to empty signal snapshots.

## Directory Contents
- See source files in this directory.

