# BUILD_SOLVER_REGISTRATION

This guide summarizes the recommended assembly order in `build_solver.py`.

## Order
1. build_modeling (problem + pipeline + bias)
2. build_evolution_solver
3. apply store + runtime governance profiles
4. apply solver profile
5. attach search adapter (optional)
6. attach runtime profile (L0)
7. attach evaluation runtime (L4)
8. attach governance plugins (L3)
9. attach observability + ops plugins (L1/L2)
10. attach checkpoint (optional)

## Notes
- Keep parameters in registries; keep selection here.
- Keep algorithm semantics out of plugins.
- Use `project doctor --build` after edits.
