# utils/runtime

## Purpose
Runtime helper logic (non-plugin implementation).

## Trigger Timing
Called by solver/plugins during active optimization.

## Input
- Solver state, stage parameters, control signals.

## Output
- Auxiliary runtime state and decisions.

## Side Effects
May update runtime control fields.

## Failure Policy
Prefer recoverable state; raise only for contract violations.

## Directory Contents
- See source files in this directory.

