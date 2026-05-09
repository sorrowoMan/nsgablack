# Orthogonal Symbolic Consensus System

English overview for the current `nsgablack -> mlblack` orthogonal symbolic consensus stack.

Status:

- current working system summary
- updated through the recent mechanism refresh
- intended as the shared reference for architecture, usage, product surface, and mechanism discussion

---

## 1. Goal

This system is not just "run symbolic regression once".

It is a layered system for:

1. discovering relatively orthogonal symbolic basis terms
2. assembling them with a small symbolic budget
3. repeating runs across a cycle
4. extracting stable core basis from multi-run consensus
5. re-running with locked core basis
6. materializing the full process into runtime run/artifact surfaces
7. inspecting the whole evolution in a product-style experiment dashboard

In practical terms, the goal is to formalize the full chain:

1. basis discovery
2. basis-set structure search
3. budgeted symbolic assembly
4. multi-run consensus
5. locked-core refinement
6. truth-recovery evaluation
7. observable runtime catalog and dashboard surfaces

---

## 2. System Scope

Current scope includes:

- `mlblack` symbolic orthogonal trainer and basis search engine
- `mlblack` basis consensus and locked-core selection logic
- `nsgablack` outer orchestration scaffold
- `nsgablack` runtime surface tracker
- `nsgablack` experiment catalog and dashboard
- formal benchmark scaffold for known-relation suites

This means the system is already more than an algorithm module.

It has four simultaneous faces:

1. algorithm face
2. orchestration face
3. contract face
4. product surface face

---

## 3. Layered Architecture

There are two useful views of the stack.

### 3.1 Framework-Level View

`nsgablack`

- owns outer orchestration
- owns outer search budget
- owns runtime surface persistence
- owns experiment UI and catalog product surface

`mlblack`

- owns actual symbolic modeling logic
- owns basis search, symbolic assembly, and truth recovery
- owns consensus-to-locked-core symbolic workflow

### 3.2 Runtime-Level View

`L1`: outer `nsgablack` solver

- chooses orchestration and search-budget knobs
- treats one whole mlblack symbolic orchestration as an inner evaluation

`L2`: consensus cycle orchestration

- runs multiple unlocked symbolic attempts
- computes consensus tables
- produces locked-core seed genome

`L3`: stage-level execution

- `unlocked_batch`
- `consensus`
- `locked_core_refinement`

Within `L3`, the real symbolic model runs happen in `mlblack`.

---

## 4. Core File Map

### 4.1 `mlblack`

Basis search engine:

- `C:\Users\hp\Desktop\mlblack\core\symbolic\orthogonal_basis_search.py`

Consensus and locked core:

- `C:\Users\hp\Desktop\mlblack\core\symbolic\basis_consensus.py`

Trainer:

- `C:\Users\hp\Desktop\mlblack\core\trainers\symbolic_orthogonal_trainer.py`

### 4.2 `nsgablack`

Backend bridge:

- `C:\Users\hp\Desktop\nsgablack\plugins\solver_backends\mlblack_symbolic_consensus_backend.py`

Outer scaffold entry:

- `C:\Users\hp\Desktop\nsgablack\examples\cases\mlblack_symbolic_consensus_scaffold\build_solver.py`

Benchmark suite runner:

- `C:\Users\hp\Desktop\nsgablack\examples\cases\mlblack_symbolic_consensus_scaffold\run_benchmark_suite.py`

Outer problem:

- `C:\Users\hp\Desktop\nsgablack\examples\cases\mlblack_symbolic_consensus_scaffold\problem\outer_problem.py`

Runtime surface tracker:

- `C:\Users\hp\Desktop\nsgablack\plugins\storage\runtime_surface_tracker.py`

Experiment dashboard:

- `C:\Users\hp\Desktop\nsgablack\experiment\dashboard.py`

Experiment CLI:

- `C:\Users\hp\Desktop\nsgablack\experiment\cli.py`

Unified UI shell:

- `C:\Users\hp\Desktop\nsgablack\ui\dashboard.py`

---

## 5. Formal Contracts

The runtime and product side are built around four formal records:

1. `SurfaceRecord`
2. `AssemblyRecord`
3. `RunRecord`
4. `ArtifactRecord`

Related protocol docs:

- `docs/project/RUN_SURFACE_CONTRACT.md`
- `docs/project/RUN_ARTIFACT_SURFACE_PROTOCOL.md`

Meaning of the four layers:

- `SurfaceRecord`: which standard scaffold surface this is
- `AssemblyRecord`: what actual stack was mounted
- `RunRecord`: one concrete execution instance
- `ArtifactRecord`: one concrete output object

These records are not abstract paperwork.

They are what allow the experiment UI to answer:

1. which benchmark or scaffold surface ran
2. which symbolic mechanism path was used
3. which cycle, stage, and run this came from
4. which artifacts and summaries were produced

---

## 6. End-to-End Execution Flow

The standard path is:

1. `nsgablack` outer solver proposes one orchestration candidate
2. the candidate is decoded into benchmark, search-budget, and consensus parameters
3. inner runtime delegates to `MlblackSymbolicConsensusBackend.solve(...)`
4. the backend builds the benchmark data bundle
5. the backend runs unlocked symbolic runs
6. the backend builds core basis tables
7. the backend selects the locked-core seed genome
8. the backend runs locked-core refinement symbolic runs
9. the backend summarizes leaderboards, cycle reports, stage reports, and basis evolution
10. runtime surface tracker persists all surfaces
11. dashboard reads the persisted surfaces

In product terms:

- the system emits not only a best expression
- it emits a structured evolutionary history

---

## 7. Mechanism Overview

The current symbolic mechanism has five important layers.

### 7.1 Layer A: Candidate Screening

The screen is no longer just marginal target correlation.

Current screen protocol:

- `target corr`
- `residual gain`
- `semantic novelty`
- `consensus prior`

Interpretation:

- `target corr`: does this candidate correlate with the target
- `residual gain`: after the current baseline fit, does this term still explain residual
- `semantic novelty`: is it semantically non-redundant inside the candidate pool
- `consensus prior`: does it align with previously selected stable core rows

This is exposed as:

- `screening_protocol = target_corr+residual_gain+semantic_novelty+consensus_prior`

### 7.2 Layer B: Outer Basis-Set Search

The outer search is no longer simple greedy assembly from a fixed candidate list.

It is now a beam-style basis-set structure search.

Important properties:

- multiple seed states
- branching expansions
- beam frontier pruning
- correlation control
- feature reuse control
- semantic repeat control
- piecewise or gate bonus support
- seed locking for locked-core runs

This is exposed as:

- `outer_search_protocol = beam_basis_set_structure_search`

Important outer expansion considerations:

- pairwise absolute correlation
- feature overlap penalty
- family diversity bonus
- semantic family bonus
- residual correlation to current residual
- marginal `R2` gain
- piecewise gate bonus

### 7.3 Layer C: Group-Level Outer Objective

The selected basis-set is scored by a combined group objective.

The current group-level logic explicitly considers:

- mean screen score
- orthogonality score
- residual complementarity
- semantic uniqueness
- pairwise correlation penalty
- feature overlap penalty

So the outer layer is already acting like a symbolic structure search objective, not just a list sorter.

### 7.4 Layer D: Inner Budgeted Symbolic Assembler

Once an outer basis set is selected, the inner stage is not plain ridge-only readout.

It runs a small-budget symbolic assembly process over the selected basis space.

Intent:

- keep inner symbolic composition cheap
- allow symbolic refinement inside the chosen basis space
- preserve a real symbolic second stage instead of only linear readout

This is tracked as:

- `inner_symbolic_search`
- `assembler_budget`

### 7.5 Layer E: Multi-Run Consensus and Locked Core

Unlocked runs are first collected across a cycle.

Then the system builds consensus tables under equivalence modes:

- `strict`
- `phase`
- `family`

After that, it selects a locked-core seed genome and runs locked refinement.

This is the part that turns a single symbolic run into a multi-run symbolic system.

---

## 8. Locked-Core Mechanism

Current locked-core selection is no longer family-only.

It uses a joint score built from:

- `support_rate`
- `exact_stability`
- `support_weight_rate`

Current formula:

- `joint_core_score = 0.50 * support_rate + 0.30 * exact_stability + 0.20 * support_weight_rate`

Meaning:

- `support_rate`: appears across how many runs
- `exact_stability`: within the chosen family or phase group, does one exact form stay dominant
- `support_weight_rate`: weighted support, usually influenced by run quality or outer objective

Important outputs now include:

- `exact_stability`
- `multi_run_core_frequency`
- `joint_core_score`
- `representative_exact_support_rate`
- `selection_source`

Backfill mode:

- current system can do `weighted_rank` backfill
- this helps when consensus alone yields too few seed terms

---

## 9. Truth-Recovery Evaluation

The system does not only report RMSE.

It tracks truth recovery at multiple levels:

- `exact_basis_hit_score`
- `exact_term_recovery_score`
- `phase_equivalent_term_recovery_score`
- `family_level_term_recovery_score`

Interpretation:

- `basis_hit`: did the actual basis term appear
- `term_recovery`: even if exact basis differs, did the final expression recover that truth term
- `phase-equivalent`: periodic or phase-equivalent terms get a fairer equivalence class
- `family-level`: higher-level mechanism families get a coarser but useful truth view

This is especially important for symbolic systems because:

- exact expression equality can be too strict
- family-level recovery can reveal mechanism direction even when syntax differs

---

## 10. Benchmark Families

Current known-relation benchmark family includes:

- `ohm_like`
- `ideal_gas_like`
- `arrhenius_gate_like`
- `periodic_gate_like`
- `redundant_proxy_control`

These are intended to test different failure modes:

- ratio structure
- exponential mechanism
- piecewise or gate behavior
- periodic equivalence
- redundant proxy confusion

---

## 11. Product Surface

This system already has a product-style experiment surface.

### 11.1 Runtime Tables

Current experiment runtime surface exposes:

- `runtime_run_surface`
- `runtime_artifact_surface`

The dashboard reads these directly.

### 11.2 Derived Product Fields

Recent additions make the following fields directly filterable:

- `screening_protocol`
- `outer_search_protocol`
- `joint_core_score_min`
- `consensus_prior_row_count`
- `selected_core_row_count`

These fields are not mere metadata decoration.

They let the UI directly ask:

- show me runs using the new four-part screening protocol
- show me runs using the new outer basis-set search
- show me runs whose locked-core confidence is above some threshold

### 11.3 Dashboard Behavior

The experiment dashboard supports:

- run catalog view
- artifact catalog view
- deep-link and URL state
- selected row restore
- clickable result table
- contract detail view
- payload detail view
- cycle, stage, and basis-evolution inspection

---

## 12. Runtime Surface Semantics

There are several different run kinds inside one DB.

### 12.1 Outer Solver Summary

Typical shape:

- scaffold-level summary
- best run, leaderboards, and comparison

### 12.2 Consensus Cycle Surface

Typical shape:

- one cycle summary
- core selection
- cycle-level comparison

### 12.3 Stage Surface

Typical stage keys:

- `unlocked_batch`
- `consensus`
- `locked_core_refinement`

### 12.4 Flow Surface

Typical shape:

- one concrete symbolic run
- direct symbolic search summary
- best for inspecting actual basis rows and truth recovery

---

## 13. Standard Usage

### 13.1 Run One Scaffold

```powershell
python examples\cases\mlblack_symbolic_consensus_scaffold\build_solver.py `
  --benchmark-key ohm_like `
  --generations 3 `
  --pop-size 6 `
  --vanilla-runs 3 `
  --locked-runs 2
```

### 13.2 Run a Benchmark Suite

```powershell
python examples\cases\mlblack_symbolic_consensus_scaffold\run_benchmark_suite.py `
  --suite-id my_suite `
  --benchmarks ohm_like arrhenius_gate_like redundant_proxy_control `
  --consensus-cycles 2 `
  --unlocked-runs-per-cycle 2 `
  --locked-runs-per-cycle 1 `
  --generations 2 `
  --pop-size 2 `
  --batch-size 4
```

### 13.3 Open Experiment UI

```powershell
python -m nsgablack experiment ui --db "C:\path\to\runtime_surface.sqlite3"
```

### 13.4 Open Unified UI Home

```powershell
python -m nsgablack ui
```

### 13.5 Filter Runs from CLI

```powershell
python -m nsgablack experiment list-runs `
  --db "C:\path\to\runtime_surface.sqlite3" `
  --screening-protocol "target_corr+residual_gain+semantic_novelty+consensus_prior" `
  --outer-search-protocol "beam_basis_set_structure_search" `
  --joint-core-score-min 0.5
```

---

## 14. Typical Output Files

One suite typically emits:

- `orchestrator_benchmark_suite_summary.json`
- `orchestrator_benchmark_suite_table.csv`
- `runtime_surface.sqlite3`
- per-benchmark `summary.json`
- per-benchmark `orchestration_summary.json`
- `cycle_reports.json`
- `stage_reports.json`
- `core_basis_evolution.json`
- `locked_core_selection.json`

Recent truth-frequency analysis also emits:

- `truth_frequency_report.json`
- `truth_frequency_report.csv`

---

## 15. Current Benchmark Readout

### 15.1 `ohm_like`

Observed pattern:

- locked-core can improve RMSE
- best exact recovery may still stay on the orthogonal run
- exact truth recovery and best fit do not always coincide

### 15.2 `redundant_proxy_control`

Observed pattern:

- locked-core is currently useful
- consensus prior can lift some true terms that unlocked runs missed
- in the recent larger run, `drift_bias` frequency improved under locked-core

Interpretation:

- consensus and locked-core are helping against redundant proxy confusion

### 15.3 `arrhenius_gate_like`

Observed pattern:

- consensus prior and locked-core become stable
- but they can stabilize the wrong proxy family
- the recent larger run did not raise true mechanism term frequency

Interpretation:

- the current issue is not only budget size
- it is a mechanism-selection problem
- the system is locking stable proxy basis, not the desired Arrhenius-style mechanism basis

---

## 16. Current Strengths

The current stack already does several hard things correctly:

1. standard scaffold path only, not ad hoc demo glue
2. multi-run consensus is formalized
3. locked core is formalized
4. truth recovery is multi-level, not RMSE-only
5. runtime surface is persistent and queryable
6. experiment dashboard is deep-linkable and clickable
7. mechanism protocol is now visible in product filters

This is already a serious systems foundation.

---

## 17. Current Weaknesses

Main current weaknesses:

1. some benchmarks still converge to stable proxies rather than true mechanism basis
2. `arrhenius_gate_like` remains the clearest failure case
3. locked-core quality depends on what unlocked runs expose
4. exact basis recovery is still hard when near-equivalent structures dominate
5. the system still needs stronger mechanism-family-aware outer objectives

---

## 18. What The Current System Really Is

It is best described as:

- a nested symbolic search system
- with orthogonal-basis-first structure discovery
- with budgeted symbolic assembly
- with multi-run consensus
- with locked-core refinement
- with formal runtime surfaces
- with product-level experiment inspection

So this is no longer just:

- one trainer
- one symbolic regression
- one benchmark script

It is already a full symbolic experimentation stack.

---

## 19. Recommended Next Step

If the goal is mechanism faithfulness rather than only stable fit, the most valuable next step is:

1. strengthen the outer objective toward mechanism-family truth candidates, especially for `arrhenius_gate_like`
2. make `exp_ratio` and `gate` families win against stable single-feature proxies
3. keep the current consensus and locked-core machinery, but improve what it is allowed to stabilize

In short:

- the consensus machinery is no longer the main missing part
- the next frontier is better mechanism-aware structure preference

---

## 20. Related Recent Artifacts

Recent larger benchmark suite:

- `examples/cases/mlblack_symbolic_consensus_scaffold/runs/benchmark_suite/orchestrator_arrhenius_redundant_mech_refresh_20260505/`

Important files inside:

- `orchestrator_benchmark_suite_summary.json`
- `runtime_surface.sqlite3`
- `truth_frequency_report.json`
- `truth_frequency_report.csv`

These files are the current best reference for:

- actual mechanism behavior
- consensus prior behavior
- locked-core truth-frequency effects
- dashboard-ready runtime surfaces

---

## 21. Two Guard Mechanisms

The current stack should now treat the following as explicit mechanism guards rather than informal trainer heuristics.

### 21.1 Equivalence-Expression Handling

This guard owns:

- equivalence-class formation across empirical / residual / semantic similarity
- representative choice inside a local equivalence family
- novelty reduction when multiple symbolic forms mean the same mechanism coordinate

Surface keys:

- `equivalence_expression_protocol`
- `equivalence_expression_mode`
- `equivalence_class_scope`

### 21.2 Interference-Feature Handling

This guard owns:

- proxy-like feature suppression
- trivial nonlinearity penalties on overlapping feature sources
- future cross-explanatory rejection and invariance audits

Surface keys:

- `interference_feature_protocol`
- `interference_feature_mode`
- `cross_explanatory_rejection_mode`
- `trivial_nonlinearity_penalty_mode`
- `environment_invariance_audit_mode`

Current status:

- protocol keys and runtime/artifact projection are formalized
- hard rejection behavior is still heuristic-first, not yet fully causal or intervention-complete
