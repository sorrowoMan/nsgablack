# utils/context

## Purpose
Context keys/events/contracts/lifecycle helpers.

## Trigger Timing
Called during context build, audit, replay, and validation.

## Input
- Context dicts, event streams, contract declarations.

## Output
- Normalized context, replay results, contract warnings/errors.

## Side Effects
May append context events.

## Failure Policy
Strict mode can raise; default mode returns warnings.

## Directory Contents
- See source files in this directory.

