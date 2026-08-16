# Run / Artifact Surface Protocol

This document defines the higher-level product protocol shared by `nsgablack`
and `mlblack` for runtime experiment surfaces.

It sits above the raw record contract:

- `SurfaceRecord`
- `AssemblyRecord`
- `RunRecord`
- `ArtifactRecord`

The goal is not only to keep field names aligned, but also to keep:

- SQL materialization semantics aligned
- list/show/filter semantics aligned
- URL / deep-link semantics aligned
- dashboard page behavior aligned

Contract family:

- `run-surface.v1`

## 1. Product Goal

The experiment surface should answer four questions together:

1. Which standard Case surface ran?
2. What assembly stack was actually mounted?
3. What run result was produced?
4. What concrete artifacts came out of that run?

This prevents both frameworks from collapsing into:

- "just solver name"
- "just trainer name"

## 2. Record Layers

The formal detail stack is always:

1. `SurfaceRecord`
2. `AssemblyRecord`
3. `RunRecord`
4. `ArtifactRecord`

Rules:

- `SurfaceRecord` answers the scaffold entry surface
- `AssemblyRecord` answers the resolved mounted stack
- `RunRecord` answers one concrete execution
- `ArtifactRecord` answers one concrete output object

## 3. SQL Materialization Surface

The first-class product surface must expose both:

- run surface table / view
- artifact surface table / view

Recommended minimum list fields for the run surface:

- `run_id`
- `status`
- `surface_key`
- `surface_kind`
- `driver_ref`
- `semantic_layer`
- `assembly_signature`
- `primary_metric_name`
- `primary_metric_value`
- `started_at_utc`
- `finished_at_utc`
- `duration_s`

Recommended minimum list fields for the artifact surface:

- `run_id`
- `artifact_id`
- `artifact_role`
- `artifact_kind`
- `producer_ref`
- `surface_key`
- `assembly_signature`
- `path`
- `format`

JSON projections should remain visible:

- `surface_record_json`
- `assembly_record_json`
- `run_record_json`
- `artifact_record_json`

## 4. Framework Mapping

### 4.1 `nsgablack`

Recommended mapping:

- `surface_kind = case`
- `semantic_layer = optimization`
- `driver_ref = adapter:<name>` or `solver:<name>`
- `solver_ref`, `adapter_ref`, `representation_refs`, `bias_refs`,
  `provider_refs`, `plugin_refs` remain first-class through
  `AssemblyRecord`

### 4.2 `mlblack`

Recommended mapping:

- `surface_kind = case`
- `semantic_layer = ml`
- `driver_ref = trainer:<name>`
- `preset_ref = preset:<name>`
- `head_ref = head:<task>`

## 5. URL / Deep-Link Protocol

All runtime experiment dashboards should support these core query params:

- `db`
- `limit`
- `view`
- `selected`
- `detail_tab`
- `column_mode`
- `page_size`
- `results_collapse`
- `query`

Facet-style filters use:

- `f_<field>=value`

Examples:

- `f_run_status=completed`
- `f_semantic_layer=ml`
- `f_artifact_role=report`

### 5.1 `view`

Stable values:

- `run_catalog`
- `artifact_catalog`

### 5.2 `selected`

Stable encoding:

- run row: `run:<run_id>`
- artifact row: `artifact:<run_id>:<artifact_id>`

### 5.3 Result Layout State

Stable values:

- `column_mode = compact | standard | full`
- `page_size = integer`
- `results_collapse = expanded | collapsed`

### 5.4 Detail State

`detail_tab` is a first-class state and should be deep-linkable.

Recommended stable values:

- `overview`
- `contracts`
- `payload`

## 6. Dashboard Page Protocol

The runtime product page should preserve the same five-block structure:

1. hero
2. stats
3. filter
4. results
5. detail

Behavioral rules:

- filters are top-aligned, not scattered through sidebars
- results must expose the formal run / artifact list surface
- detail must always show the four-layer contract stack
- deep-link must restore current filters and current selection

## 7. Required Cross-Link Behavior

When the current view is `run_catalog`:

- detail should expose linked artifact rows
- users should be able to inspect the run-level `ArtifactRecord` set

When the current view is `artifact_catalog`:

- detail should expose the linked run surface
- users should be able to inspect the linked `SurfaceRecord`,
  `AssemblyRecord`, and `RunRecord`

## 8. Comparison Semantics

Cross-run comparison should prefer:

- `surface_signature`
- `assembly_signature`
- `subject_signature`
- `param_signature`

not only:

- solver name
- trainer name

## 9. Compatibility Rule

Future expansion should extend existing fields before inventing synonyms.

That means:

- do not replace `surface_key` with another surface identifier
- do not replace `assembly_signature` with another assembly hash name
- do not invent alternate encodings for `selected`

If a new framework-specific scalar is needed, add it as an extension field
without breaking the shared meaning of the common fields above.
