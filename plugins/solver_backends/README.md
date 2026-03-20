# plugins/solver_backends

Backend adapters for numeric solvers and inner-runtime tools:
- `contract_bridge.py`
- `timeout_budget.py`
- `ngspice_backend.py`
- `copt_backend.py`

## CoptBackend templates

All templates share the same **top-level** parameter convention via
`payload["copt_template_params"]`:

- `spec`: mapping (preferred)
- `params`: alias of `spec`
- `spec_builder` or `builder`: callable `(request) -> spec`
- payload builders: `copt_spec_builder` or `copt_<template>_spec_builder`
- inline fields (for backward compatibility of `linear`/`qp`)

### Template list and spec keys

- `linear` / `lp` / `mip` / `milp`
  - `c`, `A`, `rhs`, `sense`, `lb`, `ub`, `vtype`, `objective_sense`
- `qp` / `miqp`
  - `c`, `Q`, `A`, `rhs`, `sense`, `lb`, `ub`, `vtype`, `objective_sense`, `quadratic_scale`
- `qcp` / `qcqp` / `miqcp`
  - all `qp` fields plus `qconstrs` (list of quadratic constraints)
- `socp` / `rsocp`
  - linear fields plus `cones`: list of `{type: "quad"|"rquad", vars: [idx|name...]}`  
- `expcone`
  - linear fields plus `exp_cones`: list of `{type: "primal"|"dual", vars: [...]}`  
- `sdp`
  - `psd_vars`, `psd_mats`, `psd_constrs`, optional `psd_objective`, plus linear fields
- `nlp`
  - `nl_objective` and `nl_constrs` with callable `expr` builders
- `multiobj`
  - `objectives`: list of `{c, Q, sense, priority, weight}`

All templates also accept `params` (or `model_params`) to forward
`model.setParam(...)` options.

### Shared advanced fields

These fields can be used in `spec` across most templates:
- `warm_start`: backend warm-start spec (apply_fn or mst_path)
- `solution_pool`: solution pool spec (params/max_solutions/extract_fn)
- `callback`: backend callback spec (register_fn/handler)
- `diagnostics`: IIS/feas-relax spec (iis/feas_relax/apply_fn)
- `indicator_constraints`: list of indicator specs
  - fields: `binvar`, `binval`, `expr` (callable or linear spec), `indicator_type`, `name`
- `gen_constrs`: list of general constraint specs
  - `kind`: `and`/`or`/`abs`/`max`/`min`/`pwl`
- `feas_relax`: feasibility relaxation settings
  - `mode`, `relax_constr`, `relax_var`, `on_infeasible`, `force`

### Decomposition templates (callback-driven)

- `dw` / `dantzig_wolfe` / `cg` / `column_generation`
  - required: `master_builder`, `subproblem_builder`, `column_generator`, `add_columns`
  - optional: `master_solve`, `subproblem_solve`, `stop_condition`, `objective_extractor`
- `bd` / `benders`
  - required: `master_builder`, `subproblem_builder`, `cut_generator`, `add_cuts`
  - optional: `master_solve`, `subproblem_solve`, `stop_condition`, `objective_extractor`

### Matrix-mode template

- `matrix` / `matrix_lp` / `matrix_mip`
  - `shape`, `vtype`, `lb`, `ub`, `A`, `rhs`, `sense`, `objective`, `matrix_mode`
  - or `matrix_builder` callable for fully custom matrix modeling
