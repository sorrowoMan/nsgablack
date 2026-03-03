# NSGA-II + Bias Architecture (Current)

This document describes the *current* recommended architecture for:

- NSGA-II as a baseline engine
- Bias as modular guidance (domain + algorithmic)
- Role-like behavior as composition (no special solver branch)

## 1) Baseline: NSGA-II

- Use `core/solver.py` (`EvolutionSolver`) when you want a classic baseline.
- Keep feasibility in `RepresentationPipeline` as much as possible.

## 2) Bias: guidance, not control flow

- Put soft constraints / preferences / tendencies into `BiasModule`.
- Keep hard constraints in `RepresentationPipeline.repair` (or feasible construction).

## 3) "Roles" without a new solver

If you want multi-role / cooperative search:

- Use `adapters/multi_strategy.py` as the controller (phase/regions/seeds/shared facts)
- Each role is an Adapter (or RoleAdapter-wrapped Adapter)
- Each role can have multiple units (independent adapter instances)

This keeps solver bases pure and makes coordination a single place to iterate:
the controller adapter.

