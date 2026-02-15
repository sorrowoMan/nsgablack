# utils/parallel

## Purpose
Parallel execution and batch scheduling helpers.

## Trigger Timing
Called in batch evaluation or plugin-level parallel workflows.

## Input
- Task function, task list, backend parameters.

## Output
- Parallel execution results and status snapshots.

## Side Effects
Uses threads/processes and related resources.

## Failure Policy
Task errors should preserve task context for diagnosis.

## Directory Contents
- See source files in this directory.

