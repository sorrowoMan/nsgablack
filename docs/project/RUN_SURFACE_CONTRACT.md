# Run Surface Contract

This document defines the stable runtime catalog contract shared by `nsgablack`
and `mlblack`.

Contract version:

- `run-surface.v1`

The goal is to make runs comparable across frameworks without collapsing
everything into "just one solver name" or "just one trainer name".

The primary unit is:

- which standard scaffold surface was executed
- what assembly stack was actually mounted
- what artifacts were produced
- what result the run ended with

## 1. Records

The formal contract contains four records:

1. `SurfaceRecord`
2. `AssemblyRecord`
3. `ArtifactRecord`
4. `RunRecord`

`Subject` is intentionally embedded inside `RunRecord` as
`subject_kind / subject_key / subject_signature / subject_json`, so we do not
introduce a fifth top-level record too early.

## 2. SurfaceRecord

`SurfaceRecord` answers:

- which standard scaffold entry was executed
- from which project / scaffold root
- what the formal surface kind is

Stable fields:

- `framework`
- `project_root`
- `scaffold_root`
- `surface_kind`
- `surface_key`
- `surface_label`
- `entry_path`
- `entry_module`
- `entry_symbol`
- `driver_ref`
- `family_ref`
- `tags`
- `metadata_json`
- `surface_signature`

Framework mapping:

- `nsgablack`: `surface_kind = solver`
- `mlblack`: `surface_kind = flow`

The surface record is the answer to:

- "Which scaffold folder entry did this run come from?"

## 3. AssemblyRecord

`AssemblyRecord` answers:

- what was actually mounted under that surface
- which parts should be reproduced to reconstruct the run

Stable fields:

- `framework`
- `surface_key`
- `assembly_key`
- `driver_ref`
- `family_ref`
- `preset_ref`
- `head_ref`
- `solver_ref`
- `trainer_ref`
- `adapter_ref`
- `representation_refs`
- `bias_refs`
- `component_refs`
- `provider_refs`
- `plugin_refs`
- `pipeline_refs`
- `mount_order`
- `component_slots_json`
- `metadata_json`
- `assembly_signature`

Notes:

- `mount_order` is the replay order surface.
- `component_slots_json` is where framework-specific slot wiring lives.
- `assembly_signature` is the primary comparison key for reproducibility.

## 4. ArtifactRecord

`ArtifactRecord` answers:

- what concrete artifact was produced by the run
- what role the artifact plays
- how to trace it back to the run and assembly

Stable fields:

- `framework`
- `run_id`
- `artifact_id`
- `artifact_kind`
- `artifact_role`
- `producer_ref`
- `surface_key`
- `assembly_signature`
- `path`
- `uri`
- `format`
- `created_at_utc`
- `metrics_json`
- `metadata_json`
- `tags`
- `artifact_signature`

Examples of `artifact_role`:

- `primary_model_artifact`
- `report`
- `checkpoint`
- `trace`
- `export`

## 5. RunRecord

`RunRecord` is the top-level run index row.

It answers:

- what was run
- on what subject
- with what parameters
- with what result

Stable fields:

- `framework`
- `run_id`
- `namespace`
- `tag`
- `status`
- `started_at_utc`
- `finished_at_utc`
- `duration_s`
- `surface_key`
- `surface_kind`
- `surface_signature`
- `assembly_signature`
- `subject_kind`
- `subject_key`
- `subject_signature`
- `param_signature`
- `driver_ref`
- `family_ref`
- `output_dir`
- `primary_metric_name`
- `primary_metric_value`
- `metric_summary_json`
- `params_json`
- `result_json`
- `component_refs`
- `artifact_ids`
- `metadata_json`

This means the comparison key is not only:

- `solver_name`
- or `trainer_name`

It is instead:

- `surface_signature`
- `assembly_signature`
- `subject_signature`
- `param_signature`

## 6. Cross-Framework Interpretation

### 6.1 nsgablack

Recommended mapping:

- `surface_kind = solver`
- `driver_ref = solver:<name>` or `adapter:<name>`
- `adapter_ref` is first-class
- `representation_refs / bias_refs / plugin_refs / provider_refs` carry the
  actual solver stack

### 6.2 mlblack

Recommended mapping:

- `surface_kind = flow`
- `driver_ref = trainer:<name>`
- `family_ref / preset_ref / head_ref` are first-class
- `component_refs / provider_refs / plugin_refs` carry the actual training stack

## 7. Why This Contract Exists

This contract prevents a bad simplification:

- "Just store solver name."
- "Just store trainer name."

That is not enough for reproducibility.

The contract makes the runtime surface comparable by scaffold entry,
resolved assembly, subject, parameters, result, and artifact set.

## 8. Code Surface

Current code contract modules:

- `nsgablack.utils.engineering.run_contracts`
- `mlblack.experiment.contracts`

Both expose:

- `SurfaceRecord`
- `AssemblyRecord`
- `ArtifactRecord`
- `RunRecord`
- `RUN_SURFACE_CONTRACT_VERSION`

