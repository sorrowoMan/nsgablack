# core/adapters

Purpose:
- Canonical home of algorithm adapters.
- Adapters are first-class runtime units with `propose()` and `update()`.

Boundary:
- Keep process/search logic here.
- Do not put process-level classes in `bias.*`.
- Keep problem modeling in `problem/*`, and representation operators in `representation/*`.

Single-entry rule:
- One algorithm, one canonical adapter entry.
- Multi-strategy composition should wire these adapters instead of duplicating algorithm variants.
