# Companion Problem (Level-Set Mode) Guide

This note defines how to model a companion problem that stays in the same
problem domain while switching the solver's acceptance rule from vertical
improvement to horizontal (level-set) exploration.

## 1. Definition

- Primary problem: minimize or optimize objectives `f(x)`.
- Companion problem: keep `x` in the same domain, but accept candidates that
  stay near a target level set derived from existing Pareto points.

The companion problem does NOT change:
- `problem` definition
- `pipeline` (encoding/repair)
- `bias` logic
- adapters (candidate generators)

It ONLY changes solver control-plane state and acceptance/selection rules.

## 2. Why It Exists

Companion mode is a late-stage strategy for:
- lateral exploration across disconnected or thin feasible regions
- increasing Pareto diversity without destroying convergence
- jumping between basins without introducing new components

It is NOT a proof mechanism.

## 3. State Model (Solver-Control Fields)

Required fields (solver control-plane):
- `search_mode`: `"vertical"` or `"lateral"`
- `levelset_targets`: list of target objective vectors
- `levelset_eps`: tolerance (scalar or per-objective)
- `levelset_budget`: attempts per target or per epoch
- `levelset_policy`: how to pick targets (`best`, `frontier`, `round_robin`)
- `levelset_accept`: acceptance rule (`l2`, `linf`, `bandwidth`, `weighted`)
- `levelset_outcome`: counters for success/fail

Optional fields:
- `levelset_anchor_key`: id for which Pareto point spawned the companion task
- `levelset_phase`: scheduling phase index

Recommended context keys (if persisted):
- `context["search_mode"]`
- `context["levelset_target"]`
- `context["levelset_eps"]`
- `context["levelset_budget_used"]`
- `context["levelset_success_count"]`
- `context["levelset_fail_count"]`

## 4. Target Construction (Companion Problem)

For each Pareto solution `x` discovered by the primary search:
- compute `b = f(x)`
- store `b` as a target in `levelset_targets`

Multi-objective options:
- `l2`: accept if `||f(x') - b|| <= eps`
- `linf`: accept if `max_i |f_i(x') - b_i| <= eps`
- `bandwidth`: accept if `f_i(x') in [b_i - eps_i, b_i + eps_i]`
- `weighted`: accept if `sum_i w_i * |f_i(x') - b_i| <= eps`

Single-objective:
- accept if `|f(x') - b| <= eps`

## 5. Scheduling Policy

Example policy:
1. `t < t_switch`: run in `"vertical"` mode
2. `t >= t_switch`: mix modes by budget
3. For each epoch:
   - allocate `p`% budget to `"vertical"`
   - allocate `1-p`% budget to `"lateral"`

Target selection:
- `frontier`: pick latest Pareto points
- `round_robin`: cycle through stored targets
- `best`: pick best trade-offs by scalarization

## 6. Acceptance & Handling

When `search_mode = "lateral"`:
1. adapters still generate candidates
2. solver evaluates `f(x')`
3. accept if within level-set tolerance
4. if accepted:
   - add to Pareto candidate pool
   - update diversity metrics
5. if rejected:
   - record failure for this target

If no candidate matches within budget:
- mark target as `exhausted`
- either drop or re-queue with higher `eps`

## 7. Failure Modes and Guards

Common issues:
- infeasible level sets after repair
- targets too strict (`eps` too small)
- heavy drift after repair/encoding

Guards:
- increase `eps` when repeated failures occur
- cap per-target retries
- verify post-repair `f(x')` against `b`

## 8. Minimal Pseudocode

```python
def step():
    if search_mode == "vertical":
        candidates = propose()
        accept_vertical(candidates)
        return

    # lateral
    target = pick_levelset_target()
    for _ in range(levelset_budget):
        x = propose_one()
        fx = evaluate(x)
        if levelset_accept(fx, target, eps):
            accept_candidate(x, fx)
            record_success(target)
            break
    else:
        record_failure(target)
```

## 9. Recommended Defaults

- `t_switch`: 0.4 * max_steps
- `levelset_eps`: start large, decay each epoch
- `levelset_budget`: small fixed number per target (e.g. 3-10)
- `levelset_policy`: `frontier` or `round_robin`
- `levelset_accept`: `linf` for stability in multi-objective
