# 全局 API 改名审计（全文件 / 全方法）

> 本文由 `tools/generate_api_rename_audit.py` 自动生成，覆盖仓库内所有可解析 Python 文件中的类、函数、方法与异步方法。

## 1. 审计范围

- Python 文件数：`403`
- 符号总数：`4253`
- 明确建议改名：`0`

## 2. 动作说明

- `rename`：高置信度，建议直接进入首批改名计划。
- `review`：需要结合语义人工复核，不能机械替换。
- `keep`：当前规则下建议保留。
- `out-of-scope`：不作为 Canonical API 命名源头，但会受后续改名波及。

## 3. 目录级计数

| 目录 | rename | review | keep | out-of-scope |
|---|---:|---:|---:|---:|
| `adapters` | 0 | 0 | 365 | 0 |
| `benchmarks` | 0 | 0 | 13 | 0 |
| `bias` | 0 | 0 | 630 | 0 |
| `catalog` | 0 | 0 | 81 | 0 |
| `core` | 0 | 0 | 193 | 0 |
| `docs` | 0 | 0 | 1 | 0 |
| `examples` | 0 | 0 | 411 | 0 |
| `my_project` | 0 | 0 | 39 | 0 |
| `nsgablack` | 0 | 0 | 66 | 0 |
| `plugins` | 0 | 0 | 380 | 0 |
| `project` | 0 | 0 | 127 | 0 |
| `representation` | 0 | 0 | 188 | 0 |
| `root` | 0 | 0 | 40 | 0 |
| `scripts` | 0 | 0 | 17 | 0 |
| `tests` | 0 | 0 | 0 | 1017 |
| `tools` | 0 | 0 | 110 | 0 |
| `utils` | 0 | 0 | 575 | 0 |

## 4. 首批高置信度改名清单

| 文件 | 行号 | 类型 | 当前名称 | 建议新名 | 原因 |
|---|---:|---|---|---|---|

## 5. 全量逐项建议

### `__init__.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 114 | function | `get_version` | `keep` | `get_version` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 119 | function | `get_package_info` | `keep` | `get_package_info` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 124 | function | `get_available_features` | `keep` | `get_available_features` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 127 | function | `get_available_features._has_mod` | `keep` | `_has_mod` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `__main__.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 54 | function | `_ensure_utf8_io` | `keep` | `_ensure_utf8_io` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 66 | function | `_kind_label` | `keep` | `_kind_label` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 71 | function | `_print_entries` | `keep` | `_print_entries` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 106 | function | `_normalize_contract_values` | `keep` | `_normalize_contract_values` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 117 | function | `_collect_contract_fields` | `keep` | `_collect_contract_fields` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 136 | function | `_iter_contract_fields` | `keep` | `_iter_contract_fields` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 167 | function | `_print_contract_fields` | `keep` | `_print_contract_fields` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 178 | function | `_print_usage_fields` | `keep` | `_print_usage_fields` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 183 | function | `_print_usage_fields._print_list` | `keep` | `_print_list` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 198 | function | `_cmd_catalog_search` | `keep` | `_cmd_catalog_search` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 220 | function | `_cmd_catalog_list` | `keep` | `_cmd_catalog_list` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 243 | function | `_cmd_catalog_show` | `keep` | `_cmd_catalog_show` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 273 | function | `_cmd_catalog_add` | `keep` | `_cmd_catalog_add` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 300 | function | `_cmd_run_inspector` | `keep` | `_cmd_run_inspector` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 310 | function | `_cmd_project_init` | `keep` | `_cmd_project_init` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 322 | function | `_doctor_extract_line_column` | `keep` | `_doctor_extract_line_column` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 335 | function | `_doctor_severity` | `keep` | `_doctor_severity` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 339 | function | `_doctor_report_payload` | `keep` | `_doctor_report_payload` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 366 | function | `_format_doctor_problem_lines` | `keep` | `_format_doctor_problem_lines` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 382 | function | `_doctor_exit_code` | `keep` | `_doctor_exit_code` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 390 | function | `_doctor_print_report` | `keep` | `_doctor_print_report` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 401 | function | `_doctor_watch_signature` | `keep` | `_doctor_watch_signature` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 423 | function | `_cmd_project_doctor` | `keep` | `_cmd_project_doctor` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 431 | function | `_cmd_project_doctor._run_once` | `keep` | `_run_once` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 471 | function | `_cmd_project_catalog_search` | `keep` | `_cmd_project_catalog_search` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 497 | function | `_cmd_project_catalog_list` | `keep` | `_cmd_project_catalog_list` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 524 | function | `_cmd_project_catalog_show` | `keep` | `_cmd_project_catalog_show` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 551 | function | `_add_common_filters` | `keep` | `_add_common_filters` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 569 | function | `build_parser` | `keep` | `build_parser` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 718 | function | `main` | `keep` | `main` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `adapters/algorithm_adapter.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 15 | class | `AlgorithmAdapter` | `keep` | `AlgorithmAdapter` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 27 | method | `AlgorithmAdapter.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 32 | method | `AlgorithmAdapter.resolve_config` | `keep` | `resolve_config` | `high` | `-` | 该 resolve_* 属于推断/合并/派生语义，符合规范保留。 |
| 59 | method | `AlgorithmAdapter.create_local_rng` | `keep` | `create_local_rng` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 80 | method | `AlgorithmAdapter.setup` | `keep` | `setup` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 85 | method | `AlgorithmAdapter.propose` | `keep` | `propose` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 89 | method | `AlgorithmAdapter.update` | `keep` | `update` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 100 | method | `AlgorithmAdapter.teardown` | `keep` | `teardown` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 104 | method | `AlgorithmAdapter.get_state` | `keep` | `get_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 108 | method | `AlgorithmAdapter.set_state` | `keep` | `set_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 113 | method | `AlgorithmAdapter.validate_population_snapshot` | `keep` | `validate_population_snapshot` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 142 | method | `AlgorithmAdapter.set_population` | `keep` | `set_population` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 152 | method | `AlgorithmAdapter.coerce_candidates` | `keep` | `coerce_candidates` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 162 | method | `AlgorithmAdapter.get_context_contract` | `keep` | `get_context_contract` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 205 | method | `AlgorithmAdapter.get_runtime_context_projection` | `keep` | `get_runtime_context_projection` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 209 | method | `AlgorithmAdapter.get_runtime_context_projection_sources` | `keep` | `get_runtime_context_projection_sources` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 215 | class | `CompositeAdapter` | `keep` | `CompositeAdapter` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 225 | method | `CompositeAdapter.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 230 | method | `CompositeAdapter.setup` | `keep` | `setup` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 234 | method | `CompositeAdapter.propose` | `keep` | `propose` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 245 | method | `CompositeAdapter.update` | `keep` | `update` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 268 | method | `CompositeAdapter.teardown` | `keep` | `teardown` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 272 | method | `CompositeAdapter.get_state` | `keep` | `get_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 275 | method | `CompositeAdapter.set_state` | `keep` | `set_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 282 | method | `CompositeAdapter.get_context_contract` | `keep` | `get_context_contract` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `adapters/astar/adapter.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 30 | class | `AStarConfig` | `keep` | `AStarConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 61 | class | `_Node` | `keep` | `_Node` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 64 | method | `_Node.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 72 | class | `AStarAdapter` | `keep` | `AStarAdapter` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 84 | method | `AStarAdapter.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 123 | method | `AStarAdapter.setup` | `keep` | `setup` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 137 | method | `AStarAdapter.propose` | `keep` | `propose` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 192 | method | `AStarAdapter.update` | `keep` | `update` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 241 | method | `AStarAdapter._resolve_start_state` | `keep` | `_resolve_start_state` | `high` | `-` | 该 resolve_* 属于推断/合并/派生语义，符合规范保留。 |
| 251 | method | `AStarAdapter._edge_cost` | `keep` | `_edge_cost` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 256 | method | `AStarAdapter._heuristic` | `keep` | `_heuristic` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 264 | method | `AStarAdapter._aggregate_objective` | `keep` | `_aggregate_objective` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 270 | method | `AStarAdapter._default_state_key` | `keep` | `_default_state_key` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 280 | method | `AStarAdapter._push_open` | `keep` | `_push_open` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 296 | method | `AStarAdapter._trim_open` | `keep` | `_trim_open` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 309 | method | `AStarAdapter.get_state` | `keep` | `get_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 318 | method | `AStarAdapter.set_state` | `keep` | `set_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `adapters/async_event_driven/adapter.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 32 | class | `EventStrategySpec` | `keep` | `EventStrategySpec` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 42 | class | `AsyncEventDrivenConfig` | `keep` | `AsyncEventDrivenConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 65 | class | `AsyncEventDrivenAdapter` | `keep` | `AsyncEventDrivenAdapter` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 98 | method | `AsyncEventDrivenAdapter.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 131 | method | `AsyncEventDrivenAdapter.setup` | `keep` | `setup` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 152 | method | `AsyncEventDrivenAdapter.teardown` | `keep` | `teardown` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 157 | method | `AsyncEventDrivenAdapter.propose` | `keep` | `propose` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 203 | method | `AsyncEventDrivenAdapter.update` | `keep` | `update` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 275 | method | `AsyncEventDrivenAdapter._score` | `keep` | `_score` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 282 | method | `AsyncEventDrivenAdapter._enabled_specs` | `keep` | `_enabled_specs` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 285 | method | `AsyncEventDrivenAdapter._seed_queue` | `keep` | `_seed_queue` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 292 | method | `AsyncEventDrivenAdapter._topup_queue` | `keep` | `_topup_queue` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 311 | method | `AsyncEventDrivenAdapter._enqueue_propose` | `keep` | `_enqueue_propose` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 332 | method | `AsyncEventDrivenAdapter._push_archive` | `keep` | `_push_archive` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 339 | method | `AsyncEventDrivenAdapter._log_event` | `keep` | `_log_event` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 367 | method | `AsyncEventDrivenAdapter._publish_state` | `keep` | `_publish_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 420 | method | `AsyncEventDrivenAdapter.get_runtime_context_projection` | `keep` | `get_runtime_context_projection` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 424 | method | `AsyncEventDrivenAdapter.get_runtime_context_projection_sources` | `keep` | `get_runtime_context_projection_sources` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 429 | method | `AsyncEventDrivenAdapter.get_state` | `keep` | `get_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 440 | method | `AsyncEventDrivenAdapter.set_state` | `keep` | `set_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `adapters/differential_evolution/adapter.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 32 | class | `DEConfig` | `keep` | `DEConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 41 | class | `DifferentialEvolutionAdapter` | `keep` | `DifferentialEvolutionAdapter` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 55 | method | `DifferentialEvolutionAdapter.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 78 | method | `DifferentialEvolutionAdapter.setup` | `keep` | `setup` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 87 | method | `DifferentialEvolutionAdapter.propose` | `keep` | `propose` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 111 | method | `DifferentialEvolutionAdapter.update` | `keep` | `update` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 159 | method | `DifferentialEvolutionAdapter.set_population` | `keep` | `set_population` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 167 | method | `DifferentialEvolutionAdapter.get_population` | `keep` | `get_population` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 176 | method | `DifferentialEvolutionAdapter.get_runtime_context_projection` | `keep` | `get_runtime_context_projection` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 180 | method | `DifferentialEvolutionAdapter.get_runtime_context_projection_sources` | `keep` | `get_runtime_context_projection_sources` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 185 | method | `DifferentialEvolutionAdapter.get_state` | `keep` | `get_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 193 | method | `DifferentialEvolutionAdapter.set_state` | `keep` | `set_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 204 | method | `DifferentialEvolutionAdapter._ensure_population` | `keep` | `_ensure_population` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 248 | method | `DifferentialEvolutionAdapter._population_scores` | `keep` | `_population_scores` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 255 | method | `DifferentialEvolutionAdapter._mutant_vector` | `keep` | `_mutant_vector` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 272 | method | `DifferentialEvolutionAdapter._binomial_crossover` | `keep` | `_binomial_crossover` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 281 | method | `DifferentialEvolutionAdapter._scores` | `keep` | `_scores` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 292 | method | `DifferentialEvolutionAdapter._sync_runtime_projection` | `keep` | `_sync_runtime_projection` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `adapters/gradient_descent/adapter.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 17 | class | `GradientDescentConfig` | `keep` | `GradientDescentConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 27 | class | `GradientDescentAdapter` | `keep` | `GradientDescentAdapter` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 36 | method | `GradientDescentAdapter.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 58 | method | `GradientDescentAdapter.setup` | `keep` | `setup` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 66 | method | `GradientDescentAdapter.propose` | `keep` | `propose` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 85 | method | `GradientDescentAdapter.update` | `keep` | `update` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 129 | method | `GradientDescentAdapter.get_runtime_context_projection` | `keep` | `get_runtime_context_projection` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 133 | method | `GradientDescentAdapter.get_runtime_context_projection_sources` | `keep` | `get_runtime_context_projection_sources` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 138 | method | `GradientDescentAdapter.get_state` | `keep` | `get_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 145 | method | `GradientDescentAdapter.set_state` | `keep` | `set_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 158 | method | `GradientDescentAdapter._scores` | `keep` | `_scores` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `adapters/mas/adapter.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 17 | class | `MASConfig` | `keep` | `MASConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 23 | class | `MASAdapter` | `keep` | `MASAdapter` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 40 | method | `MASAdapter.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 58 | method | `MASAdapter.propose` | `keep` | `propose` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 86 | method | `MASAdapter.update` | `keep` | `update` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 101 | method | `MASAdapter._init_center` | `keep` | `_init_center` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 120 | method | `MASAdapter._extract_bounds` | `keep` | `_extract_bounds` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 132 | method | `MASAdapter._clip_to_bounds` | `keep` | `_clip_to_bounds` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 138 | method | `MASAdapter.get_state` | `keep` | `get_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 143 | method | `MASAdapter.set_state` | `keep` | `set_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 149 | method | `MASAdapter._score` | `keep` | `_score` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `adapters/moa_star/adapter.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 30 | class | `MOAStarConfig` | `keep` | `MOAStarConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 68 | class | `_Label` | `keep` | `_Label` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 71 | method | `_Label.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 80 | class | `MOAStarAdapter` | `keep` | `MOAStarAdapter` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 92 | method | `MOAStarAdapter.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 134 | method | `MOAStarAdapter.setup` | `keep` | `setup` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 156 | method | `MOAStarAdapter.propose` | `keep` | `propose` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 206 | method | `MOAStarAdapter.update` | `keep` | `update` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 250 | method | `MOAStarAdapter._try_add_label` | `keep` | `_try_add_label` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 289 | method | `MOAStarAdapter._update_pareto` | `keep` | `_update_pareto` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 312 | method | `MOAStarAdapter._resolve_start_state` | `keep` | `_resolve_start_state` | `high` | `-` | 该 resolve_* 属于推断/合并/派生语义，符合规范保留。 |
| 322 | method | `MOAStarAdapter._edge_cost_vec` | `keep` | `_edge_cost_vec` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 328 | method | `MOAStarAdapter._heuristic_vec` | `keep` | `_heuristic_vec` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 335 | method | `MOAStarAdapter._as_vec` | `keep` | `_as_vec` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 349 | method | `MOAStarAdapter._priority` | `keep` | `_priority` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 365 | method | `MOAStarAdapter._dominates` | `keep` | `_dominates` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 370 | method | `MOAStarAdapter._default_state_key` | `keep` | `_default_state_key` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 380 | method | `MOAStarAdapter._push_open` | `keep` | `_push_open` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 390 | method | `MOAStarAdapter._trim_open` | `keep` | `_trim_open` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 402 | method | `MOAStarAdapter.get_state` | `keep` | `get_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 411 | method | `MOAStarAdapter.set_state` | `keep` | `set_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `adapters/moead/adapter.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 27 | class | `MOEADConfig` | `keep` | `MOEADConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 57 | class | `MOEADAdapter` | `keep` | `MOEADAdapter` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 81 | method | `MOEADAdapter.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 117 | method | `MOEADAdapter.setup` | `keep` | `setup` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 157 | method | `MOEADAdapter.teardown` | `keep` | `teardown` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 163 | method | `MOEADAdapter.propose` | `keep` | `propose` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 190 | method | `MOEADAdapter.update` | `keep` | `update` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 250 | method | `MOEADAdapter.get_runtime_context_projection` | `keep` | `get_runtime_context_projection` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 254 | method | `MOEADAdapter.get_runtime_context_projection_sources` | `keep` | `get_runtime_context_projection_sources` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 262 | method | `MOEADAdapter.get_state` | `keep` | `get_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 276 | method | `MOEADAdapter.set_state` | `keep` | `set_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 296 | method | `MOEADAdapter.get_population` | `keep` | `get_population` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 301 | method | `MOEADAdapter.set_population` | `keep` | `set_population` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 342 | method | `MOEADAdapter._warn_if_no_archive_plugin` | `keep` | `_warn_if_no_archive_plugin` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 360 | method | `MOEADAdapter._refresh_runtime_projection` | `keep` | `_refresh_runtime_projection` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 369 | method | `MOEADAdapter._sync_population_snapshot` | `keep` | `_sync_population_snapshot` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 380 | method | `MOEADAdapter._recompute_ideal` | `keep` | `_recompute_ideal` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 393 | method | `MOEADAdapter._variation` | `keep` | `_variation` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 410 | method | `MOEADAdapter._de_variation` | `keep` | `_de_variation` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 437 | method | `MOEADAdapter._update_ideal` | `keep` | `_update_ideal` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 451 | method | `MOEADAdapter._is_better_for_subproblem` | `keep` | `_is_better_for_subproblem` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 468 | method | `MOEADAdapter._g` | `keep` | `_g` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 477 | method | `MOEADAdapter._generate_weights` | `keep` | `_generate_weights` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 498 | method | `MOEADAdapter._auto_lattice_h` | `keep` | `_auto_lattice_h` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 507 | method | `MOEADAdapter._n_simplex_lattice` | `keep` | `_n_simplex_lattice` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 513 | method | `MOEADAdapter._simplex_lattice` | `keep` | `_simplex_lattice` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 517 | method | `MOEADAdapter._simplex_lattice.rec` | `keep` | `rec` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 535 | method | `MOEADAdapter._compute_neighbors` | `keep` | `_compute_neighbors` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `adapters/multi_strategy/adapter.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 44 | class | `StrategySpec` | `keep` | `StrategySpec` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 54 | class | `RoleSpec` | `keep` | `RoleSpec` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 71 | class | `UnitSpec` | `keep` | `UnitSpec` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 79 | class | `MultiStrategyControlRule` | `keep` | `MultiStrategyControlRule` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 98 | class | `MultiStrategyConfig` | `keep` | `MultiStrategyConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 162 | class | `StrategyRouterAdapter` | `keep` | `StrategyRouterAdapter` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 198 | method | `StrategyRouterAdapter.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 249 | method | `StrategyRouterAdapter.setup` | `keep` | `setup` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 281 | method | `StrategyRouterAdapter.teardown` | `keep` | `teardown` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 285 | method | `StrategyRouterAdapter._build_units` | `keep` | `_build_units` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 302 | method | `StrategyRouterAdapter._instantiate_role_adapter` | `keep` | `_instantiate_role_adapter` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 321 | method | `StrategyRouterAdapter._score` | `keep` | `_score` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 328 | method | `StrategyRouterAdapter._role_specs` | `keep` | `_role_specs` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 334 | method | `StrategyRouterAdapter._phase_for_step` | `keep` | `_phase_for_step` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 350 | method | `StrategyRouterAdapter._enabled_roles_for_phase` | `keep` | `_enabled_roles_for_phase` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 358 | method | `StrategyRouterAdapter._effective_weight` | `keep` | `_effective_weight` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 366 | method | `StrategyRouterAdapter._build_runtime_rule_context` | `keep` | `_build_runtime_rule_context` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 394 | method | `StrategyRouterAdapter._dsl_get_value_by_path` | `keep` | `_dsl_get_value_by_path` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 414 | method | `StrategyRouterAdapter._dsl_resolve` | `keep` | `_dsl_resolve` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 421 | method | `StrategyRouterAdapter._dsl_eval` | `keep` | `_dsl_eval` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 474 | method | `StrategyRouterAdapter._list_to_str_set` | `keep` | `_list_to_str_set` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 481 | method | `StrategyRouterAdapter._rule_action_payload` | `keep` | `_rule_action_payload` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 520 | method | `StrategyRouterAdapter._evaluate_control_rules` | `keep` | `_evaluate_control_rules` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 574 | method | `StrategyRouterAdapter._build_policy_context` | `keep` | `_build_policy_context` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 592 | method | `StrategyRouterAdapter._apply_phase_policy` | `keep` | `_apply_phase_policy` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 619 | method | `StrategyRouterAdapter._allocate_role_budgets` | `keep` | `_allocate_role_budgets` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 689 | method | `StrategyRouterAdapter._split_to_units` | `keep` | `_split_to_units` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 709 | method | `StrategyRouterAdapter._maybe_refresh_regions` | `keep` | `_maybe_refresh_regions` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 718 | method | `StrategyRouterAdapter._default_region_partition` | `keep` | `_default_region_partition` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 758 | method | `StrategyRouterAdapter._assign_regions_to_units` | `keep` | `_assign_regions_to_units` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 771 | method | `StrategyRouterAdapter._select_seeds` | `keep` | `_select_seeds` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 789 | method | `StrategyRouterAdapter._broadcast_state` | `keep` | `_broadcast_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 797 | method | `StrategyRouterAdapter.propose` | `keep` | `propose` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 933 | method | `StrategyRouterAdapter.update` | `keep` | `update` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1018 | method | `StrategyRouterAdapter.get_runtime_context_projection` | `keep` | `get_runtime_context_projection` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1066 | method | `StrategyRouterAdapter.get_runtime_context_projection_sources` | `keep` | `get_runtime_context_projection_sources` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1070 | method | `StrategyRouterAdapter._record_unit_report` | `keep` | `_record_unit_report` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1096 | method | `StrategyRouterAdapter._collect_role_reports` | `keep` | `_collect_role_reports` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1115 | method | `StrategyRouterAdapter._build_strategy_stats` | `keep` | `_build_strategy_stats` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1132 | method | `StrategyRouterAdapter._build_unit_stats` | `keep` | `_build_unit_stats` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1145 | method | `StrategyRouterAdapter._build_region_stats` | `keep` | `_build_region_stats` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1178 | method | `StrategyRouterAdapter._adapt_weights` | `keep` | `_adapt_weights` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1223 | method | `StrategyRouterAdapter.get_context_contract` | `keep` | `get_context_contract` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `adapters/nsga2/adapter.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 26 | class | `NSGA2Config` | `keep` | `NSGA2Config` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 33 | class | `NSGA2Adapter` | `keep` | `NSGA2Adapter` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 42 | method | `NSGA2Adapter.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 65 | method | `NSGA2Adapter.setup` | `keep` | `setup` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 74 | method | `NSGA2Adapter.propose` | `keep` | `propose` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 92 | method | `NSGA2Adapter.update` | `keep` | `update` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 127 | method | `NSGA2Adapter.set_population` | `keep` | `set_population` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 136 | method | `NSGA2Adapter.get_population` | `keep` | `get_population` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 145 | method | `NSGA2Adapter.get_runtime_context_projection` | `keep` | `get_runtime_context_projection` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 149 | method | `NSGA2Adapter.get_runtime_context_projection_sources` | `keep` | `get_runtime_context_projection_sources` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 154 | method | `NSGA2Adapter.get_state` | `keep` | `get_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 161 | method | `NSGA2Adapter.set_state` | `keep` | `set_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 173 | method | `NSGA2Adapter._ensure_population` | `keep` | `_ensure_population` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 213 | method | `NSGA2Adapter._refresh_ranking` | `keep` | `_refresh_ranking` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 232 | method | `NSGA2Adapter._tournament_pick` | `keep` | `_tournament_pick` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 248 | method | `NSGA2Adapter._crossover` | `keep` | `_crossover` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 263 | method | `NSGA2Adapter._environmental_select` | `keep` | `_environmental_select` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 277 | method | `NSGA2Adapter._sync_runtime_projection` | `keep` | `_sync_runtime_projection` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 286 | method | `NSGA2Adapter._objective_scores` | `keep` | `_objective_scores` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `adapters/nsga3/adapter.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 17 | class | `NSGA3Config` | `keep` | `NSGA3Config` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 21 | class | `NSGA3Adapter` | `keep` | `NSGA3Adapter` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 33 | method | `NSGA3Adapter.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 51 | method | `NSGA3Adapter.setup` | `keep` | `setup` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 56 | method | `NSGA3Adapter._environmental_select` | `keep` | `_environmental_select` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 73 | method | `NSGA3Adapter._sort_fronts` | `keep` | `_sort_fronts` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 78 | method | `NSGA3Adapter._niching_pick` | `keep` | `_niching_pick` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 114 | method | `NSGA3Adapter._generate_reference_points` | `keep` | `_generate_reference_points` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 117 | method | `NSGA3Adapter._generate_reference_points._recurse` | `keep` | `_recurse` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 128 | method | `NSGA3Adapter._pairwise_dist` | `keep` | `_pairwise_dist` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 134 | method | `NSGA3Adapter._sync_runtime_projection` | `keep` | `_sync_runtime_projection` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `adapters/pattern_search/adapter.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 17 | class | `PatternSearchConfig` | `keep` | `PatternSearchConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 26 | class | `PatternSearchAdapter` | `keep` | `PatternSearchAdapter` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 35 | method | `PatternSearchAdapter.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 56 | method | `PatternSearchAdapter.setup` | `keep` | `setup` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 63 | method | `PatternSearchAdapter.propose` | `keep` | `propose` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 80 | method | `PatternSearchAdapter.update` | `keep` | `update` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 106 | method | `PatternSearchAdapter.get_runtime_context_projection` | `keep` | `get_runtime_context_projection` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 110 | method | `PatternSearchAdapter.get_runtime_context_projection_sources` | `keep` | `get_runtime_context_projection_sources` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 115 | method | `PatternSearchAdapter.get_state` | `keep` | `get_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 122 | method | `PatternSearchAdapter.set_state` | `keep` | `set_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 135 | method | `PatternSearchAdapter._scores` | `keep` | `_scores` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `adapters/role_adapters/adapter.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 30 | class | `RoleAdapter` | `keep` | `RoleAdapter` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 48 | method | `RoleAdapter.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 73 | method | `RoleAdapter._warn_once` | `keep` | `_warn_once` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 79 | method | `RoleAdapter._check_contract` | `keep` | `_check_contract` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 98 | method | `RoleAdapter.setup` | `keep` | `setup` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 102 | method | `RoleAdapter.propose` | `keep` | `propose` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 114 | method | `RoleAdapter.update` | `keep` | `update` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 131 | method | `RoleAdapter.teardown` | `keep` | `teardown` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 135 | method | `RoleAdapter._update_report` | `keep` | `_update_report` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 200 | method | `RoleAdapter.get_state` | `keep` | `get_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 213 | method | `RoleAdapter.set_state` | `keep` | `set_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 231 | method | `RoleAdapter.get_context_contract` | `keep` | `get_context_contract` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 254 | class | `RoleRouterAdapter` | `keep` | `RoleRouterAdapter` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 263 | method | `RoleRouterAdapter.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 284 | method | `RoleRouterAdapter.setup` | `keep` | `setup` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 289 | method | `RoleRouterAdapter.propose` | `keep` | `propose` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 310 | method | `RoleRouterAdapter.update` | `keep` | `update` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 340 | method | `RoleRouterAdapter.teardown` | `keep` | `teardown` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 344 | method | `RoleRouterAdapter.get_state` | `keep` | `get_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 349 | method | `RoleRouterAdapter.set_state` | `keep` | `set_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 359 | method | `RoleRouterAdapter._collect_role_reports` | `keep` | `_collect_role_reports` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 367 | method | `RoleRouterAdapter.get_runtime_context_projection` | `keep` | `get_runtime_context_projection` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 371 | method | `RoleRouterAdapter.get_runtime_context_projection_sources` | `keep` | `get_runtime_context_projection_sources` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `adapters/serial_strategy/adapter.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 25 | class | `SerialPhaseSpec` | `keep` | `SerialPhaseSpec` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 34 | class | `SerialStrategyConfig` | `keep` | `SerialStrategyConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 41 | class | `StrategyChainAdapter` | `keep` | `StrategyChainAdapter` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 56 | method | `StrategyChainAdapter.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 82 | method | `StrategyChainAdapter.setup` | `keep` | `setup` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 90 | method | `StrategyChainAdapter.teardown` | `keep` | `teardown` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 100 | method | `StrategyChainAdapter.propose` | `keep` | `propose` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 110 | method | `StrategyChainAdapter.update` | `keep` | `update` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 154 | method | `StrategyChainAdapter.get_state` | `keep` | `get_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 169 | method | `StrategyChainAdapter.set_state` | `keep` | `set_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 184 | method | `StrategyChainAdapter._materialize_adapters` | `keep` | `_materialize_adapters` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 204 | method | `StrategyChainAdapter._current_adapter` | `keep` | `_current_adapter` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 210 | method | `StrategyChainAdapter._current_phase_name` | `keep` | `_current_phase_name` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 216 | method | `StrategyChainAdapter._should_advance` | `keep` | `_should_advance` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 232 | method | `StrategyChainAdapter._advance_phase` | `keep` | `_advance_phase` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `adapters/simulated_annealing/adapter.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 30 | class | `SAConfig` | `keep` | `SAConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 51 | class | `SimulatedAnnealingAdapter` | `keep` | `SimulatedAnnealingAdapter` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 68 | method | `SimulatedAnnealingAdapter.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 91 | method | `SimulatedAnnealingAdapter._build_rng` | `keep` | `_build_rng` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 97 | method | `SimulatedAnnealingAdapter.setup` | `keep` | `setup` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 106 | method | `SimulatedAnnealingAdapter._warn_if_pipeline_has_no_mutator` | `keep` | `_warn_if_pipeline_has_no_mutator` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 123 | method | `SimulatedAnnealingAdapter._score` | `keep` | `_score` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 130 | method | `SimulatedAnnealingAdapter._build_sa_context` | `keep` | `_build_sa_context` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 143 | method | `SimulatedAnnealingAdapter.propose` | `keep` | `propose` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 156 | method | `SimulatedAnnealingAdapter.update` | `keep` | `update` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 212 | method | `SimulatedAnnealingAdapter.get_state` | `keep` | `get_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 220 | method | `SimulatedAnnealingAdapter.set_state` | `keep` | `set_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 231 | method | `SimulatedAnnealingAdapter.get_runtime_context_projection` | `keep` | `get_runtime_context_projection` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 235 | method | `SimulatedAnnealingAdapter.get_runtime_context_projection_sources` | `keep` | `get_runtime_context_projection_sources` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `adapters/single_trajectory_adaptive/adapter.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 25 | class | `SingleTrajectoryAdaptiveConfig` | `keep` | `SingleTrajectoryAdaptiveConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 46 | class | `SingleTrajectoryAdaptiveAdapter` | `keep` | `SingleTrajectoryAdaptiveAdapter` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 65 | method | `SingleTrajectoryAdaptiveAdapter.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 91 | method | `SingleTrajectoryAdaptiveAdapter.setup` | `keep` | `setup` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 101 | method | `SingleTrajectoryAdaptiveAdapter._score` | `keep` | `_score` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 108 | method | `SingleTrajectoryAdaptiveAdapter._build_context` | `keep` | `_build_context` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 119 | method | `SingleTrajectoryAdaptiveAdapter.propose` | `keep` | `propose` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 132 | method | `SingleTrajectoryAdaptiveAdapter.update` | `keep` | `update` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 187 | method | `SingleTrajectoryAdaptiveAdapter.get_state` | `keep` | `get_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 199 | method | `SingleTrajectoryAdaptiveAdapter.set_state` | `keep` | `set_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 214 | method | `SingleTrajectoryAdaptiveAdapter.get_runtime_context_projection` | `keep` | `get_runtime_context_projection` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 226 | method | `SingleTrajectoryAdaptiveAdapter.get_runtime_context_projection_sources` | `keep` | `get_runtime_context_projection_sources` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `adapters/spea2/adapter.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 16 | class | `SPEA2Config` | `keep` | `SPEA2Config` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 21 | class | `SPEA2Adapter` | `keep` | `SPEA2Adapter` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 30 | method | `SPEA2Adapter.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 47 | method | `SPEA2Adapter._environmental_select` | `keep` | `_environmental_select` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 79 | method | `SPEA2Adapter._spea2_fitness` | `keep` | `_spea2_fitness` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 102 | method | `SPEA2Adapter._pairwise_dist` | `keep` | `_pairwise_dist` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `adapters/trust_region_base/adapter.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 16 | class | `TrustRegionBaseAdapter` | `keep` | `TrustRegionBaseAdapter` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 32 | method | `TrustRegionBaseAdapter.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 47 | method | `TrustRegionBaseAdapter.setup` | `keep` | `setup` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 53 | method | `TrustRegionBaseAdapter.propose` | `keep` | `propose` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 71 | method | `TrustRegionBaseAdapter.update` | `keep` | `update` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 104 | method | `TrustRegionBaseAdapter.get_state` | `keep` | `get_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 115 | method | `TrustRegionBaseAdapter.set_state` | `keep` | `set_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 125 | method | `TrustRegionBaseAdapter._init_center` | `keep` | `_init_center` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 144 | method | `TrustRegionBaseAdapter._extract_bounds` | `keep` | `_extract_bounds` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 156 | method | `TrustRegionBaseAdapter._clip_to_bounds` | `keep` | `_clip_to_bounds` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 163 | method | `TrustRegionBaseAdapter._reset_internal_state` | `keep` | `_reset_internal_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 166 | method | `TrustRegionBaseAdapter._before_propose` | `keep` | `_before_propose` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 169 | method | `TrustRegionBaseAdapter._after_propose` | `keep` | `_after_propose` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 172 | method | `TrustRegionBaseAdapter._after_update` | `keep` | `_after_update` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 184 | method | `TrustRegionBaseAdapter._extra_state` | `keep` | `_extra_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 187 | method | `TrustRegionBaseAdapter._load_extra_state` | `keep` | `_load_extra_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 192 | method | `TrustRegionBaseAdapter._sample_delta` | `keep` | `_sample_delta` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 196 | method | `TrustRegionBaseAdapter._score` | `keep` | `_score` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `adapters/trust_region_dfo/adapter.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 16 | class | `TrustRegionDFOConfig` | `keep` | `TrustRegionDFOConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 28 | class | `TrustRegionDFOAdapter` | `keep` | `TrustRegionDFOAdapter` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 41 | method | `TrustRegionDFOAdapter.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 57 | method | `TrustRegionDFOAdapter._sample_delta` | `keep` | `_sample_delta` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 62 | method | `TrustRegionDFOAdapter._score` | `keep` | `_score` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `adapters/trust_region_mo_dfo/adapter.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 17 | class | `TrustRegionMODFOConfig` | `keep` | `TrustRegionMODFOConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 31 | class | `TrustRegionMODFOAdapter` | `keep` | `TrustRegionMODFOAdapter` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 46 | method | `TrustRegionMODFOAdapter.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 63 | method | `TrustRegionMODFOAdapter._reset_internal_state` | `keep` | `_reset_internal_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 66 | method | `TrustRegionMODFOAdapter._sample_delta` | `keep` | `_sample_delta` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 71 | method | `TrustRegionMODFOAdapter._get_weights` | `keep` | `_get_weights` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 104 | method | `TrustRegionMODFOAdapter._score` | `keep` | `_score` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 121 | method | `TrustRegionMODFOAdapter._extra_state` | `keep` | `_extra_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 124 | method | `TrustRegionMODFOAdapter._load_extra_state` | `keep` | `_load_extra_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `adapters/trust_region_nonsmooth/adapter.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 16 | class | `TrustRegionNonSmoothConfig` | `keep` | `TrustRegionNonSmoothConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 29 | class | `TrustRegionNonSmoothAdapter` | `keep` | `TrustRegionNonSmoothAdapter` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 41 | method | `TrustRegionNonSmoothAdapter.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 57 | method | `TrustRegionNonSmoothAdapter._sample_delta` | `keep` | `_sample_delta` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 62 | method | `TrustRegionNonSmoothAdapter._score` | `keep` | `_score` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `adapters/trust_region_subspace/adapter.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 17 | class | `TrustRegionSubspaceConfig` | `keep` | `TrustRegionSubspaceConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 31 | class | `TrustRegionSubspaceAdapter` | `keep` | `TrustRegionSubspaceAdapter` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 45 | method | `TrustRegionSubspaceAdapter.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 63 | method | `TrustRegionSubspaceAdapter._reset_internal_state` | `keep` | `_reset_internal_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 67 | method | `TrustRegionSubspaceAdapter._before_propose` | `keep` | `_before_propose` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 75 | method | `TrustRegionSubspaceAdapter._sample_delta` | `keep` | `_sample_delta` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 81 | method | `TrustRegionSubspaceAdapter._sample_subspace` | `keep` | `_sample_subspace` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 88 | method | `TrustRegionSubspaceAdapter._score` | `keep` | `_score` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 102 | method | `TrustRegionSubspaceAdapter._extra_state` | `keep` | `_extra_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 108 | method | `TrustRegionSubspaceAdapter._load_extra_state` | `keep` | `_load_extra_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `adapters/vns/adapter.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 23 | class | `VNSConfig` | `keep` | `VNSConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 45 | class | `VNSAdapter` | `keep` | `VNSAdapter` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 66 | method | `VNSAdapter.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 87 | method | `VNSAdapter.setup` | `keep` | `setup` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 97 | method | `VNSAdapter._warn_if_pipeline_does_not_consume_context` | `keep` | `_warn_if_pipeline_does_not_consume_context` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 134 | method | `VNSAdapter.propose` | `keep` | `propose` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 154 | method | `VNSAdapter.update` | `keep` | `update` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 200 | method | `VNSAdapter._current_sigma` | `keep` | `_current_sigma` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 204 | method | `VNSAdapter.get_runtime_context_projection` | `keep` | `get_runtime_context_projection` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 208 | method | `VNSAdapter.get_runtime_context_projection_sources` | `keep` | `get_runtime_context_projection_sources` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 213 | method | `VNSAdapter._scores` | `keep` | `_scores` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 225 | method | `VNSAdapter.get_state` | `keep` | `get_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 232 | method | `VNSAdapter.set_state` | `keep` | `set_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `benchmarks/compare_summary.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 9 | function | `_load_summary` | `keep` | `_load_summary` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 16 | function | `_as_float` | `keep` | `_as_float` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 23 | function | `_as_int` | `keep` | `_as_int` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 30 | function | `build_markdown_table` | `keep` | `build_markdown_table` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 50 | function | `main` | `keep` | `main` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `benchmarks/parallel_benchmark.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 20 | function | `_ensure_importable` | `keep` | `_ensure_importable` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 38 | class | `SphereProblem` | `keep` | `SphereProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 39 | method | `SphereProblem.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 45 | method | `SphereProblem.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 53 | class | `BenchmarkResult` | `keep` | `BenchmarkResult` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 62 | method | `BenchmarkResult.eval_per_s` | `keep` | `eval_per_s` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 66 | function | `run_once` | `keep` | `run_once` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 90 | function | `main` | `keep` | `main` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `bias/algorithmic/cma_es.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 20 | class | `CMAESBias` | `keep` | `CMAESBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 44 | method | `CMAESBias.__post_init__` | `keep` | `__post_init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 47 | method | `CMAESBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 69 | method | `CMAESBias._get_array` | `keep` | `_get_array` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 77 | method | `CMAESBias._get_scalar` | `keep` | `_get_scalar` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 86 | class | `AdaptiveCMAESBias` | `keep` | `AdaptiveCMAESBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 104 | method | `AdaptiveCMAESBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `bias/algorithmic/convergence.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 13 | class | `ConvergenceBias` | `keep` | `ConvergenceBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 27 | method | `ConvergenceBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 32 | method | `ConvergenceBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 48 | method | `ConvergenceBias._calculate_convergence_direction` | `keep` | `_calculate_convergence_direction` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 59 | class | `AdaptiveConvergenceBias` | `keep` | `AdaptiveConvergenceBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 74 | method | `AdaptiveConvergenceBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 85 | method | `AdaptiveConvergenceBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 103 | method | `AdaptiveConvergenceBias._calculate_improvement_rate` | `keep` | `_calculate_improvement_rate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 122 | method | `AdaptiveConvergenceBias._calculate_convergence_value` | `keep` | `_calculate_convergence_value` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 132 | class | `PrecisionBias` | `keep` | `PrecisionBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 147 | method | `PrecisionBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 151 | method | `PrecisionBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 160 | method | `PrecisionBias._is_promising_region` | `keep` | `_is_promising_region` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 171 | method | `PrecisionBias._calculate_precision_value` | `keep` | `_calculate_precision_value` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 177 | class | `LateStageConvergenceBias` | `keep` | `LateStageConvergenceBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 191 | method | `LateStageConvergenceBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 201 | method | `LateStageConvergenceBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 213 | method | `LateStageConvergenceBias._calculate_intensity` | `keep` | `_calculate_intensity` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 219 | class | `MultiStageConvergenceBias` | `keep` | `MultiStageConvergenceBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 233 | method | `MultiStageConvergenceBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 242 | method | `MultiStageConvergenceBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 255 | method | `MultiStageConvergenceBias._get_current_stage` | `keep` | `_get_current_stage` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 262 | method | `MultiStageConvergenceBias._calculate_strategy_bias` | `keep` | `_calculate_strategy_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `bias/algorithmic/diversity.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 18 | class | `DiversityBias` | `keep` | `DiversityBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 37 | method | `DiversityBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 52 | method | `DiversityBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 80 | method | `DiversityBias._calculate_distances` | `keep` | `_calculate_distances` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 105 | method | `DiversityBias.get_average_diversity` | `keep` | `get_average_diversity` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 117 | class | `AdaptiveDiversityBias` | `keep` | `AdaptiveDiversityBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 136 | method | `AdaptiveDiversityBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 155 | method | `AdaptiveDiversityBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 184 | method | `AdaptiveDiversityBias._calculate_population_diversity` | `keep` | `_calculate_population_diversity` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 210 | method | `AdaptiveDiversityBias._calculate_individual_distance` | `keep` | `_calculate_individual_distance` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 225 | class | `NicheDiversityBias` | `keep` | `NicheDiversityBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 244 | method | `NicheDiversityBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 263 | method | `NicheDiversityBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 287 | method | `NicheDiversityBias._find_niche` | `keep` | `_find_niche` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 303 | method | `NicheDiversityBias.update_niches` | `keep` | `update_niches` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 318 | class | `CrowdingDistanceBias` | `keep` | `CrowdingDistanceBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 337 | method | `CrowdingDistanceBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 346 | method | `CrowdingDistanceBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 364 | method | `CrowdingDistanceBias._calculate_crowding_distance` | `keep` | `_calculate_crowding_distance` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 388 | class | `SharingFunctionBias` | `keep` | `SharingFunctionBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 407 | method | `SharingFunctionBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 420 | method | `SharingFunctionBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `bias/algorithmic/levy_flight.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 17 | class | `LevyFlightBias` | `keep` | `LevyFlightBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 36 | method | `LevyFlightBias.__post_init__` | `keep` | `__post_init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 39 | method | `LevyFlightBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `bias/algorithmic/pso.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 19 | class | `ParticleSwarmBias` | `keep` | `ParticleSwarmBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 44 | method | `ParticleSwarmBias.__post_init__` | `keep` | `__post_init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 47 | method | `ParticleSwarmBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 65 | method | `ParticleSwarmBias._get_best` | `keep` | `_get_best` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 74 | class | `AdaptivePSOBias` | `keep` | `AdaptivePSOBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 94 | method | `AdaptivePSOBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `bias/algorithmic/signal_driven/robustness.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 24 | class | `RobustnessBias` | `keep` | `RobustnessBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 39 | method | `RobustnessBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 52 | method | `RobustnessBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 74 | method | `RobustnessBias._aggregate` | `keep` | `_aggregate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 82 | method | `RobustnessBias._to_1d_float` | `keep` | `_to_1d_float` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `bias/algorithmic/signal_driven/uncertainty_exploration.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 15 | class | `UncertaintyExplorationBias` | `keep` | `UncertaintyExplorationBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 40 | method | `UncertaintyExplorationBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `bias/algorithmic/tabu_search.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 18 | class | `TabuSearchBias` | `keep` | `TabuSearchBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 40 | method | `TabuSearchBias.__post_init__` | `keep` | `__post_init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 44 | method | `TabuSearchBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 59 | method | `TabuSearchBias._remember` | `keep` | `_remember` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `bias/algorithmic/template_algorithmic_bias.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 9 | class | `ExampleAlgorithmicBias` | `keep` | `ExampleAlgorithmicBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 19 | method | `ExampleAlgorithmicBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 32 | method | `ExampleAlgorithmicBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `bias/analytics.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 14 | class | `BiasAnalytics` | `keep` | `BiasAnalytics` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 26 | method | `BiasAnalytics.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 39 | method | `BiasAnalytics.generate_report` | `keep` | `generate_report` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 82 | method | `BiasAnalytics._collect_metadata` | `keep` | `_collect_metadata` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 93 | method | `BiasAnalytics._generate_summary` | `keep` | `_generate_summary` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 144 | method | `BiasAnalytics._collect_bias_stats` | `keep` | `_collect_bias_stats` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 154 | method | `BiasAnalytics._analyze_interactions` | `keep` | `_analyze_interactions` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 191 | method | `BiasAnalytics._generate_recommendations` | `keep` | `_generate_recommendations` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 245 | method | `BiasAnalytics._generate_markdown_report` | `keep` | `_generate_markdown_report` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 340 | method | `BiasAnalytics._format_bias_detail` | `keep` | `_format_bias_detail` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 388 | method | `BiasAnalytics._print_summary` | `keep` | `_print_summary` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `bias/core/base.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 18 | class | `BiasInterface` | `keep` | `BiasInterface` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 21 | method | `BiasInterface.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 24 | method | `BiasInterface.get_name` | `keep` | `get_name` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 27 | method | `BiasInterface.get_weight` | `keep` | `get_weight` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 30 | method | `BiasInterface.set_weight` | `keep` | `set_weight` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 33 | method | `BiasInterface.enable` | `keep` | `enable` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 36 | method | `BiasInterface.disable` | `keep` | `disable` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 40 | class | `OptimizationContext` | `keep` | `OptimizationContext` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 52 | method | `OptimizationContext.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 73 | method | `OptimizationContext.set_stuck_status` | `keep` | `set_stuck_status` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 82 | method | `OptimizationContext.set_convergence_status` | `keep` | `set_convergence_status` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 91 | method | `OptimizationContext.set_constraint_violation` | `keep` | `set_constraint_violation` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 101 | class | `BiasBase` | `keep` | `BiasBase` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 122 | method | `BiasBase.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 159 | method | `BiasBase.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 175 | method | `BiasBase.compute_with_tracking` | `keep` | `compute_with_tracking` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 218 | method | `BiasBase.get_context_contract` | `keep` | `get_context_contract` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 256 | method | `BiasBase._enforce_required_metrics` | `keep` | `_enforce_required_metrics` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 278 | method | `BiasBase._missing_required_metrics` | `keep` | `_missing_required_metrics` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 298 | method | `BiasBase.enable` | `keep` | `enable` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 303 | method | `BiasBase.disable` | `keep` | `disable` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 308 | method | `BiasBase.set_weight` | `keep` | `set_weight` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 318 | method | `BiasBase.get_weight` | `keep` | `get_weight` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 321 | method | `BiasBase.get_name` | `keep` | `get_name` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 324 | method | `BiasBase.register_param_change_callback` | `keep` | `register_param_change_callback` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 329 | method | `BiasBase._notify_param_change` | `keep` | `_notify_param_change` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 337 | method | `BiasBase.get_average_bias` | `keep` | `get_average_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 346 | method | `BiasBase.reset_statistics` | `keep` | `reset_statistics` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 354 | method | `BiasBase.finalize_generation` | `keep` | `finalize_generation` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 378 | method | `BiasBase.get_statistics` | `keep` | `get_statistics` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 406 | method | `BiasBase.__str__` | `keep` | `__str__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 411 | class | `AlgorithmicBias` | `keep` | `AlgorithmicBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 437 | method | `AlgorithmicBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 458 | method | `AlgorithmicBias.is_adaptive` | `keep` | `is_adaptive` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 467 | method | `AlgorithmicBias.reset_to_initial_weight` | `keep` | `reset_to_initial_weight` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 472 | class | `DomainBias` | `keep` | `DomainBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 491 | method | `DomainBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 511 | method | `DomainBias.is_mandatory` | `keep` | `is_mandatory` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 522 | class | `BiasManager` | `keep` | `BiasManager` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 529 | method | `BiasManager.add_bias` | `keep` | `add_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 538 | method | `BiasManager.remove_bias` | `keep` | `remove_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 550 | method | `BiasManager.compute_total_bias` | `keep` | `compute_total_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 563 | method | `BiasManager.get_bias` | `keep` | `get_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 577 | function | `create_bias` | `keep` | `create_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `bias/core/manager.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 25 | class | `BiasManagerMixin` | `keep` | `BiasManagerMixin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 35 | method | `BiasManagerMixin.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 38 | method | `BiasManagerMixin.add_bias` | `keep` | `add_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 57 | method | `BiasManagerMixin.remove_bias` | `keep` | `remove_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 72 | method | `BiasManagerMixin.get_bias` | `keep` | `get_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 84 | method | `BiasManagerMixin.list_biases` | `keep` | `list_biases` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 93 | method | `BiasManagerMixin.enable_all` | `keep` | `enable_all` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 98 | method | `BiasManagerMixin.disable_all` | `keep` | `disable_all` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 103 | method | `BiasManagerMixin.get_enabled_biases` | `keep` | `get_enabled_biases` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 112 | method | `BiasManagerMixin.get_bias_statistics` | `keep` | `get_bias_statistics` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 132 | class | `AlgorithmicBiasManager` | `keep` | `AlgorithmicBiasManager` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 145 | method | `AlgorithmicBiasManager.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 151 | method | `AlgorithmicBiasManager.add_algorithmic_bias` | `keep` | `add_algorithmic_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 168 | method | `AlgorithmicBiasManager.compute_total_bias` | `keep` | `compute_total_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 186 | method | `AlgorithmicBiasManager.adapt_weights` | `keep` | `adapt_weights` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 217 | method | `AlgorithmicBiasManager.adjust_exploration_weights` | `keep` | `adjust_exploration_weights` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 229 | method | `AlgorithmicBiasManager.adjust_convergence_weights` | `keep` | `adjust_convergence_weights` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 241 | method | `AlgorithmicBiasManager.reset_adaptive_weights` | `keep` | `reset_adaptive_weights` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 248 | class | `DomainBiasManager` | `keep` | `DomainBiasManager` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 261 | method | `DomainBiasManager.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 267 | method | `DomainBiasManager.add_domain_bias` | `keep` | `add_domain_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 284 | method | `DomainBiasManager.compute_total_bias` | `keep` | `compute_total_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 312 | method | `DomainBiasManager.get_mandatory_biases` | `keep` | `get_mandatory_biases` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 322 | method | `DomainBiasManager.ensure_mandatory_enabled` | `keep` | `ensure_mandatory_enabled` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 327 | method | `DomainBiasManager.compute_constraint_violation_rate` | `keep` | `compute_constraint_violation_rate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 341 | class | `UniversalBiasManager` | `keep` | `UniversalBiasManager` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 354 | method | `UniversalBiasManager.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 363 | method | `UniversalBiasManager.add_algorithmic_bias` | `keep` | `add_algorithmic_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 372 | method | `UniversalBiasManager.add_domain_bias` | `keep` | `add_domain_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 381 | method | `UniversalBiasManager.compute_total_bias` | `keep` | `compute_total_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 432 | method | `UniversalBiasManager.compute_total_algorithmic_bias` | `keep` | `compute_total_algorithmic_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 443 | method | `UniversalBiasManager.get_comprehensive_statistics` | `keep` | `get_comprehensive_statistics` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 463 | method | `UniversalBiasManager.save_configuration` | `keep` | `save_configuration` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 497 | method | `UniversalBiasManager.load_configuration` | `keep` | `load_configuration` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 527 | method | `UniversalBiasManager.reset_all_statistics` | `keep` | `reset_all_statistics` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 541 | method | `UniversalBiasManager._get_timestamp` | `keep` | `_get_timestamp` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 546 | method | `UniversalBiasManager.__str__` | `keep` | `__str__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |

### `bias/core/registry.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 14 | class | `BiasRegistry` | `keep` | `BiasRegistry` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 21 | method | `BiasRegistry.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 27 | method | `BiasRegistry.register_algorithmic_bias` | `keep` | `register_algorithmic_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 51 | method | `BiasRegistry.register_domain_bias` | `keep` | `register_domain_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 75 | method | `BiasRegistry.register_bias_factory` | `keep` | `register_bias_factory` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 96 | method | `BiasRegistry.create_algorithmic_bias` | `keep` | `create_algorithmic_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 117 | method | `BiasRegistry.create_domain_bias` | `keep` | `create_domain_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 138 | method | `BiasRegistry.create_bias_from_factory` | `keep` | `create_bias_from_factory` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 159 | method | `BiasRegistry.list_algorithmic_biases` | `keep` | `list_algorithmic_biases` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 163 | method | `BiasRegistry.list_domain_biases` | `keep` | `list_domain_biases` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 167 | method | `BiasRegistry.list_bias_factories` | `keep` | `list_bias_factories` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 171 | method | `BiasRegistry.list_categories` | `keep` | `list_categories` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 175 | method | `BiasRegistry.get_biases_in_category` | `keep` | `get_biases_in_category` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 179 | method | `BiasRegistry.get_bias_info` | `keep` | `get_bias_info` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 209 | method | `BiasRegistry.get_bias_documentation` | `keep` | `get_bias_documentation` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 214 | method | `BiasRegistry.search_biases` | `keep` | `search_biases` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 240 | method | `BiasRegistry.validate_bias_registration` | `keep` | `validate_bias_registration` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 291 | function | `get_bias_registry` | `keep` | `get_bias_registry` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 296 | function | `register_algorithmic_bias` | `keep` | `register_algorithmic_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 308 | function | `register_algorithmic_bias.decorator` | `keep` | `decorator` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 314 | function | `register_domain_bias` | `keep` | `register_domain_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 326 | function | `register_domain_bias.decorator` | `keep` | `decorator` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 332 | function | `register_bias_factory` | `keep` | `register_bias_factory` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 344 | function | `register_bias_factory.decorator` | `keep` | `decorator` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `bias/domain/callable_bias.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 19 | class | `CallableBias` | `keep` | `CallableBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 44 | method | `CallableBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 57 | method | `CallableBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 65 | method | `CallableBias._call_func` | `keep` | `_call_func` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 95 | method | `CallableBias._coerce_value` | `keep` | `_coerce_value` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `bias/domain/constraint.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 18 | class | `ConstraintBias` | `keep` | `ConstraintBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 38 | method | `ConstraintBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 53 | method | `ConstraintBias.add_constraint` | `keep` | `add_constraint` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 79 | method | `ConstraintBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 115 | method | `ConstraintBias.get_violation_statistics` | `keep` | `get_violation_statistics` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 141 | class | `FeasibilityBias` | `keep` | `FeasibilityBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 161 | method | `FeasibilityBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 179 | method | `FeasibilityBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 205 | class | `PreferenceBias` | `keep` | `PreferenceBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 226 | method | `PreferenceBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 244 | method | `PreferenceBias.add_preference_function` | `keep` | `add_preference_function` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 253 | method | `PreferenceBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 292 | class | `RuleBasedBias` | `keep` | `RuleBasedBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 312 | method | `RuleBasedBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 324 | method | `RuleBasedBias.add_rule` | `keep` | `add_rule` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 357 | method | `RuleBasedBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 394 | method | `RuleBasedBias.get_rule_statistics` | `keep` | `get_rule_statistics` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `bias/domain/dynamic_penalty.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 19 | function | `_coerce_value` | `keep` | `_coerce_value` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 38 | function | `_call_func` | `keep` | `_call_func` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 69 | class | `DynamicPenaltyBias` | `keep` | `DynamicPenaltyBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 94 | method | `DynamicPenaltyBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 121 | method | `DynamicPenaltyBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 126 | method | `DynamicPenaltyBias._schedule_scale` | `keep` | `_schedule_scale` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 160 | method | `DynamicPenaltyBias._resolve_max_generations` | `keep` | `_resolve_max_generations` | `high` | `-` | 该 resolve_* 属于推断/合并/派生语义，符合规范保留。 |

### `bias/domain/engineering.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 13 | class | `EngineeringDesignBias` | `keep` | `EngineeringDesignBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 26 | method | `EngineeringDesignBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 41 | method | `EngineeringDesignBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 54 | class | `SafetyBias` | `keep` | `SafetyBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 66 | method | `SafetyBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 69 | method | `SafetyBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 75 | class | `ManufacturingBias` | `keep` | `ManufacturingBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 87 | method | `ManufacturingBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 90 | method | `ManufacturingBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `bias/domain/risk_bias.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 15 | class | `RiskBias` | `keep` | `RiskBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 43 | method | `RiskBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 60 | method | `RiskBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 84 | method | `RiskBias._coerce_vector` | `keep` | `_coerce_vector` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 99 | method | `RiskBias._alpha_to_k` | `keep` | `_alpha_to_k` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `bias/domain/scheduling.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 12 | class | `SchedulingBias` | `keep` | `SchedulingBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 24 | method | `SchedulingBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 27 | method | `SchedulingBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 33 | class | `ResourceConstraintBias` | `keep` | `ResourceConstraintBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 45 | method | `ResourceConstraintBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 48 | method | `ResourceConstraintBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 54 | class | `TimeWindowBias` | `keep` | `TimeWindowBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 66 | method | `TimeWindowBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 69 | method | `TimeWindowBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `bias/domain/structure_prior.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 15 | class | `StructurePriorBias` | `keep` | `StructurePriorBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 37 | method | `StructurePriorBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 54 | method | `StructurePriorBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 71 | method | `StructurePriorBias._pair_penalty` | `keep` | `_pair_penalty` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 80 | method | `StructurePriorBias._group_variance` | `keep` | `_group_variance` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `bias/domain/template_domain_bias.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 9 | class | `ExampleDomainBias` | `keep` | `ExampleDomainBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 19 | method | `ExampleDomainBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 33 | method | `ExampleDomainBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `bias/library.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 16 | class | `_GenericAlgorithmicBias` | `keep` | `_GenericAlgorithmicBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 27 | method | `_GenericAlgorithmicBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 31 | class | `_GenericDomainBias` | `keep` | `_GenericDomainBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 41 | method | `_GenericDomainBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 45 | function | `_collect_biases` | `keep` | `_collect_biases` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 53 | function | `_filter_kwargs` | `keep` | `_filter_kwargs` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 60 | class | `BiasFactory` | `keep` | `BiasFactory` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 79 | method | `BiasFactory._ensure_registry` | `keep` | `_ensure_registry` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 86 | method | `BiasFactory.list_available_algorithmic_biases` | `keep` | `list_available_algorithmic_biases` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 94 | method | `BiasFactory.list_available_domain_biases` | `keep` | `list_available_domain_biases` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 102 | method | `BiasFactory.create_algorithmic_bias` | `keep` | `create_algorithmic_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 114 | method | `BiasFactory.create_domain_bias` | `keep` | `create_domain_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 126 | class | `BiasComposer` | `keep` | `BiasComposer` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 129 | method | `BiasComposer.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 132 | method | `BiasComposer.add_algorithmic_bias_from_config` | `keep` | `add_algorithmic_bias_from_config` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 137 | method | `BiasComposer.add_domain_bias_from_config` | `keep` | `add_domain_bias_from_config` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 142 | method | `BiasComposer.build` | `keep` | `build` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 146 | function | `create_bias_manager_from_template` | `keep` | `create_bias_manager_from_template` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 178 | function | `quick_engineering_bias` | `keep` | `quick_engineering_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 182 | function | `quick_ml_bias` | `keep` | `quick_ml_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 186 | function | `quick_financial_bias` | `keep` | `quick_financial_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `bias/managers/adaptive_manager.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 17 | class | `OptimizationState` | `keep` | `OptimizationState` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 28 | class | `AdaptiveAlgorithmicManager` | `keep` | `AdaptiveAlgorithmicManager` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 31 | method | `AdaptiveAlgorithmicManager.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 63 | method | `AdaptiveAlgorithmicManager.add_bias` | `keep` | `add_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 70 | method | `AdaptiveAlgorithmicManager.update_state` | `keep` | `update_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 81 | method | `AdaptiveAlgorithmicManager._compute_optimization_state` | `keep` | `_compute_optimization_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 110 | method | `AdaptiveAlgorithmicManager._adapt_biases` | `keep` | `_adapt_biases` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 136 | method | `AdaptiveAlgorithmicManager._adapt_when_stuck` | `keep` | `_adapt_when_stuck` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 158 | method | `AdaptiveAlgorithmicManager._adapt_for_diversity` | `keep` | `_adapt_for_diversity` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 172 | method | `AdaptiveAlgorithmicManager._adapt_for_acceleration` | `keep` | `_adapt_for_acceleration` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 186 | method | `AdaptiveAlgorithmicManager._balance_exploration_exploitation` | `keep` | `_balance_exploration_exploitation` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 208 | method | `AdaptiveAlgorithmicManager._resolve_biases` | `keep` | `_resolve_biases` | `high` | `-` | 该 resolve_* 属于推断/合并/派生语义，符合规范保留。 |
| 227 | method | `AdaptiveAlgorithmicManager._compute_diversity` | `keep` | `_compute_diversity` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 256 | method | `AdaptiveAlgorithmicManager._compute_convergence_rate` | `keep` | `_compute_convergence_rate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 268 | method | `AdaptiveAlgorithmicManager._compute_improvement_rate` | `keep` | `_compute_improvement_rate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 285 | method | `AdaptiveAlgorithmicManager._compute_population_density` | `keep` | `_compute_population_density` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 309 | method | `AdaptiveAlgorithmicManager._compute_exploration_exploitation_ratio` | `keep` | `_compute_exploration_exploitation_ratio` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 328 | method | `AdaptiveAlgorithmicManager.get_adaptation_history` | `keep` | `get_adaptation_history` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `bias/managers/analytics.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 28 | class | `MetricType` | `keep` | `MetricType` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 38 | class | `BiasEffectivenessMetrics` | `keep` | `BiasEffectivenessMetrics` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 53 | class | `BiasEffectivenessAnalyzer` | `keep` | `BiasEffectivenessAnalyzer` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 56 | method | `BiasEffectivenessAnalyzer.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 69 | method | `BiasEffectivenessAnalyzer.evaluate_bias` | `keep` | `evaluate_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 98 | method | `BiasEffectivenessAnalyzer._compute_convergence_improvement` | `keep` | `_compute_convergence_improvement` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 111 | method | `BiasEffectivenessAnalyzer._compute_solution_quality_improvement` | `keep` | `_compute_solution_quality_improvement` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 126 | method | `BiasEffectivenessAnalyzer._compute_diversity_score` | `keep` | `_compute_diversity_score` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 134 | method | `BiasEffectivenessAnalyzer._compute_computational_overhead` | `keep` | `_compute_computational_overhead` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 147 | method | `BiasEffectivenessAnalyzer._compute_robustness_score` | `keep` | `_compute_robustness_score` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 158 | method | `BiasEffectivenessAnalyzer._compute_consistency_score` | `keep` | `_compute_consistency_score` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 166 | method | `BiasEffectivenessAnalyzer._compute_statistical_significance` | `keep` | `_compute_statistical_significance` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 172 | method | `BiasEffectivenessAnalyzer._extract_performance_history` | `keep` | `_extract_performance_history` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 180 | method | `BiasEffectivenessAnalyzer._find_convergence_generation` | `keep` | `_find_convergence_generation` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 194 | method | `BiasEffectivenessAnalyzer._safe_min` | `keep` | `_safe_min` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 202 | method | `BiasEffectivenessAnalyzer.plot_bias_comparison` | `keep` | `plot_bias_comparison` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 263 | method | `BiasEffectivenessAnalyzer._compute_overall_score` | `keep` | `_compute_overall_score` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 286 | method | `BiasEffectivenessAnalyzer.export_metrics_to_csv` | `keep` | `export_metrics_to_csv` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `bias/managers/meta_learning_selector.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 37 | class | `ProblemFeatures` | `keep` | `ProblemFeatures` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 62 | class | `BiasRecommendation` | `keep` | `BiasRecommendation` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 72 | class | `ProblemFeatureExtractor` | `keep` | `ProblemFeatureExtractor` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 75 | method | `ProblemFeatureExtractor.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 84 | method | `ProblemFeatureExtractor.extract_features` | `keep` | `extract_features` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 117 | method | `ProblemFeatureExtractor._infer_problem_type` | `keep` | `_infer_problem_type` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 130 | method | `ProblemFeatureExtractor._estimate_complexity_features` | `keep` | `_estimate_complexity_features` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 140 | method | `ProblemFeatureExtractor._estimate_scale_features` | `keep` | `_estimate_scale_features` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 156 | method | `ProblemFeatureExtractor._estimate_computation_features` | `keep` | `_estimate_computation_features` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 164 | class | `MetaLearningBiasSelector` | `keep` | `MetaLearningBiasSelector` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 167 | method | `MetaLearningBiasSelector.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 197 | method | `MetaLearningBiasSelector.add_historical_data` | `keep` | `add_historical_data` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 213 | method | `MetaLearningBiasSelector.train_models` | `keep` | `train_models` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 267 | method | `MetaLearningBiasSelector.recommend_biases` | `keep` | `recommend_biases` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 328 | method | `MetaLearningBiasSelector._prepare_training_data` | `keep` | `_prepare_training_data` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 369 | method | `MetaLearningBiasSelector._extract_feature_vector` | `keep` | `_extract_feature_vector` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 386 | method | `MetaLearningBiasSelector._predict_bias_effects` | `keep` | `_predict_bias_effects` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 417 | method | `MetaLearningBiasSelector._get_bias_type_modifier` | `keep` | `_get_bias_type_modifier` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 430 | method | `MetaLearningBiasSelector._select_top_biases` | `keep` | `_select_top_biases` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 449 | method | `MetaLearningBiasSelector._compute_bias_weights` | `keep` | `_compute_bias_weights` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 487 | method | `MetaLearningBiasSelector._generate_reasoning` | `keep` | `_generate_reasoning` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 524 | method | `MetaLearningBiasSelector._compute_confidence` | `keep` | `_compute_confidence` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 544 | method | `MetaLearningBiasSelector._compute_problem_similarity` | `keep` | `_compute_problem_similarity` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 563 | method | `MetaLearningBiasSelector._estimate_expected_improvement` | `keep` | `_estimate_expected_improvement` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 581 | method | `MetaLearningBiasSelector._generate_alternatives` | `keep` | `_generate_alternatives` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 618 | method | `MetaLearningBiasSelector._heuristic_recommendation` | `keep` | `_heuristic_recommendation` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 657 | method | `MetaLearningBiasSelector._get_best_bias_metrics_for_problem` | `keep` | `_get_best_bias_metrics_for_problem` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 671 | method | `MetaLearningBiasSelector._compute_overall_score` | `keep` | `_compute_overall_score` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 692 | method | `MetaLearningBiasSelector._models_trained` | `keep` | `_models_trained` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 702 | method | `MetaLearningBiasSelector._save_models` | `keep` | `_save_models` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 723 | method | `MetaLearningBiasSelector.load_models` | `keep` | `load_models` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 746 | method | `MetaLearningBiasSelector.export_database` | `keep` | `export_database` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 793 | method | `MetaLearningBiasSelector.import_database` | `keep` | `import_database` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `bias/specialized/bayesian_biases.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 12 | class | `SimpleBayesianOptimizer` | `keep` | `SimpleBayesianOptimizer` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 15 | method | `SimpleBayesianOptimizer.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 22 | method | `SimpleBayesianOptimizer.observe` | `keep` | `observe` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 27 | method | `SimpleBayesianOptimizer.reset` | `keep` | `reset` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 38 | class | `BayesianGuidanceBias` | `keep` | `BayesianGuidanceBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 50 | method | `BayesianGuidanceBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 73 | method | `BayesianGuidanceBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 90 | method | `BayesianGuidanceBias.apply` | `keep` | `apply` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 106 | method | `BayesianGuidanceBias._update_buffer` | `keep` | `_update_buffer` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 135 | method | `BayesianGuidanceBias._update_model` | `keep` | `_update_model` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 146 | method | `BayesianGuidanceBias._update_model_simple` | `keep` | `_update_model_simple` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 152 | method | `BayesianGuidanceBias._update_model_with_real_eval` | `keep` | `_update_model_with_real_eval` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 164 | method | `BayesianGuidanceBias._try_update_with_nsga_surrogate` | `keep` | `_try_update_with_nsga_surrogate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 225 | method | `BayesianGuidanceBias._try_update_with_nsga_data` | `keep` | `_try_update_with_nsga_data` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 246 | method | `BayesianGuidanceBias._update_with_evaluation_function` | `keep` | `_update_with_evaluation_function` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 269 | method | `BayesianGuidanceBias._predict_improvement` | `keep` | `_predict_improvement` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 293 | method | `BayesianGuidanceBias._adaptive_weight_adjustment` | `keep` | `_adaptive_weight_adjustment` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 305 | class | `BayesianExplorationBias` | `keep` | `BayesianExplorationBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 315 | method | `BayesianExplorationBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 324 | method | `BayesianExplorationBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 340 | method | `BayesianExplorationBias.apply` | `keep` | `apply` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 358 | method | `BayesianExplorationBias._collect_data` | `keep` | `_collect_data` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 367 | method | `BayesianExplorationBias._collect_data_simple` | `keep` | `_collect_data_simple` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 376 | method | `BayesianExplorationBias._predict_uncertainty` | `keep` | `_predict_uncertainty` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 390 | class | `BayesianConvergenceBias` | `keep` | `BayesianConvergenceBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 401 | method | `BayesianConvergenceBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 409 | method | `BayesianConvergenceBias.apply` | `keep` | `apply` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 419 | method | `BayesianConvergenceBias._check_convergence` | `keep` | `_check_convergence` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 427 | method | `BayesianConvergenceBias._predict_optimal_direction` | `keep` | `_predict_optimal_direction` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 455 | function | `create_bayesian_guidance_bias` | `keep` | `create_bayesian_guidance_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 460 | function | `create_bayesian_exploration_bias` | `keep` | `create_bayesian_exploration_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 465 | function | `create_bayesian_convergence_bias` | `keep` | `create_bayesian_convergence_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 470 | function | `create_bayesian_suite` | `keep` | `create_bayesian_suite` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `bias/specialized/engineering.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 31 | class | `EngineeringPrecisionBias` | `keep` | `EngineeringPrecisionBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 54 | method | `EngineeringPrecisionBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 72 | method | `EngineeringPrecisionBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 111 | method | `EngineeringPrecisionBias._estimate_numerical_precision` | `keep` | `_estimate_numerical_precision` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 146 | method | `EngineeringPrecisionBias._adjust_precision_requirement` | `keep` | `_adjust_precision_requirement` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 173 | class | `EngineeringConstraintBias` | `keep` | `EngineeringConstraintBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 192 | method | `EngineeringConstraintBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 209 | method | `EngineeringConstraintBias.add_engineering_constraint` | `keep` | `add_engineering_constraint` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 242 | method | `EngineeringConstraintBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 285 | method | `EngineeringConstraintBias.get_constraint_status` | `keep` | `get_constraint_status` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 313 | class | `EngineeringRobustnessBias` | `keep` | `EngineeringRobustnessBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 333 | method | `EngineeringRobustnessBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 350 | method | `EngineeringRobustnessBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 404 | method | `EngineeringRobustnessBias._calculate_robustness_metric` | `keep` | `_calculate_robustness_metric` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 445 | function | `create_engineering_bias_suite` | `keep` | `create_engineering_bias_suite` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 483 | function | `create_engineering_constraint_bias` | `keep` | `create_engineering_constraint_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `bias/specialized/graph/abstract.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 27 | class | `GraphType` | `keep` | `GraphType` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 40 | class | `SolutionEncoding` | `keep` | `SolutionEncoding` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 51 | class | `GraphMetadata` | `keep` | `GraphMetadata` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 61 | class | `ValidationResult` | `keep` | `ValidationResult` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 68 | method | `ValidationResult.__post_init__` | `keep` | `__post_init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 73 | class | `AbstractGraphProblem` | `keep` | `AbstractGraphProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 80 | method | `AbstractGraphProblem.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 90 | method | `AbstractGraphProblem.get_name` | `keep` | `get_name` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 95 | method | `AbstractGraphProblem.get_encoding` | `keep` | `get_encoding` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 100 | method | `AbstractGraphProblem.validate_solution` | `keep` | `validate_solution` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 105 | method | `AbstractGraphProblem.decode_solution` | `keep` | `decode_solution` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 110 | method | `AbstractGraphProblem.evaluate_solution` | `keep` | `evaluate_solution` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 115 | class | `PermutationGraphProblem` | `keep` | `PermutationGraphProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 122 | method | `PermutationGraphProblem.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 127 | method | `PermutationGraphProblem.get_encoding` | `keep` | `get_encoding` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 130 | method | `PermutationGraphProblem.validate_permutation_constraints` | `keep` | `validate_permutation_constraints` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 171 | method | `PermutationGraphProblem.decode_solution` | `keep` | `decode_solution` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 180 | class | `TSPProblem` | `keep` | `TSPProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 187 | method | `TSPProblem.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 193 | method | `TSPProblem.get_name` | `keep` | `get_name` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 196 | method | `TSPProblem.validate_solution` | `keep` | `validate_solution` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 212 | method | `TSPProblem.evaluate_solution` | `keep` | `evaluate_solution` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 229 | class | `HamiltonianPathProblem` | `keep` | `HamiltonianPathProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 234 | method | `HamiltonianPathProblem.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 240 | method | `HamiltonianPathProblem.get_name` | `keep` | `get_name` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 243 | method | `HamiltonianPathProblem.validate_solution` | `keep` | `validate_solution` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 270 | method | `HamiltonianPathProblem.evaluate_solution` | `keep` | `evaluate_solution` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 278 | class | `BinaryEdgesGraphProblem` | `keep` | `BinaryEdgesGraphProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 285 | method | `BinaryEdgesGraphProblem.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 291 | method | `BinaryEdgesGraphProblem.get_encoding` | `keep` | `get_encoding` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 294 | method | `BinaryEdgesGraphProblem.decode_edges` | `keep` | `decode_edges` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 307 | method | `BinaryEdgesGraphProblem.decode_solution` | `keep` | `decode_solution` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 311 | class | `SpanningTreeProblem` | `keep` | `SpanningTreeProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 316 | method | `SpanningTreeProblem.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 327 | method | `SpanningTreeProblem.get_name` | `keep` | `get_name` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 330 | method | `SpanningTreeProblem.validate_solution` | `keep` | `validate_solution` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 363 | method | `SpanningTreeProblem._is_connected` | `keep` | `_is_connected` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 385 | method | `SpanningTreeProblem._has_cycle` | `keep` | `_has_cycle` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 389 | method | `SpanningTreeProblem._has_cycle.find` | `keep` | `find` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 395 | method | `SpanningTreeProblem._has_cycle.union` | `keep` | `union` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 408 | method | `SpanningTreeProblem.evaluate_solution` | `keep` | `evaluate_solution` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 419 | class | `PartitionGraphProblem` | `keep` | `PartitionGraphProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 426 | method | `PartitionGraphProblem.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 431 | method | `PartitionGraphProblem.get_encoding` | `keep` | `get_encoding` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 434 | method | `PartitionGraphProblem.decode_partition` | `keep` | `decode_partition` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 440 | method | `PartitionGraphProblem.decode_solution` | `keep` | `decode_solution` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 444 | class | `GraphColoringProblem` | `keep` | `GraphColoringProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 449 | method | `GraphColoringProblem.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 457 | method | `GraphColoringProblem.get_name` | `keep` | `get_name` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 460 | method | `GraphColoringProblem.validate_solution` | `keep` | `validate_solution` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 492 | method | `GraphColoringProblem.evaluate_solution` | `keep` | `evaluate_solution` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 503 | class | `GraphProblemFactory` | `keep` | `GraphProblemFactory` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 511 | method | `GraphProblemFactory.create_tsp` | `keep` | `create_tsp` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 516 | method | `GraphProblemFactory.create_spanning_tree` | `keep` | `create_spanning_tree` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 521 | method | `GraphProblemFactory.create_graph_coloring` | `keep` | `create_graph_coloring` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 526 | method | `GraphProblemFactory.create_hamiltonian_path` | `keep` | `create_hamiltonian_path` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 531 | method | `GraphProblemFactory.get_available_problems` | `keep` | `get_available_problems` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 542 | class | `CompositeGraphProblem` | `keep` | `CompositeGraphProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 549 | method | `CompositeGraphProblem.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 559 | method | `CompositeGraphProblem.get_name` | `keep` | `get_name` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 562 | method | `CompositeGraphProblem.get_encoding` | `keep` | `get_encoding` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 566 | method | `CompositeGraphProblem.validate_solution` | `keep` | `validate_solution` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 579 | method | `CompositeGraphProblem.decode_solution` | `keep` | `decode_solution` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 583 | method | `CompositeGraphProblem.evaluate_solution` | `keep` | `evaluate_solution` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 595 | method | `CompositeGraphProblem.add_subproblem` | `keep` | `add_subproblem` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `bias/specialized/graph/base.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 34 | class | `GraphStructure` | `keep` | `GraphStructure` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 52 | method | `GraphStructure.__post_init__` | `keep` | `__post_init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 59 | method | `GraphStructure._build_adjacency_matrix_from_edges` | `keep` | `_build_adjacency_matrix_from_edges` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 67 | method | `GraphStructure._build_edge_list_from_edges` | `keep` | `_build_edge_list_from_edges` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 76 | class | `GraphUtils` | `keep` | `GraphUtils` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 80 | method | `GraphUtils.compute_graph_properties` | `keep` | `compute_graph_properties` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 102 | method | `GraphUtils._compute_clustering_coefficient` | `keep` | `_compute_clustering_coefficient` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 134 | method | `GraphUtils.extract_subgraph` | `keep` | `extract_subgraph` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 156 | class | `GraphBias` | `keep` | `GraphBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 166 | method | `GraphBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 171 | method | `GraphBias.encode_solution_to_graph` | `keep` | `encode_solution_to_graph` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 176 | class | `ConnectivityBias` | `keep` | `ConnectivityBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 186 | method | `ConnectivityBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 189 | method | `ConnectivityBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 214 | class | `SparsityBias` | `keep` | `SparsityBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 224 | method | `SparsityBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 229 | method | `SparsityBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 241 | class | `DegreeDistributionBias` | `keep` | `DegreeDistributionBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 251 | method | `DegreeDistributionBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 256 | method | `DegreeDistributionBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 285 | method | `DegreeDistributionBias._compute_gini_coefficient` | `keep` | `_compute_gini_coefficient` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 297 | class | `ShortestPathBias` | `keep` | `ShortestPathBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 307 | method | `ShortestPathBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 328 | method | `ShortestPathBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 358 | class | `MaxFlowBias` | `keep` | `MaxFlowBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 368 | method | `MaxFlowBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 374 | method | `MaxFlowBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 400 | class | `GraphColoringBias` | `keep` | `GraphColoringBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 410 | method | `GraphColoringBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 415 | method | `GraphColoringBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 433 | method | `GraphColoringBias.encode_solution_to_graph` | `keep` | `encode_solution_to_graph` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 439 | class | `CommunityDetectionBias` | `keep` | `CommunityDetectionBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 449 | method | `CommunityDetectionBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 454 | method | `CommunityDetectionBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 468 | method | `CommunityDetectionBias._compute_modularity` | `keep` | `_compute_modularity` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 490 | class | `GraphBiasFactory` | `keep` | `GraphBiasFactory` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 494 | method | `GraphBiasFactory.create_bias` | `keep` | `create_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 513 | method | `GraphBiasFactory.get_available_biases` | `keep` | `get_available_biases` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `bias/specialized/graph/constraints.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 32 | class | `GraphConstraintViolation` | `keep` | `GraphConstraintViolation` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 38 | class | `ValidationResult` | `keep` | `ValidationResult` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 45 | method | `ValidationResult.__post_init__` | `keep` | `__post_init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 51 | class | `GraphConstraintBias` | `keep` | `GraphConstraintBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 65 | method | `GraphConstraintBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 69 | method | `GraphConstraintBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 81 | method | `GraphConstraintBias.validate_constraints` | `keep` | `validate_constraints` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 90 | class | `TSPConstraintBias` | `keep` | `TSPConstraintBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 107 | method | `TSPConstraintBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 111 | method | `TSPConstraintBias.validate_constraints` | `keep` | `validate_constraints` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 163 | method | `TSPConstraintBias._extract_tour_from_binary` | `keep` | `_extract_tour_from_binary` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 192 | class | `PathConstraintBias` | `keep` | `PathConstraintBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 209 | method | `PathConstraintBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 217 | method | `PathConstraintBias.validate_constraints` | `keep` | `validate_constraints` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 267 | method | `PathConstraintBias._extract_path` | `keep` | `_extract_path` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 277 | method | `PathConstraintBias._is_connected` | `keep` | `_is_connected` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 283 | class | `TreeConstraintBias` | `keep` | `TreeConstraintBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 300 | method | `TreeConstraintBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 304 | method | `TreeConstraintBias.validate_constraints` | `keep` | `validate_constraints` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 346 | method | `TreeConstraintBias._extract_edges` | `keep` | `_extract_edges` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 359 | method | `TreeConstraintBias._is_connected` | `keep` | `_is_connected` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 381 | method | `TreeConstraintBias._has_cycle` | `keep` | `_has_cycle` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 386 | method | `TreeConstraintBias._has_cycle.find` | `keep` | `find` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 392 | method | `TreeConstraintBias._has_cycle.union` | `keep` | `union` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 406 | class | `GraphColoringConstraintBias` | `keep` | `GraphColoringConstraintBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 422 | method | `GraphColoringConstraintBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 428 | method | `GraphColoringConstraintBias.validate_constraints` | `keep` | `validate_constraints` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 471 | class | `MatchingConstraintBias` | `keep` | `MatchingConstraintBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 486 | method | `MatchingConstraintBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 491 | method | `MatchingConstraintBias.validate_constraints` | `keep` | `validate_constraints` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 531 | method | `MatchingConstraintBias._extract_edges` | `keep` | `_extract_edges` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 545 | class | `HamiltonianPathConstraintBias` | `keep` | `HamiltonianPathConstraintBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 561 | method | `HamiltonianPathConstraintBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 566 | method | `HamiltonianPathConstraintBias.validate_constraints` | `keep` | `validate_constraints` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 618 | method | `HamiltonianPathConstraintBias._extract_path` | `keep` | `_extract_path` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 623 | method | `HamiltonianPathConstraintBias._are_adjacent` | `keep` | `_are_adjacent` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 629 | class | `GraphConstraintFactory` | `keep` | `GraphConstraintFactory` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 633 | method | `GraphConstraintFactory.create_constraint` | `keep` | `create_constraint` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 651 | method | `GraphConstraintFactory.get_available_constraints` | `keep` | `get_available_constraints` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 664 | class | `CompositeGraphConstraintBias` | `keep` | `CompositeGraphConstraintBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 678 | method | `CompositeGraphConstraintBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 682 | method | `CompositeGraphConstraintBias.validate_constraints` | `keep` | `validate_constraints` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 691 | method | `CompositeGraphConstraintBias.add_constraint` | `keep` | `add_constraint` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `bias/specialized/local_search.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 26 | class | `GradientDescentBias` | `keep` | `GradientDescentBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 46 | method | `GradientDescentBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 69 | method | `GradientDescentBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 147 | method | `GradientDescentBias._compute_gradient` | `keep` | `_compute_gradient` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 177 | class | `NewtonMethodBias` | `keep` | `NewtonMethodBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 188 | method | `NewtonMethodBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 199 | method | `NewtonMethodBias.apply` | `keep` | `apply` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 241 | method | `NewtonMethodBias._update_bfgs_approx` | `keep` | `_update_bfgs_approx` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 253 | method | `NewtonMethodBias._compute_gradient` | `keep` | `_compute_gradient` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 267 | method | `NewtonMethodBias._compute_hessian` | `keep` | `_compute_hessian` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 290 | method | `NewtonMethodBias._damped_newton_step` | `keep` | `_damped_newton_step` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 308 | class | `LineSearchBias` | `keep` | `LineSearchBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 319 | method | `LineSearchBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 332 | method | `LineSearchBias.apply` | `keep` | `apply` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 351 | method | `LineSearchBias._line_search` | `keep` | `_line_search` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 362 | method | `LineSearchBias._armijo_line_search` | `keep` | `_armijo_line_search` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 382 | method | `LineSearchBias._wolfe_line_search` | `keep` | `_wolfe_line_search` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 419 | method | `LineSearchBias._compute_gradient` | `keep` | `_compute_gradient` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 434 | class | `TrustRegionBias` | `keep` | `TrustRegionBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 445 | method | `TrustRegionBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 458 | method | `TrustRegionBias.apply` | `keep` | `apply` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 495 | method | `TrustRegionBias._compute_gradient` | `keep` | `_compute_gradient` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 509 | method | `TrustRegionBias._compute_hessian` | `keep` | `_compute_hessian` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 529 | method | `TrustRegionBias._dogleg_step` | `keep` | `_dogleg_step` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 578 | class | `NelderMeadBias` | `keep` | `NelderMeadBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 589 | method | `NelderMeadBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 601 | method | `NelderMeadBias.apply` | `keep` | `apply` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 614 | method | `NelderMeadBias._initialize_simplex` | `keep` | `_initialize_simplex` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 628 | method | `NelderMeadBias._nelder_mead_step` | `keep` | `_nelder_mead_step` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 688 | class | `QuasiNewtonBias` | `keep` | `QuasiNewtonBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 699 | method | `QuasiNewtonBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 708 | method | `QuasiNewtonBias.apply` | `keep` | `apply` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 737 | method | `QuasiNewtonBias._update_quasi_newton` | `keep` | `_update_quasi_newton` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 758 | method | `QuasiNewtonBias._compute_gradient` | `keep` | `_compute_gradient` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 775 | function | `create_gradient_descent_suite` | `keep` | `create_gradient_descent_suite` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 783 | function | `create_newton_suite` | `keep` | `create_newton_suite` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 791 | function | `create_hybrid_local_suite` | `keep` | `create_hybrid_local_suite` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 800 | function | `create_derivative_free_suite` | `keep` | `create_derivative_free_suite` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `bias/specialized/production/scheduling.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 26 | class | `ProductionSchedulingBiasManager` | `keep` | `ProductionSchedulingBiasManager` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 34 | method | `ProductionSchedulingBiasManager.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 53 | method | `ProductionSchedulingBiasManager._configure_bias_weights` | `keep` | `_configure_bias_weights` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 59 | method | `ProductionSchedulingBiasManager._setup_constraints` | `keep` | `_setup_constraints` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 69 | method | `ProductionSchedulingBiasManager._setup_algorithmic_bias` | `keep` | `_setup_algorithmic_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 90 | method | `ProductionSchedulingBiasManager.compute_bias` | `keep` | `compute_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 95 | class | `ProductionConstraintBias` | `keep` | `ProductionConstraintBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 105 | method | `ProductionConstraintBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 123 | method | `ProductionConstraintBias._setup_material_info` | `keep` | `_setup_material_info` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 133 | method | `ProductionConstraintBias._decode_plan` | `keep` | `_decode_plan` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 137 | method | `ProductionConstraintBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 156 | method | `ProductionConstraintBias._material_shortage` | `keep` | `_material_shortage` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 169 | method | `ProductionConstraintBias._integer_penalty` | `keep` | `_integer_penalty` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 173 | method | `ProductionConstraintBias._smoothness_penalty` | `keep` | `_smoothness_penalty` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 177 | method | `ProductionConstraintBias._batch_penalty` | `keep` | `_batch_penalty` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 189 | class | `ProductionDiversityBias` | `keep` | `ProductionDiversityBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 200 | method | `ProductionDiversityBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 203 | method | `ProductionDiversityBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 209 | class | `ProductionContinuityBias` | `keep` | `ProductionContinuityBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 220 | method | `ProductionContinuityBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 225 | method | `ProductionContinuityBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 233 | class | `ProductionOptimizationContext` | `keep` | `ProductionOptimizationContext` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 240 | class | `ProductionSchedulingBias` | `keep` | `ProductionSchedulingBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 250 | method | `ProductionSchedulingBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 253 | method | `ProductionSchedulingBias.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `bias/surrogate/base.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 9 | class | `SurrogateBiasContext` | `keep` | `SurrogateBiasContext` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 28 | method | `SurrogateBiasContext.progress` | `keep` | `progress` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 33 | method | `SurrogateBiasContext.get` | `keep` | `get` | `high` | `-` | 通用存取方法，参数别名规则不适用。 |
| 39 | class | `SurrogateControlBias` | `keep` | `SurrogateControlBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 49 | method | `SurrogateControlBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 52 | method | `SurrogateControlBias.should_apply` | `keep` | `should_apply` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 55 | method | `SurrogateControlBias.apply` | `keep` | `apply` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 58 | method | `SurrogateControlBias.__call__` | `keep` | `__call__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |

### `bias/surrogate/phase_schedule.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 9 | class | `PhaseScheduleBias` | `keep` | `PhaseScheduleBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 19 | method | `PhaseScheduleBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 31 | method | `PhaseScheduleBias.apply` | `keep` | `apply` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 38 | method | `PhaseScheduleBias._progress_value` | `keep` | `_progress_value` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 55 | method | `PhaseScheduleBias._normalize_phases` | `keep` | `_normalize_phases` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 69 | method | `PhaseScheduleBias._select_phase` | `keep` | `_select_phase` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 81 | method | `PhaseScheduleBias._extract_updates` | `keep` | `_extract_updates` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `bias/surrogate/template_surrogate_bias.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 7 | class | `ExampleSurrogateBias` | `keep` | `ExampleSurrogateBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 17 | method | `ExampleSurrogateBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 20 | method | `ExampleSurrogateBias.apply` | `keep` | `apply` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `bias/surrogate/uncertainty_budget.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 10 | class | `UncertaintyBudgetBias` | `keep` | `UncertaintyBudgetBias` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 20 | method | `UncertaintyBudgetBias.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 47 | method | `UncertaintyBudgetBias.should_apply` | `keep` | `should_apply` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 51 | method | `UncertaintyBudgetBias.apply` | `keep` | `apply` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 90 | method | `UncertaintyBudgetBias._fallback_when_not_ready` | `keep` | `_fallback_when_not_ready` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 97 | method | `UncertaintyBudgetBias._reduce_uncertainty` | `keep` | `_reduce_uncertainty` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 105 | method | `UncertaintyBudgetBias._map_uncertainty_to_ratio` | `keep` | `_map_uncertainty_to_ratio` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 115 | method | `UncertaintyBudgetBias._quality_override` | `keep` | `_quality_override` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 125 | method | `UncertaintyBudgetBias._extract_quality` | `keep` | `_extract_quality` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 144 | method | `UncertaintyBudgetBias._build_update` | `keep` | `_build_update` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `bias/utils/helpers.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 11 | function | `create_universal_bias_manager` | `keep` | `create_universal_bias_manager` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 44 | function | `quick_bias_setup` | `keep` | `quick_bias_setup` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 112 | function | `get_bias_system_info` | `keep` | `get_bias_system_info` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `catalog/__init__.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 29 | function | `search_catalog` | `keep` | `search_catalog` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 34 | function | `list_catalog` | `keep` | `list_catalog` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 39 | function | `get_entry` | `keep` | `get_entry` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 44 | function | `reload_catalog` | `keep` | `reload_catalog` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `catalog/markers.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 6 | function | `component` | `keep` | `component` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 19 | function | `component._wrap` | `keep` | `_wrap` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `catalog/quick_add.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 12 | function | `_split_values` | `keep` | `_split_values` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 22 | function | `build_entry_payload` | `keep` | `build_entry_payload` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 83 | function | `_format_list` | `keep` | `_format_list` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 88 | function | `render_entry_block` | `keep` | `render_entry_block` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 111 | function | `upsert_catalog_entry` | `keep` | `upsert_catalog_entry` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 144 | function | `remove_catalog_entry` | `keep` | `remove_catalog_entry` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 194 | function | `main` | `keep` | `main` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `catalog/registry.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 22 | class | `CatalogEntry` | `keep` | `CatalogEntry` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 47 | method | `CatalogEntry.load` | `keep` | `load` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 56 | class | `Catalog` | `keep` | `Catalog` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 57 | method | `Catalog.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 64 | method | `Catalog.get` | `keep` | `get` | `high` | `-` | 通用存取方法，参数别名规则不适用。 |
| 70 | method | `Catalog.list` | `keep` | `list` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 80 | method | `Catalog.search` | `keep` | `search` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 106 | method | `Catalog.search.match` | `keep` | `match` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 135 | method | `Catalog.search.rank` | `keep` | `rank` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 150 | method | `Catalog._hydrate_entry` | `keep` | `_hydrate_entry` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 179 | method | `Catalog._load_detail_payload` | `keep` | `_load_detail_payload` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 205 | method | `Catalog._entry_context_blob` | `keep` | `_entry_context_blob` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 212 | method | `Catalog._entry_context_blob.add_field` | `keep` | `add_field` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 260 | method | `Catalog._entry_usage_blob` | `keep` | `_entry_usage_blob` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 272 | function | `_coerce_str_tuple` | `keep` | `_coerce_str_tuple` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 296 | function | `_parse_literal_fallback` | `keep` | `_parse_literal_fallback` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 309 | function | `_parse_entry_block_fallback` | `keep` | `_parse_entry_block_fallback` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 333 | function | `_expand_token_groups` | `keep` | `_expand_token_groups` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 407 | function | `_default_entries` | `keep` | `_default_entries` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 2322 | function | `_load_entrypoint_entries` | `keep` | `_load_entrypoint_entries` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 2358 | function | `_discover_python_entries` | `keep` | `_discover_python_entries` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 2370 | function | `_discover_python_entries.parse_items` | `keep` | `parse_items` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 2433 | class | `CatalogProvider` | `keep` | `CatalogProvider` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 2438 | method | `CatalogProvider.load` | `keep` | `load` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 2442 | function | `_parse_entries_from_toml` | `keep` | `_parse_entries_from_toml` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 2493 | function | `_collect_toml_paths` | `keep` | `_collect_toml_paths` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 2501 | function | `_load_toml_entries` | `keep` | `_load_toml_entries` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 2512 | class | `BuiltinTomlProvider` | `keep` | `BuiltinTomlProvider` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 2521 | method | `BuiltinTomlProvider.load` | `keep` | `load` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 2530 | class | `EnvTomlProvider` | `keep` | `EnvTomlProvider` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 2535 | method | `EnvTomlProvider.load` | `keep` | `load` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 2547 | function | `_load_external_entries` | `keep` | `_load_external_entries` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 2559 | function | `get_catalog` | `keep` | `get_catalog` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `catalog/source_sync.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 18 | class | `SourceSymbol` | `keep` | `SourceSymbol` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 26 | class | `ExpansionScope` | `keep` | `ExpansionScope` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 31 | function | `_infer_kind` | `keep` | `_infer_kind` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 51 | function | `_decorator_name` | `keep` | `_decorator_name` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 61 | function | `_decorator_kw_str` | `keep` | `_decorator_kw_str` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 70 | function | `_marker_meta` | `keep` | `_marker_meta` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 78 | function | `_is_scaffold_project_root` | `keep` | `_is_scaffold_project_root` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 84 | function | `_is_framework_root` | `keep` | `_is_framework_root` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 93 | function | `detect_expansion_scope` | `keep` | `detect_expansion_scope` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 106 | function | `list_source_symbols` | `keep` | `list_source_symbols` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 127 | function | `_literal_str` | `keep` | `_literal_str` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 133 | function | `_read_values` | `keep` | `_read_values` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 147 | function | `read_symbol_contract` | `keep` | `read_symbol_contract` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 167 | function | `_is_placeholder_name` | `keep` | `_is_placeholder_name` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 180 | function | `_pick_unique_class_name` | `keep` | `_pick_unique_class_name` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 193 | function | `_is_empty_shell_class` | `keep` | `_is_empty_shell_class` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 207 | function | `_import_insert_line` | `keep` | `_import_insert_line` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 228 | function | `_ensure_imports` | `keep` | `_ensure_imports` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 240 | function | `_build_template_block` | `keep` | `_build_template_block` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 329 | function | `expand_marked_component_template` | `keep` | `expand_marked_component_template` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 390 | function | `_format_tuple_assignment` | `keep` | `_format_tuple_assignment` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 401 | function | `_class_indent` | `keep` | `_class_indent` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 405 | function | `apply_symbol_contract` | `keep` | `apply_symbol_contract` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `catalog/usage.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 10 | class | `CatalogUsage` | `keep` | `CatalogUsage` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 18 | function | `_normalize_values` | `keep` | `_normalize_values` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 35 | function | `_symbol_from_import` | `keep` | `_symbol_from_import` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 42 | function | `_normalize_context_notes` | `keep` | `_normalize_context_notes` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 54 | function | `_infer_use_when` | `keep` | `_infer_use_when` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 67 | function | `_infer_minimal_wiring` | `keep` | `_infer_minimal_wiring` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 98 | function | `_infer_required_companions` | `keep` | `_infer_required_companions` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 103 | function | `_infer_config_keys` | `keep` | `_infer_config_keys` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 129 | function | `_infer_example_entry` | `keep` | `_infer_example_entry` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 157 | function | `build_usage_profile` | `keep` | `build_usage_profile` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 180 | function | `enrich_context_contracts` | `keep` | `enrich_context_contracts` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 229 | function | `enrich_usage_contracts` | `keep` | `enrich_usage_contracts` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `core/base.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 1 | class | `BlackBoxProblem` | `keep` | `BlackBoxProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 10 | method | `BlackBoxProblem.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 21 | method | `BlackBoxProblem.__init_subclass__` | `keep` | `__init_subclass__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 31 | method | `BlackBoxProblem.__init_subclass__._wrapped_evaluate` | `keep` | `_wrapped_evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 42 | method | `BlackBoxProblem.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 46 | method | `BlackBoxProblem.evaluate_constraints` | `keep` | `evaluate_constraints` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 62 | method | `BlackBoxProblem.is_valid` | `keep` | `is_valid` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 100 | method | `BlackBoxProblem.get_num_objectives` | `keep` | `get_num_objectives` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 105 | method | `BlackBoxProblem.is_multiobjective` | `keep` | `is_multiobjective` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `core/blank_solver.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 86 | class | `SolverBase` | `keep` | `SolverBase` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 95 | method | `SolverBase.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 218 | method | `SolverBase._build_context_store` | `keep` | `_build_context_store` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 228 | method | `SolverBase._build_snapshot_store` | `keep` | `_build_snapshot_store` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 245 | method | `SolverBase.set_context_store` | `keep` | `set_context_store` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 248 | method | `SolverBase.set_snapshot_store` | `keep` | `set_snapshot_store` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 251 | method | `SolverBase.set_context_store_backend` | `keep` | `set_context_store_backend` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 268 | method | `SolverBase.set_snapshot_store_backend` | `keep` | `set_snapshot_store_backend` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 304 | method | `SolverBase.bias_module` | `keep` | `bias_module` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 319 | method | `SolverBase.bias_module` | `keep` | `bias_module` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 327 | method | `SolverBase.init_bias_module` | `keep` | `init_bias_module` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 353 | method | `SolverBase.representation_pipeline` | `keep` | `representation_pipeline` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 361 | method | `SolverBase.representation_pipeline` | `keep` | `representation_pipeline` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 366 | method | `SolverBase.enable_bias_module` | `keep` | `enable_bias_module` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 374 | method | `SolverBase.add_plugin` | `keep` | `add_plugin` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 494 | method | `SolverBase.remove_plugin` | `keep` | `remove_plugin` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 503 | method | `SolverBase.get_plugin` | `keep` | `get_plugin` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 506 | method | `SolverBase.set_plugin_order` | `keep` | `set_plugin_order` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 522 | method | `SolverBase._set_plugin_order` | `keep` | `_set_plugin_order` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 551 | method | `SolverBase.request_plugin_order` | `keep` | `request_plugin_order` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 568 | method | `SolverBase._apply_pending_plugin_order_updates` | `keep` | `_apply_pending_plugin_order_updates` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 580 | method | `SolverBase._sync_plugin_execution_order` | `keep` | `_sync_plugin_execution_order` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 584 | method | `SolverBase.validate_plugin_order` | `keep` | `validate_plugin_order` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 590 | method | `SolverBase.validate_control_plane` | `keep` | `validate_control_plane` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 599 | method | `SolverBase.set_adapter` | `keep` | `set_adapter` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 602 | method | `SolverBase.set_strategy_controller` | `keep` | `set_strategy_controller` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 606 | method | `SolverBase.set_phase_controller` | `keep` | `set_phase_controller` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 626 | method | `SolverBase.set_bias_module` | `keep` | `set_bias_module` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 636 | method | `SolverBase.set_bias_enabled` | `keep` | `set_bias_enabled` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 641 | method | `SolverBase.set_representation_pipeline` | `keep` | `set_representation_pipeline` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 644 | method | `SolverBase.has_bias_support` | `keep` | `has_bias_support` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 649 | method | `SolverBase.has_numba_support` | `keep` | `has_numba_support` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 652 | method | `SolverBase.register_controller` | `keep` | `register_controller` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 655 | method | `SolverBase.register_evaluation_provider` | `keep` | `register_evaluation_provider` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 658 | method | `SolverBase.register_acceleration_backend` | `keep` | `register_acceleration_backend` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 661 | method | `SolverBase.get_acceleration_backend` | `keep` | `get_acceleration_backend` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 664 | method | `SolverBase.set_max_steps` | `keep` | `set_max_steps` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 667 | method | `SolverBase.set_generation` | `keep` | `set_generation` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 670 | method | `SolverBase.increment_evaluation_count` | `keep` | `increment_evaluation_count` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 678 | method | `SolverBase.set_best_snapshot` | `keep` | `set_best_snapshot` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 687 | method | `SolverBase.set_pareto_snapshot` | `keep` | `set_pareto_snapshot` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 696 | method | `SolverBase.get_best_snapshot` | `keep` | `get_best_snapshot` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 699 | method | `SolverBase.set_solver_hyperparams` | `keep` | `set_solver_hyperparams` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 719 | method | `SolverBase.init_candidate` | `keep` | `init_candidate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 728 | method | `SolverBase.mutate_candidate` | `keep` | `mutate_candidate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 736 | method | `SolverBase.repair_candidate` | `keep` | `repair_candidate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 744 | method | `SolverBase.encode_candidate` | `keep` | `encode_candidate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 750 | method | `SolverBase.decode_candidate` | `keep` | `decode_candidate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 773 | method | `SolverBase.initialize_population` | `keep` | `initialize_population` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 792 | method | `SolverBase.write_population_snapshot` | `keep` | `write_population_snapshot` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 820 | method | `SolverBase._snapshot_run_id` | `keep` | `_snapshot_run_id` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 827 | method | `SolverBase._build_snapshot_key` | `keep` | `_build_snapshot_key` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 834 | method | `SolverBase._snapshot_meta` | `keep` | `_snapshot_meta` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 853 | method | `SolverBase._prepare_snapshot_payload` | `keep` | `_prepare_snapshot_payload` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 874 | method | `SolverBase._persist_snapshot` | `keep` | `_persist_snapshot` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 962 | method | `SolverBase.read_snapshot` | `keep` | `read_snapshot` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 987 | method | `SolverBase._strip_large_context` | `keep` | `_strip_large_context` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 990 | method | `SolverBase._purge_large_context_store` | `keep` | `_purge_large_context_store` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1017 | method | `SolverBase._attach_snapshot_refs` | `keep` | `_attach_snapshot_refs` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1054 | method | `SolverBase.set_random_seed` | `keep` | `set_random_seed` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1072 | method | `SolverBase.fork_rng` | `keep` | `fork_rng` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1082 | method | `SolverBase.get_rng_state` | `keep` | `get_rng_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1085 | method | `SolverBase.set_rng_state` | `keep` | `set_rng_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1109 | method | `SolverBase.build_context` | `keep` | `build_context` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1126 | method | `SolverBase.get_context` | `keep` | `get_context` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1134 | method | `SolverBase._ensure_snapshot_readable` | `keep` | `_ensure_snapshot_readable` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1137 | method | `SolverBase._get_best_snapshot` | `keep` | `_get_best_snapshot` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1144 | method | `SolverBase._collect_runtime_context_projection` | `keep` | `_collect_runtime_context_projection` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1151 | method | `SolverBase.evaluate_individual` | `keep` | `evaluate_individual` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1154 | method | `SolverBase.evaluate_population` | `keep` | `evaluate_population` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1157 | method | `SolverBase._apply_bias` | `keep` | `_apply_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1178 | method | `SolverBase._apply_runtime_control_slot` | `keep` | `_apply_runtime_control_slot` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1183 | method | `SolverBase.request_stop` | `keep` | `request_stop` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1186 | method | `SolverBase.setup` | `keep` | `setup` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1189 | method | `SolverBase.step` | `keep` | `step` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1192 | method | `SolverBase.teardown` | `keep` | `teardown` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1195 | method | `SolverBase.run` | `keep` | `run` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1203 | method | `SolverBase._random_candidate` | `keep` | `_random_candidate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `core/composable_solver.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 19 | class | `ComposableSolver` | `keep` | `ComposableSolver` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 22 | method | `ComposableSolver.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 76 | method | `ComposableSolver.set_adapter` | `keep` | `set_adapter` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 79 | method | `ComposableSolver.set_adapters` | `keep` | `set_adapters` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 82 | method | `ComposableSolver.setup` | `keep` | `setup` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 86 | method | `ComposableSolver.teardown` | `keep` | `teardown` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 90 | method | `ComposableSolver.step` | `keep` | `step` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 136 | method | `ComposableSolver.select_best` | `keep` | `select_best` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 151 | method | `ComposableSolver._update_best` | `keep` | `_update_best` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 165 | method | `ComposableSolver._summarize_step` | `keep` | `_summarize_step` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `core/config.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 16 | class | `SolverConfig` | `keep` | `SolverConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 43 | class | `StorageConfig` | `keep` | `StorageConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 80 | function | `_apply_storage_config` | `keep` | `_apply_storage_config` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 98 | class | `OptimizationResult` | `keep` | `OptimizationResult` | `high` | `-` | 类名未命中当前归一化冲突规则。 |

### `core/evolution_solver.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 19 | class | `EvolutionSolver` | `keep` | `EvolutionSolver` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 22 | method | `EvolutionSolver.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 162 | method | `EvolutionSolver.representation_pipeline` | `keep` | `representation_pipeline` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 167 | method | `EvolutionSolver.representation_pipeline` | `keep` | `representation_pipeline` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 170 | method | `EvolutionSolver._sync_nsga2_adapter_config` | `keep` | `_sync_nsga2_adapter_config` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 179 | method | `EvolutionSolver.set_adapter` | `keep` | `set_adapter` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 183 | method | `EvolutionSolver.set_solver_hyperparams` | `keep` | `set_solver_hyperparams` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 208 | method | `EvolutionSolver.set_context_store` | `keep` | `set_context_store` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 211 | method | `EvolutionSolver.set_snapshot_store` | `keep` | `set_snapshot_store` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 214 | method | `EvolutionSolver.set_context_store_backend` | `keep` | `set_context_store_backend` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 229 | method | `EvolutionSolver.set_snapshot_store_backend` | `keep` | `set_snapshot_store_backend` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 254 | method | `EvolutionSolver._ensure_parallel_evaluator` | `keep` | `_ensure_parallel_evaluator` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 310 | method | `EvolutionSolver.evaluate_population` | `keep` | `evaluate_population` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 327 | method | `EvolutionSolver.initialize_population` | `keep` | `initialize_population` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 345 | method | `EvolutionSolver.setup` | `keep` | `setup` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 379 | method | `EvolutionSolver.step` | `keep` | `step` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 393 | method | `EvolutionSolver._sync_adapter_from_solver` | `keep` | `_sync_adapter_from_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 415 | method | `EvolutionSolver._sync_solver_from_adapter` | `keep` | `_sync_solver_from_adapter` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 447 | method | `EvolutionSolver.non_dominated_sorting` | `keep` | `non_dominated_sorting` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 469 | method | `EvolutionSolver.selection` | `keep` | `selection` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 490 | method | `EvolutionSolver.crossover` | `keep` | `crossover` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 525 | method | `EvolutionSolver.mutate` | `keep` | `mutate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 544 | method | `EvolutionSolver._clip_to_bounds` | `keep` | `_clip_to_bounds` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 558 | method | `EvolutionSolver.environmental_selection` | `keep` | `environmental_selection` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 599 | method | `EvolutionSolver.update_pareto_solutions` | `keep` | `update_pareto_solutions` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 625 | method | `EvolutionSolver.record_history` | `keep` | `record_history` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 641 | method | `EvolutionSolver._refresh_best` | `keep` | `_refresh_best` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 650 | method | `EvolutionSolver._get_best_solution` | `keep` | `_get_best_solution` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 669 | method | `EvolutionSolver._build_run_result` | `keep` | `_build_run_result` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 679 | method | `EvolutionSolver.run` | `keep` | `run` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 682 | method | `EvolutionSolver.run._build_experiment` | `keep` | `_build_experiment` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 706 | method | `EvolutionSolver.run._build_tuple` | `keep` | `_build_tuple` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 719 | method | `EvolutionSolver._log_progress` | `keep` | `_log_progress` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 731 | method | `EvolutionSolver._experiment_result_class` | `keep` | `_experiment_result_class` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `core/nested_solver.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 15 | class | `InnerSolveRequest` | `keep` | `InnerSolveRequest` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 25 | class | `InnerSolveResult` | `keep` | `InnerSolveResult` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 40 | class | `InnerRuntimeEvaluator` | `keep` | `InnerRuntimeEvaluator` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 43 | method | `InnerRuntimeEvaluator.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 68 | method | `InnerRuntimeEvaluator.can_handle` | `keep` | `can_handle` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 74 | method | `InnerRuntimeEvaluator.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 110 | method | `InnerRuntimeEvaluator._build_inner_solver` | `keep` | `_build_inner_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 119 | method | `InnerRuntimeEvaluator._validate_parent_contract` | `keep` | `_validate_parent_contract` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 138 | method | `InnerRuntimeEvaluator._run_inner_solver` | `keep` | `_run_inner_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 169 | method | `InnerRuntimeEvaluator._project_result` | `keep` | `_project_result` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 183 | class | `InnerRuntimeConfig` | `keep` | `InnerRuntimeConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 193 | class | `TaskInnerRuntimeEvaluator` | `keep` | `TaskInnerRuntimeEvaluator` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 196 | method | `TaskInnerRuntimeEvaluator.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 219 | method | `TaskInnerRuntimeEvaluator.can_handle` | `keep` | `can_handle` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 229 | method | `TaskInnerRuntimeEvaluator.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 307 | method | `TaskInnerRuntimeEvaluator._build_task` | `keep` | `_build_task` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 342 | method | `TaskInnerRuntimeEvaluator._run_task` | `keep` | `_run_task` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 408 | method | `TaskInnerRuntimeEvaluator._run_task_with_timeout` | `keep` | `_run_task_with_timeout` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 421 | method | `TaskInnerRuntimeEvaluator._fallback` | `keep` | `_fallback` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `core/solver_helpers/bias_helpers.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 10 | function | `_report_debug_soft_error` | `keep` | `_report_debug_soft_error` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 29 | function | `apply_bias_module` | `keep` | `apply_bias_module` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `core/solver_helpers/candidate_helpers.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 10 | function | `sample_random_candidate` | `keep` | `sample_random_candidate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `core/solver_helpers/component_scheduler.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 9 | class | `ComponentOrderError` | `keep` | `ComponentOrderError` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 14 | class | `_ComponentRecord` | `keep` | `_ComponentRecord` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 20 | function | `_norm_names` | `keep` | `_norm_names` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 31 | class | `ComponentDependencyScheduler` | `keep` | `ComponentDependencyScheduler` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 40 | method | `ComponentDependencyScheduler.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 45 | method | `ComponentDependencyScheduler.register_component` | `keep` | `register_component` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 64 | method | `ComponentDependencyScheduler.unregister_component` | `keep` | `unregister_component` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 75 | method | `ComponentDependencyScheduler.snapshot_rules` | `keep` | `snapshot_rules` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 85 | method | `ComponentDependencyScheduler.restore_rules` | `keep` | `restore_rules` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 96 | method | `ComponentDependencyScheduler.set_constraints` | `keep` | `set_constraints` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 115 | method | `ComponentDependencyScheduler.validate_constraints` | `keep` | `validate_constraints` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 153 | method | `ComponentDependencyScheduler.resolve_order` | `keep` | `resolve_order` | `high` | `-` | 该 resolve_* 属于推断/合并/派生语义，符合规范保留。 |
| 156 | method | `ComponentDependencyScheduler.resolve_order_strict` | `keep` | `resolve_order_strict` | `high` | `-` | 该 resolve_* 属于推断/合并/派生语义，符合规范保留。 |
| 159 | method | `ComponentDependencyScheduler._resolve_order_internal` | `keep` | `_resolve_order_internal` | `high` | `-` | 该 resolve_* 属于推断/合并/派生语义，符合规范保留。 |
| 227 | method | `ComponentDependencyScheduler._sort_key` | `keep` | `_sort_key` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 231 | method | `ComponentDependencyScheduler._validate_single_rule` | `keep` | `_validate_single_rule` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `core/solver_helpers/context_helpers.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 16 | function | `_report_debug_soft_error` | `keep` | `_report_debug_soft_error` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 35 | function | `build_solver_context` | `keep` | `build_solver_context` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 112 | function | `get_solver_context_view` | `keep` | `get_solver_context_view` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 147 | function | `ensure_snapshot_readable` | `keep` | `ensure_snapshot_readable` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `core/solver_helpers/control_plane_helpers.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 10 | function | `_report_debug_soft_error` | `keep` | `_report_debug_soft_error` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 29 | function | `set_generation_value` | `keep` | `set_generation_value` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 35 | function | `increment_evaluation_counter` | `keep` | `increment_evaluation_counter` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 58 | function | `set_best_snapshot_fields` | `keep` | `set_best_snapshot_fields` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 80 | function | `set_pareto_snapshot_fields` | `keep` | `set_pareto_snapshot_fields` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 113 | function | `get_best_snapshot_fields` | `keep` | `get_best_snapshot_fields` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 164 | function | `collect_runtime_context_projection` | `keep` | `collect_runtime_context_projection` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `core/solver_helpers/result_helpers.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 8 | function | `format_run_result` | `keep` | `format_run_result` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `core/solver_helpers/run_helpers.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 9 | function | `apply_runtime_control_slot` | `keep` | `apply_runtime_control_slot` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 36 | function | `run_solver_loop` | `keep` | `run_solver_loop` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `core/solver_helpers/snapshot_helpers.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 42 | function | `strip_large_context_fields` | `keep` | `strip_large_context_fields` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 48 | function | `snapshot_meta` | `keep` | `snapshot_meta` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 78 | function | `build_snapshot_payload` | `keep` | `build_snapshot_payload` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 127 | function | `build_snapshot_refs` | `keep` | `build_snapshot_refs` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `core/solver_helpers/store_helpers.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 11 | function | `build_context_store_or_memory` | `keep` | `build_context_store_or_memory` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 39 | function | `build_snapshot_store_or_memory` | `keep` | `build_snapshot_store_or_memory` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `docs/conf.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 163 | function | `setup` | `keep` | `setup` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/_misc_examples/async_event_driven_demo.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 49 | class | `SphereProblem` | `keep` | `SphereProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 50 | method | `SphereProblem.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 57 | method | `SphereProblem.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 62 | function | `build_solver` | `keep` | `build_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/_misc_examples/benchmark_harness_demo.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 21 | function | `_ensure_importable` | `keep` | `_ensure_importable` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 44 | class | `DemoSphere` | `keep` | `DemoSphere` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 45 | method | `DemoSphere.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 49 | method | `DemoSphere.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 54 | function | `main` | `keep` | `main` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/_misc_examples/blank_solver_plugin_demo.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 29 | class | `SimpleSphereProblem` | `keep` | `SimpleSphereProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 32 | method | `SimpleSphereProblem.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 41 | method | `SimpleSphereProblem.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 46 | class | `RandomWalkPlugin` | `keep` | `RandomWalkPlugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 49 | method | `RandomWalkPlugin.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 58 | method | `RandomWalkPlugin.on_solver_init` | `keep` | `on_solver_init` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 66 | method | `RandomWalkPlugin.on_step` | `keep` | `on_step` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 78 | method | `RandomWalkPlugin._update_buffers` | `keep` | `_update_buffers` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 92 | method | `RandomWalkPlugin._maybe_update_best` | `keep` | `_maybe_update_best` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 99 | function | `build_solver` | `keep` | `build_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/_misc_examples/composable_solver_fusion_demo.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 31 | class | `SimpleSphereProblem` | `keep` | `SimpleSphereProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 32 | method | `SimpleSphereProblem.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 41 | method | `SimpleSphereProblem.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 46 | class | `RandomProbeAdapter` | `keep` | `RandomProbeAdapter` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 47 | method | `RandomProbeAdapter.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 51 | method | `RandomProbeAdapter.propose` | `keep` | `propose` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 55 | class | `LocalStepAdapter` | `keep` | `LocalStepAdapter` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 56 | method | `LocalStepAdapter.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 60 | method | `LocalStepAdapter.propose` | `keep` | `propose` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 66 | class | `StepLoggerPlugin` | `keep` | `StepLoggerPlugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 67 | method | `StepLoggerPlugin.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 71 | method | `StepLoggerPlugin.on_step` | `keep` | `on_step` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 79 | function | `build_solver` | `keep` | `build_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/_misc_examples/copt_qp_template_demo.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 21 | function | `main` | `keep` | `main` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/_misc_examples/decision_trace_demo.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 32 | class | `Sphere` | `keep` | `Sphere` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 33 | method | `Sphere.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 38 | method | `Sphere.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 43 | class | `DecisionSignalPlugin` | `keep` | `DecisionSignalPlugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 52 | method | `DecisionSignalPlugin.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 55 | method | `DecisionSignalPlugin.on_generation_end` | `keep` | `on_generation_end` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 99 | function | `build_solver` | `keep` | `build_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 114 | function | `main` | `keep` | `main` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/_misc_examples/dynamic_penalty_projection_demo.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 11 | class | `SimpleConstrainedProblem` | `keep` | `SimpleConstrainedProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 14 | method | `SimpleConstrainedProblem.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 18 | method | `SimpleConstrainedProblem.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 22 | method | `SimpleConstrainedProblem.evaluate_constraints` | `keep` | `evaluate_constraints` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 30 | function | `build_solver` | `keep` | `build_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 42 | function | `build_solver.constraint_penalty` | `keep` | `constraint_penalty` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 66 | function | `main` | `keep` | `main` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/_misc_examples/dynamic_repair_demo.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 11 | class | `SimpleProblem` | `keep` | `SimpleProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 12 | method | `SimpleProblem.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 16 | method | `SimpleProblem.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 21 | function | `build_solver` | `keep` | `build_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 40 | function | `main` | `keep` | `main` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/_misc_examples/mas_demo.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 27 | class | `SphereProblem` | `keep` | `SphereProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 28 | method | `SphereProblem.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 37 | method | `SphereProblem.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 42 | function | `build_solver` | `keep` | `build_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/_misc_examples/migration_lab/ga_single_objective/00_baseline.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 12 | class | `BaselineGAConfig` | `keep` | `BaselineGAConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 25 | function | `objective` | `keep` | `objective` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 31 | function | `initialize_population` | `keep` | `initialize_population` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 35 | function | `evaluate_population` | `keep` | `evaluate_population` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 39 | function | `tournament_select` | `keep` | `tournament_select` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 45 | function | `crossover` | `keep` | `crossover` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 52 | function | `mutate` | `keep` | `mutate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 60 | function | `evolve_one_generation` | `keep` | `evolve_one_generation` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 71 | function | `run_baseline` | `keep` | `run_baseline` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/_misc_examples/migration_lab/ga_single_objective/02_framework_final.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 12 | function | `_ensure_repo_importable` | `keep` | `_ensure_repo_importable` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 34 | class | `FrameworkConfig` | `keep` | `FrameworkConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 45 | class | `ShiftedSphereProblem` | `keep` | `ShiftedSphereProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 48 | method | `ShiftedSphereProblem.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 57 | method | `ShiftedSphereProblem.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 62 | function | `build_solver` | `keep` | `build_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 86 | function | `run_framework` | `keep` | `run_framework` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/_misc_examples/migration_lab/nsga2_multi_objective/00_baseline.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 12 | class | `BaselineNSGA2Config` | `keep` | `BaselineNSGA2Config` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 25 | function | `evaluate_individual` | `keep` | `evaluate_individual` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 32 | function | `evaluate_population` | `keep` | `evaluate_population` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 36 | function | `dominates` | `keep` | `dominates` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 40 | function | `fast_non_dominated_sort` | `keep` | `fast_non_dominated_sort` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 75 | function | `crowding_distance` | `keep` | `crowding_distance` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 104 | function | `initialize_population` | `keep` | `initialize_population` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 108 | function | `crossover` | `keep` | `crossover` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 115 | function | `mutate` | `keep` | `mutate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 123 | function | `tournament_select` | `keep` | `tournament_select` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 135 | function | `environmental_selection` | `keep` | `environmental_selection` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 156 | function | `run_baseline` | `keep` | `run_baseline` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/_misc_examples/migration_lab/nsga2_multi_objective/02_framework_final.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 12 | function | `_ensure_repo_importable` | `keep` | `_ensure_repo_importable` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 35 | class | `FrameworkNSGA2Config` | `keep` | `FrameworkNSGA2Config` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 46 | class | `BiObjectiveShiftedSphere` | `keep` | `BiObjectiveShiftedSphere` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 49 | method | `BiObjectiveShiftedSphere.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 58 | method | `BiObjectiveShiftedSphere.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 65 | function | `build_solver` | `keep` | `build_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 89 | function | `run_framework` | `keep` | `run_framework` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/_misc_examples/nested_three_layer_demo.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 26 | function | `_ensure_importable` | `keep` | `_ensure_importable` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 52 | function | `_solve_level3_newton` | `keep` | `_solve_level3_newton` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 55 | function | `_solve_level3_newton.residual` | `keep` | `residual` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 70 | function | `_run_level2` | `keep` | `_run_level2` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 91 | class | `NestedOuterProblem` | `keep` | `NestedOuterProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 94 | method | `NestedOuterProblem.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 97 | method | `NestedOuterProblem.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 102 | method | `NestedOuterProblem.build_inner_task` | `keep` | `build_inner_task` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 107 | method | `NestedOuterProblem.evaluate_from_inner_result` | `keep` | `evaluate_from_inner_result` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 112 | class | `RandomSearchAdapter` | `keep` | `RandomSearchAdapter` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 113 | method | `RandomSearchAdapter.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 117 | method | `RandomSearchAdapter.propose` | `keep` | `propose` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 126 | function | `build_solver` | `keep` | `build_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 158 | function | `main` | `keep` | `main` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/_misc_examples/ngspice_inner_demo.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 12 | class | `NgspiceOuterProblem` | `keep` | `NgspiceOuterProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 13 | method | `NgspiceOuterProblem.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 16 | method | `NgspiceOuterProblem.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 21 | method | `NgspiceOuterProblem.build_inner_problem` | `keep` | `build_inner_problem` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 26 | method | `NgspiceOuterProblem.evaluate_from_inner_result` | `keep` | `evaluate_from_inner_result` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 31 | class | `FixedAdapter` | `keep` | `FixedAdapter` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 38 | method | `FixedAdapter.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 41 | method | `FixedAdapter.propose` | `keep` | `propose` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 46 | function | `build_solver` | `keep` | `build_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 71 | function | `main` | `keep` | `main` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/_misc_examples/nsga2_solver_demo.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 17 | class | `BiObjectiveSphere` | `keep` | `BiObjectiveSphere` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 18 | method | `BiObjectiveSphere.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 24 | method | `BiObjectiveSphere.get_num_objectives` | `keep` | `get_num_objectives` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 27 | method | `BiObjectiveSphere.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 34 | function | `build_solver` | `keep` | `build_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/_misc_examples/otel_tracing_demo.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 35 | class | `Sphere` | `keep` | `Sphere` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 36 | method | `Sphere.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 41 | method | `Sphere.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 46 | function | `build_solver` | `keep` | `build_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 70 | function | `main` | `keep` | `main` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/_misc_examples/ray_parallel_demo.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 14 | function | `main` | `keep` | `main` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 25 | class | `main.SphereProblem` | `keep` | `SphereProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 30 | method | `SphereProblem.main.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 34 | method | `SphereProblem.main.get_num_objectives` | `keep` | `get_num_objectives` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 37 | function | `main.problem_factory` | `keep` | `problem_factory` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/_misc_examples/sequence_graph_demo.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 28 | class | `Sphere` | `keep` | `Sphere` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 29 | method | `Sphere.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 34 | method | `Sphere.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 39 | function | `build_solver` | `keep` | `build_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 57 | function | `main` | `keep` | `main` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/_misc_examples/single_trajectory_adaptive_demo.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 25 | class | `SphereProblem` | `keep` | `SphereProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 26 | method | `SphereProblem.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 33 | method | `SphereProblem.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 38 | function | `build_solver` | `keep` | `build_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/_misc_examples/template_assignment_matrix.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 25 | class | `AssignmentProblem` | `keep` | `AssignmentProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 28 | method | `AssignmentProblem.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 38 | method | `AssignmentProblem.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 43 | function | `build_solver` | `keep` | `build_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/_misc_examples/template_graph_path.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 25 | class | `GraphRepairChain` | `keep` | `GraphRepairChain` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 32 | method | `GraphRepairChain.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 37 | method | `GraphRepairChain.repair` | `keep` | `repair` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 45 | class | `GraphPathProblem` | `keep` | `GraphPathProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 48 | method | `GraphPathProblem.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 59 | method | `GraphPathProblem.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 68 | function | `build_solver` | `keep` | `build_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/_misc_examples/template_knapsack_binary.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 25 | class | `KnapsackProblem` | `keep` | `KnapsackProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 26 | method | `KnapsackProblem.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 36 | method | `KnapsackProblem.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 46 | function | `build_solver` | `keep` | `build_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/_misc_examples/template_multiobjective_pareto.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 27 | class | `BiObjectiveSphere` | `keep` | `BiObjectiveSphere` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 30 | method | `BiObjectiveSphere.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 39 | method | `BiObjectiveSphere.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 46 | function | `build_solver` | `keep` | `build_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/_misc_examples/template_portfolio_pareto.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 27 | class | `SimplexRepair` | `keep` | `SimplexRepair` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 35 | method | `SimplexRepair.repair` | `keep` | `repair` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 45 | class | `PortfolioProblem` | `keep` | `PortfolioProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 46 | method | `PortfolioProblem.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 56 | method | `PortfolioProblem.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 64 | function | `build_solver` | `keep` | `build_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/_misc_examples/template_production_schedule_simple.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 25 | class | `ProductionScheduleProblem` | `keep` | `ProductionScheduleProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 28 | method | `ProductionScheduleProblem.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 39 | method | `ProductionScheduleProblem.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 47 | function | `build_solver` | `keep` | `build_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/_misc_examples/template_tsp_permutation.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 33 | class | `TSPProblem` | `keep` | `TSPProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 34 | method | `TSPProblem.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 43 | method | `TSPProblem._build_distance` | `keep` | `_build_distance` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 51 | method | `TSPProblem.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 60 | function | `build_solver` | `keep` | `build_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/_misc_examples/trust_region_dfo_demo.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 25 | class | `SphereProblem` | `keep` | `SphereProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 26 | method | `SphereProblem.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 35 | method | `SphereProblem.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 40 | function | `build_solver` | `keep` | `build_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/_misc_examples/trust_region_mo_dfo_demo.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 11 | class | `SimpleMOProblem` | `keep` | `SimpleMOProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 12 | method | `SimpleMOProblem.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 16 | method | `SimpleMOProblem.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 23 | function | `build_solver` | `keep` | `build_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 39 | function | `main` | `keep` | `main` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/_misc_examples/trust_region_nonsmooth_demo.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 25 | class | `AbsSphereProblem` | `keep` | `AbsSphereProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 26 | method | `AbsSphereProblem.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 35 | method | `AbsSphereProblem.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 40 | function | `build_solver` | `keep` | `build_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/_misc_examples/trust_region_subspace_demo.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 27 | class | `SphereProblem` | `keep` | `SphereProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 28 | method | `SphereProblem.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 37 | method | `SphereProblem.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 42 | function | `build_solver` | `keep` | `build_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/_misc_examples/trust_region_subspace_frontier_demo.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 11 | class | `HighDimProblem` | `keep` | `HighDimProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 12 | method | `HighDimProblem.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 16 | method | `HighDimProblem.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 21 | function | `build_solver` | `keep` | `build_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 37 | function | `main` | `keep` | `main` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/cases/production_scheduling/_bootstrap.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 14 | function | `ensure_nsgablack_importable` | `keep` | `ensure_nsgablack_importable` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/cases/production_scheduling/adapter/search_adapters.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 16 | class | `_GreedyConfig` | `keep` | `_GreedyConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 23 | function | `_build_greedy_schedule` | `keep` | `_build_greedy_schedule` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 90 | class | `ProductionRandomSearchAdapter` | `keep` | `ProductionRandomSearchAdapter` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 101 | method | `ProductionRandomSearchAdapter.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 105 | method | `ProductionRandomSearchAdapter.propose` | `keep` | `propose` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 114 | class | `ProductionLocalSearchAdapter` | `keep` | `ProductionLocalSearchAdapter` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 125 | method | `ProductionLocalSearchAdapter.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 129 | method | `ProductionLocalSearchAdapter.propose` | `keep` | `propose` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 142 | class | `ProductionGreedyBaselineAdapter` | `keep` | `ProductionGreedyBaselineAdapter` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 151 | method | `ProductionGreedyBaselineAdapter.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 155 | method | `ProductionGreedyBaselineAdapter.propose` | `keep` | `propose` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 162 | class | `ProductionACOBaselineAdapter` | `keep` | `ProductionACOBaselineAdapter` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 171 | method | `ProductionACOBaselineAdapter.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 189 | method | `ProductionACOBaselineAdapter._ensure_pheromone` | `keep` | `_ensure_pheromone` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 196 | method | `ProductionACOBaselineAdapter.propose` | `keep` | `propose` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 212 | method | `ProductionACOBaselineAdapter.update` | `keep` | `update` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/cases/production_scheduling/bias/production_bias.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 13 | function | `_ensure_importable` | `keep` | `_ensure_importable` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 39 | function | `_reshape_schedule` | `keep` | `_reshape_schedule` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 43 | function | `_constraints_value` | `keep` | `_constraints_value` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 57 | class | `_PenaltyFromConstraints` | `keep` | `_PenaltyFromConstraints` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 58 | method | `_PenaltyFromConstraints.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 62 | method | `_PenaltyFromConstraints.__call__` | `keep` | `__call__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 72 | class | `_UtilizationReward` | `keep` | `_UtilizationReward` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 73 | method | `_UtilizationReward.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 78 | method | `_UtilizationReward.__call__` | `keep` | `__call__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 86 | class | `_SmoothnessPenalty` | `keep` | `_SmoothnessPenalty` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 87 | method | `_SmoothnessPenalty.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 91 | method | `_SmoothnessPenalty.__call__` | `keep` | `__call__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 101 | class | `_VariancePenalty` | `keep` | `_VariancePenalty` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 109 | method | `_VariancePenalty.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 113 | method | `_VariancePenalty.__call__` | `keep` | `__call__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 123 | class | `_CoverageReward` | `keep` | `_CoverageReward` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 124 | method | `_CoverageReward.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 129 | method | `_CoverageReward.__call__` | `keep` | `__call__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 139 | function | `build_production_bias_module` | `keep` | `build_production_bias_module` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/cases/production_scheduling/cli/parser.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 8 | function | `build_parser` | `keep` | `build_parser` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/cases/production_scheduling/demoo.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 10 | function | `_pick_first_existing_font` | `keep` | `_pick_first_existing_font` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 19 | function | `_configure_chinese_font` | `keep` | `_configure_chinese_font` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 37 | function | `_find_latest_result` | `keep` | `_find_latest_result` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 58 | function | `_load_plan` | `keep` | `_load_plan` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 71 | function | `_normalize_plan` | `keep` | `_normalize_plan` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 97 | function | `_plot_plan` | `keep` | `_plot_plan` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 182 | function | `main` | `keep` | `main` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/cases/production_scheduling/pipeline/schedule_pipeline.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 14 | function | `_ensure_importable` | `keep` | `_ensure_importable` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 37 | class | `ProductionScheduleInitializer` | `keep` | `ProductionScheduleInitializer` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 50 | method | `ProductionScheduleInitializer.initialize` | `keep` | `initialize` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 71 | class | `SupplyAwareInitializer` | `keep` | `SupplyAwareInitializer` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 90 | method | `SupplyAwareInitializer.initialize` | `keep` | `initialize` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 194 | class | `ProductionScheduleMutation` | `keep` | `ProductionScheduleMutation` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 217 | method | `ProductionScheduleMutation._runtime_params` | `keep` | `_runtime_params` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 240 | method | `ProductionScheduleMutation.mutate` | `keep` | `mutate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 262 | class | `ProductionScheduleRepair` | `keep` | `ProductionScheduleRepair` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 275 | method | `ProductionScheduleRepair.repair` | `keep` | `repair` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 308 | class | `SupplyAwareScheduleRepair` | `keep` | `SupplyAwareScheduleRepair` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 342 | method | `SupplyAwareScheduleRepair._prune_fragments` | `keep` | `_prune_fragments` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 376 | method | `SupplyAwareScheduleRepair._balance_forward` | `keep` | `_balance_forward` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 491 | method | `SupplyAwareScheduleRepair._backfill_coverage` | `keep` | `_backfill_coverage` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 500 | method | `SupplyAwareScheduleRepair._backfill_coverage._threshold_from_total` | `keep` | `_threshold_from_total` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 621 | method | `SupplyAwareScheduleRepair._continuity_swap` | `keep` | `_continuity_swap` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 715 | method | `SupplyAwareScheduleRepair._enforce_material_feasibility` | `keep` | `_enforce_material_feasibility` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 771 | method | `SupplyAwareScheduleRepair.repair` | `keep` | `repair` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1142 | method | `SupplyAwareScheduleRepair.repair._lift_with_stock` | `keep` | `_lift_with_stock` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1218 | function | `build_schedule_pipeline` | `keep` | `build_schedule_pipeline` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/cases/production_scheduling/plugins/export_utils.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 14 | function | `choose_pareto_solutions` | `keep` | `choose_pareto_solutions` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 35 | function | `crowding_distance` | `keep` | `crowding_distance` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 55 | function | `get_pareto_export_root` | `keep` | `get_pareto_export_root` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 68 | function | `get_summary_path` | `keep` | `get_summary_path` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 72 | function | `export_pareto_batch` | `keep` | `export_pareto_batch` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 128 | function | `default_export_path` | `keep` | `default_export_path` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 136 | function | `default_export_dir` | `keep` | `default_export_dir` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 143 | function | `get_export_path` | `keep` | `get_export_path` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 157 | function | `supply_tag_from_path` | `keep` | `supply_tag_from_path` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 170 | function | `write_export_summary` | `keep` | `write_export_summary` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 194 | function | `export_schedule` | `keep` | `export_schedule` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 215 | function | `extract_pareto` | `keep` | `extract_pareto` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/cases/production_scheduling/plugins/runtime_plugins.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 23 | class | `ConsoleProgressPlugin` | `keep` | `ConsoleProgressPlugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 34 | method | `ConsoleProgressPlugin.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 40 | method | `ConsoleProgressPlugin.on_solver_init` | `keep` | `on_solver_init` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 44 | method | `ConsoleProgressPlugin.on_generation_end` | `keep` | `on_generation_end` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 80 | method | `ConsoleProgressPlugin._compute_best_metrics` | `keep` | `_compute_best_metrics` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 103 | class | `ProductionExportPlugin` | `keep` | `ProductionExportPlugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 114 | method | `ProductionExportPlugin.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 140 | method | `ProductionExportPlugin.on_solver_finish` | `keep` | `on_solver_finish` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 194 | method | `ProductionExportPlugin._sanity_check_export` | `keep` | `_sanity_check_export` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/cases/production_scheduling/problem/problem_factory.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 19 | class | `ProductionProblemFactory` | `keep` | `ProductionProblemFactory` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 22 | method | `ProductionProblemFactory.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 71 | method | `ProductionProblemFactory.__call__` | `keep` | `__call__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 103 | function | `build_problem_factory` | `keep` | `build_problem_factory` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 122 | function | `build_problem` | `keep` | `build_problem` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/cases/production_scheduling/problem/production_problem.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 14 | function | `_ensure_importable` | `keep` | `_ensure_importable` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 33 | class | `ProductionConstraints` | `keep` | `ProductionConstraints` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 46 | class | `ProductionSchedulingProblem` | `keep` | `ProductionSchedulingProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 47 | method | `ProductionSchedulingProblem.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 71 | method | `ProductionSchedulingProblem.get_num_objectives` | `keep` | `get_num_objectives` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 74 | method | `ProductionSchedulingProblem.decode_schedule` | `keep` | `decode_schedule` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 78 | method | `ProductionSchedulingProblem._compute_material_shortage` | `keep` | `_compute_material_shortage` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 89 | method | `ProductionSchedulingProblem._constraint_components` | `keep` | `_constraint_components` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 111 | method | `ProductionSchedulingProblem.evaluate_constraints` | `keep` | `evaluate_constraints` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 128 | method | `ProductionSchedulingProblem.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 186 | method | `ProductionSchedulingProblem._compute_penalty` | `keep` | `_compute_penalty` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 216 | method | `ProductionSchedulingProblem.summarize_schedule` | `keep` | `summarize_schedule` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 235 | method | `ProductionSchedulingProblem.sanity_check_schedule` | `keep` | `sanity_check_schedule` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 285 | class | `ProductionSchedulingSingleObjectiveProblem` | `keep` | `ProductionSchedulingSingleObjectiveProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 288 | method | `ProductionSchedulingSingleObjectiveProblem.get_num_objectives` | `keep` | `get_num_objectives` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 291 | method | `ProductionSchedulingSingleObjectiveProblem.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/cases/production_scheduling/project_registry.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 9 | function | `get_project_entries` | `keep` | `get_project_entries` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/cases/production_scheduling/refactor_data.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 75 | class | `ProductionData` | `keep` | `ProductionData` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 85 | method | `ProductionData.estimate_theoretical_max` | `keep` | `estimate_theoretical_max` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 94 | function | `_resolve_existing` | `keep` | `_resolve_existing` | `high` | `-` | 该 resolve_* 属于推断/合并/派生语义，符合规范保留。 |
| 102 | function | `_read_csv_with_fallback` | `keep` | `_read_csv_with_fallback` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 115 | function | `_read_table` | `keep` | `_read_table` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 123 | function | `_normalize_id` | `keep` | `_normalize_id` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 138 | function | `_normalize_id_with_base` | `keep` | `_normalize_id_with_base` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 150 | function | `load_bom_matrix` | `keep` | `load_bom_matrix` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 183 | function | `load_supply_matrix` | `keep` | `load_supply_matrix` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 206 | function | `load_production_data` | `keep` | `load_production_data` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 249 | function | `_create_fallback_data` | `keep` | `_create_fallback_data` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 283 | function | `_resolve_machine_weights` | `keep` | `_resolve_machine_weights` | `high` | `-` | 该 resolve_* 属于推断/合并/派生语义，符合规范保留。 |

### `examples/cases/production_scheduling/solver/run_case.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 21 | function | `main` | `keep` | `main` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/cases/production_scheduling/solver/strict_feasible_solver.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 12 | function | `project_schedule_material_feasible` | `keep` | `project_schedule_material_feasible` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 43 | function | `project_candidate_material_feasible` | `keep` | `project_candidate_material_feasible` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 49 | class | `StrictFeasibleProductionSolver` | `keep` | `StrictFeasibleProductionSolver` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 52 | method | `StrictFeasibleProductionSolver.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 56 | method | `StrictFeasibleProductionSolver.step` | `keep` | `step` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/cases/production_scheduling/working_integrated_optimizer.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 35 | function | `run_nsga2` | `keep` | `run_nsga2` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 39 | function | `build_multi_agent_solver` | `keep` | `build_multi_agent_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 43 | function | `run_multi_agent` | `keep` | `run_multi_agent` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 47 | function | `_build_solver_from_args` | `keep` | `_build_solver_from_args` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 51 | function | `build_solver` | `keep` | `build_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 55 | function | `main` | `keep` | `main` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/cases/supply_adjustment_nested/inner_solver.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 11 | class | `InnerProductionSolverConfig` | `keep` | `InnerProductionSolverConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 24 | function | `build_inner_production_solver` | `keep` | `build_inner_production_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 87 | class | `build_inner_production_solver._Args` | `keep` | `_Args` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 158 | function | `extract_total_output` | `keep` | `extract_total_output` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/cases/supply_adjustment_nested/material_shortage_blacklist.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 13 | function | `_load_data` | `keep` | `_load_data` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 39 | function | `_analyze_material_safety` | `keep` | `_analyze_material_safety` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 166 | function | `main` | `keep` | `main` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/cases/supply_adjustment_nested/pipeline/l0_binary_pipeline.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 11 | function | `build_l0_binary_pipeline` | `keep` | `build_l0_binary_pipeline` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/cases/supply_adjustment_nested/plugins/supply_adjustment_export_plugin.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 16 | class | `SupplyAdjustmentExportPlugin` | `keep` | `SupplyAdjustmentExportPlugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 27 | method | `SupplyAdjustmentExportPlugin.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 33 | method | `SupplyAdjustmentExportPlugin.on_solver_finish` | `keep` | `on_solver_finish` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/cases/supply_adjustment_nested/problem/blacklist_design_problem.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 24 | class | `BlacklistEvalConfig` | `keep` | `BlacklistEvalConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 45 | class | `BlacklistDesignProblem` | `keep` | `BlacklistDesignProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 56 | method | `BlacklistDesignProblem.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 102 | method | `BlacklistDesignProblem._build_relation_graph` | `keep` | `_build_relation_graph` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 116 | method | `BlacklistDesignProblem._emit` | `keep` | `_emit` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 126 | method | `BlacklistDesignProblem._decode_blacklist_ids` | `keep` | `_decode_blacklist_ids` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 159 | method | `BlacklistDesignProblem._build_l1_solver` | `keep` | `_build_l1_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 202 | method | `BlacklistDesignProblem._best_output_from_solver` | `keep` | `_best_output_from_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 215 | method | `BlacklistDesignProblem._run_l1` | `keep` | `_run_l1` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 223 | method | `BlacklistDesignProblem._compute_baseline_output` | `keep` | `_compute_baseline_output` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 237 | method | `BlacklistDesignProblem._ensure_baseline_output` | `keep` | `_ensure_baseline_output` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 242 | method | `BlacklistDesignProblem.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 275 | method | `BlacklistDesignProblem.build_inner_task` | `keep` | `build_inner_task` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 289 | method | `BlacklistDesignProblem.build_inner_task._run_inner` | `keep` | `_run_inner` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 299 | method | `BlacklistDesignProblem.evaluate_from_inner_result` | `keep` | `evaluate_from_inner_result` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 311 | method | `BlacklistDesignProblem.evaluate_constraints` | `keep` | `evaluate_constraints` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 323 | method | `BlacklistDesignProblem.decode_mask` | `keep` | `decode_mask` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/cases/supply_adjustment_nested/working_blacklist_optimizer.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 48 | function | `_resolve_default_baseline_plan` | `keep` | `_resolve_default_baseline_plan` | `high` | `-` | 该 resolve_* 属于推断/合并/派生语义，符合规范保留。 |
| 62 | function | `_load_baseline_schedule` | `keep` | `_load_baseline_schedule` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 81 | function | `_load_case_data` | `keep` | `_load_case_data` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 103 | function | `_read_ids_file` | `keep` | `_read_ids_file` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 119 | function | `_read_relational_candidates` | `keep` | `_read_relational_candidates` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 128 | function | `build_parser` | `keep` | `build_parser` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 177 | function | `_build_solver` | `keep` | `_build_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 290 | function | `_dump_best_blacklist` | `keep` | `_dump_best_blacklist` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 325 | function | `_export_supply_like_xlsx` | `keep` | `_export_supply_like_xlsx` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 339 | function | `_run_final_l1_and_export` | `keep` | `_run_final_l1_and_export` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 427 | function | `build_solver` | `keep` | `build_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 432 | function | `main` | `keep` | `main` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/copt_examples/cb_ex1.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 28 | function | `get_distance` | `keep` | `get_distance` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 35 | function | `find_subtour` | `keep` | `find_subtour` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 65 | function | `draw_tours` | `keep` | `draw_tours` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 90 | class | `TspCallback` | `keep` | `TspCallback` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 96 | method | `TspCallback.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 101 | method | `TspCallback.callback` | `keep` | `callback` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/copt_examples/cb_nlp.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 22 | class | `HS071` | `keep` | `HS071` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 23 | method | `HS071.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 26 | method | `HS071.EvalObj` | `keep` | `EvalObj` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 34 | method | `HS071.EvalGrad` | `keep` | `EvalGrad` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 45 | method | `HS071.EvalCon` | `keep` | `EvalCon` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 53 | method | `HS071.EvalJac` | `keep` | `EvalJac` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 64 | method | `HS071.EvalHess` | `keep` | `EvalHess` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 94 | method | `HS071.hessianstructure` | `keep` | `hessianstructure` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/copt_examples/cutstock_cg.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 21 | function | `reportRMP` | `keep` | `reportRMP` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 31 | function | `reportSUB` | `keep` | `reportSUB` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 36 | function | `reportMIP` | `keep` | `reportMIP` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/copt_examples/filterdesign.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 12 | function | `T_dot_X` | `keep` | `T_dot_X` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 20 | function | `trigpoly_0_pi` | `keep` | `trigpoly_0_pi` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 30 | function | `trigpoly_0_a` | `keep` | `trigpoly_0_a` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 44 | function | `trigpoly_a_pi` | `keep` | `trigpoly_a_pi` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 58 | function | `epigraph` | `keep` | `epigraph` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 79 | function | `hypograph` | `keep` | `hypograph` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 140 | function | `H` | `keep` | `H` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/copt_examples/genconstr_ex6.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 19 | function | `f` | `keep` | `f` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 22 | function | `g` | `keep` | `g` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/copt_examples/matfactor.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 9 | function | `factorMarkowitz` | `keep` | `factorMarkowitz` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/copt_examples/matqcqp.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 10 | function | `sdp_relaxation` | `keep` | `sdp_relaxation` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 30 | function | `least_squares` | `keep` | `least_squares` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/copt_examples/sensitivity_analysis.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 32 | function | `print_sensitivity` | `keep` | `print_sensitivity` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/copt_examples/socp_ex1.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 11 | function | `solve_soc` | `keep` | `solve_soc` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 69 | function | `solve_rsoc` | `keep` | `solve_rsoc` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 133 | function | `solve_mps` | `keep` | `solve_mps` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/copt_examples/sudoku_matrix.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 11 | function | `solve_mip` | `keep` | `solve_mip` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 63 | function | `solve_mip_matrix` | `keep` | `solve_mip_matrix` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `examples/copt_examples/warehouse_bd.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 10 | class | `BendersCallback` | `keep` | `BendersCallback` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 11 | method | `BendersCallback.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 28 | method | `BendersCallback.callback` | `keep` | `callback` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 64 | class | `WareHouse` | `keep` | `WareHouse` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 65 | method | `WareHouse.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 83 | method | `WareHouse.read` | `keep` | `read` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 144 | method | `WareHouse.build` | `keep` | `build` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 185 | method | `WareHouse.solve` | `keep` | `solve` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 204 | method | `WareHouse.report` | `keep` | `report` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `my_project/adapter/template_adapter.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 13 | class | `AdapterTemplate` | `keep` | `AdapterTemplate` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 22 | method | `AdapterTemplate.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 28 | method | `AdapterTemplate.propose` | `keep` | `propose` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 38 | method | `AdapterTemplate.update` | `keep` | `update` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `my_project/bias/example_bias.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 9 | function | `build_bias_module` | `keep` | `build_bias_module` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `my_project/bias/template_bias.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 11 | class | `BiasTemplate` | `keep` | `BiasTemplate` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 23 | method | `BiasTemplate.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 27 | method | `BiasTemplate.compute` | `keep` | `compute` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `my_project/pipeline/example_pipeline.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 14 | function | `build_pipeline` | `keep` | `build_pipeline` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `my_project/pipeline/template_pipeline.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 13 | class | `PipelineInitializerTemplate` | `keep` | `PipelineInitializerTemplate` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 22 | method | `PipelineInitializerTemplate.initialize` | `keep` | `initialize` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 28 | class | `PipelineMutationTemplate` | `keep` | `PipelineMutationTemplate` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 37 | method | `PipelineMutationTemplate.mutate` | `keep` | `mutate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 43 | class | `PipelineRepairTemplate` | `keep` | `PipelineRepairTemplate` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 52 | method | `PipelineRepairTemplate.repair` | `keep` | `repair` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `my_project/plugins/example_plugin.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 14 | class | `ExampleProjectPlugin` | `keep` | `ExampleProjectPlugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 23 | method | `ExampleProjectPlugin.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 29 | method | `ExampleProjectPlugin.on_solver_init` | `keep` | `on_solver_init` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 32 | method | `ExampleProjectPlugin.on_generation_end` | `keep` | `on_generation_end` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 41 | method | `ExampleProjectPlugin.on_context_build` | `keep` | `on_context_build` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 45 | method | `ExampleProjectPlugin.on_solver_finish` | `keep` | `on_solver_finish` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `my_project/plugins/template_plugin.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 14 | class | `PluginTemplate` | `keep` | `PluginTemplate` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 23 | method | `PluginTemplate.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 30 | method | `PluginTemplate.on_solver_init` | `keep` | `on_solver_init` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 34 | method | `PluginTemplate.on_generation_end` | `keep` | `on_generation_end` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 44 | method | `PluginTemplate.on_context_build` | `keep` | `on_context_build` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `my_project/problem/example_problem.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 11 | class | `ExampleProblem` | `keep` | `ExampleProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 12 | method | `ExampleProblem.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 21 | method | `ExampleProblem.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 27 | method | `ExampleProblem.evaluate_constraints` | `keep` | `evaluate_constraints` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `my_project/problem/template_problem.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 11 | class | `ProblemTemplate` | `keep` | `ProblemTemplate` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 14 | method | `ProblemTemplate.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 24 | method | `ProblemTemplate.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 31 | method | `ProblemTemplate.evaluate_constraints` | `keep` | `evaluate_constraints` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `my_project/project_registry.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 11 | function | `get_project_entries` | `keep` | `get_project_entries` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `my_project/tests/templates/checkpoint_roundtrip_template.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 6 | function | `test_component_checkpoint_roundtrip_template` | `keep` | `test_component_checkpoint_roundtrip_template` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `my_project/tests/templates/contract_template.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 6 | function | `test_component_contract_template` | `keep` | `test_component_contract_template` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `my_project/tests/templates/smoke_template.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 6 | function | `test_component_smoke_template` | `keep` | `test_component_smoke_template` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `my_project/tests/templates/strict_fault_template.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 6 | function | `test_component_strict_fault_template` | `keep` | `test_component_strict_fault_template` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `nsgablack/__init__.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 114 | function | `get_version` | `keep` | `get_version` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 119 | function | `get_package_info` | `keep` | `get_package_info` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 124 | function | `get_available_features` | `keep` | `get_available_features` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 127 | function | `get_available_features._has_mod` | `keep` | `_has_mod` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `nsgablack/__main__.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 54 | function | `_ensure_utf8_io` | `keep` | `_ensure_utf8_io` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 66 | function | `_kind_label` | `keep` | `_kind_label` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 71 | function | `_print_entries` | `keep` | `_print_entries` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 106 | function | `_normalize_contract_values` | `keep` | `_normalize_contract_values` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 117 | function | `_collect_contract_fields` | `keep` | `_collect_contract_fields` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 136 | function | `_iter_contract_fields` | `keep` | `_iter_contract_fields` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 167 | function | `_print_contract_fields` | `keep` | `_print_contract_fields` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 178 | function | `_print_usage_fields` | `keep` | `_print_usage_fields` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 183 | function | `_print_usage_fields._print_list` | `keep` | `_print_list` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 198 | function | `_cmd_catalog_search` | `keep` | `_cmd_catalog_search` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 220 | function | `_cmd_catalog_list` | `keep` | `_cmd_catalog_list` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 243 | function | `_cmd_catalog_show` | `keep` | `_cmd_catalog_show` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 273 | function | `_cmd_catalog_add` | `keep` | `_cmd_catalog_add` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 300 | function | `_cmd_run_inspector` | `keep` | `_cmd_run_inspector` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 310 | function | `_cmd_project_init` | `keep` | `_cmd_project_init` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 322 | function | `_doctor_extract_line_column` | `keep` | `_doctor_extract_line_column` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 335 | function | `_doctor_severity` | `keep` | `_doctor_severity` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 339 | function | `_doctor_report_payload` | `keep` | `_doctor_report_payload` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 366 | function | `_format_doctor_problem_lines` | `keep` | `_format_doctor_problem_lines` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 382 | function | `_doctor_exit_code` | `keep` | `_doctor_exit_code` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 390 | function | `_doctor_print_report` | `keep` | `_doctor_print_report` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 401 | function | `_doctor_watch_signature` | `keep` | `_doctor_watch_signature` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 423 | function | `_cmd_project_doctor` | `keep` | `_cmd_project_doctor` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 431 | function | `_cmd_project_doctor._run_once` | `keep` | `_run_once` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 471 | function | `_cmd_project_catalog_search` | `keep` | `_cmd_project_catalog_search` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 497 | function | `_cmd_project_catalog_list` | `keep` | `_cmd_project_catalog_list` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 524 | function | `_cmd_project_catalog_show` | `keep` | `_cmd_project_catalog_show` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 551 | function | `_add_common_filters` | `keep` | `_add_common_filters` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 569 | function | `build_parser` | `keep` | `build_parser` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 718 | function | `main` | `keep` | `main` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `nsgablack/examples_registry.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 11 | function | `_path` | `keep` | `_path` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 15 | function | `template_continuous_constrained` | `keep` | `template_continuous_constrained` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 19 | function | `template_knapsack_binary` | `keep` | `template_knapsack_binary` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 23 | function | `template_tsp_permutation` | `keep` | `template_tsp_permutation` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 27 | function | `template_multiobjective_pareto` | `keep` | `template_multiobjective_pareto` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 31 | function | `template_assignment_matrix` | `keep` | `template_assignment_matrix` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 35 | function | `template_graph_path` | `keep` | `template_graph_path` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 39 | function | `template_production_schedule_simple` | `keep` | `template_production_schedule_simple` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 43 | function | `template_portfolio_pareto` | `keep` | `template_portfolio_pareto` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 47 | function | `dynamic_multi_strategy_demo` | `keep` | `dynamic_multi_strategy_demo` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 51 | function | `trust_region_dfo_demo` | `keep` | `trust_region_dfo_demo` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 55 | function | `trust_region_subspace_demo` | `keep` | `trust_region_subspace_demo` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 59 | function | `monte_carlo_dp_robust_demo` | `keep` | `monte_carlo_dp_robust_demo` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 63 | function | `surrogate_plugin_demo` | `keep` | `surrogate_plugin_demo` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 67 | function | `multi_fidelity_demo` | `keep` | `multi_fidelity_demo` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 71 | function | `risk_bias_demo` | `keep` | `risk_bias_demo` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 75 | function | `bias_gallery_demo` | `keep` | `bias_gallery_demo` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 79 | function | `plugin_gallery_demo` | `keep` | `plugin_gallery_demo` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 83 | function | `role_adapters_demo` | `keep` | `role_adapters_demo` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 87 | function | `astar_demo` | `keep` | `astar_demo` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 91 | function | `moa_star_demo` | `keep` | `moa_star_demo` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 95 | function | `parallel_repair_demo` | `keep` | `parallel_repair_demo` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 99 | function | `nsga2_solver_demo` | `keep` | `nsga2_solver_demo` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 103 | function | `parallel_evaluator_demo` | `keep` | `parallel_evaluator_demo` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 107 | function | `context_keys_demo` | `keep` | `context_keys_demo` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 111 | function | `context_schema_demo` | `keep` | `context_schema_demo` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 115 | function | `logging_demo` | `keep` | `logging_demo` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 119 | function | `metrics_demo` | `keep` | `metrics_demo` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 123 | function | `dynamic_cli_signal_demo` | `keep` | `dynamic_cli_signal_demo` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 127 | function | `async_event_driven_demo` | `keep` | `async_event_driven_demo` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 131 | function | `single_trajectory_adaptive_demo` | `keep` | `single_trajectory_adaptive_demo` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 135 | function | `gpu_ray_mysql_stack_demo` | `keep` | `gpu_ray_mysql_stack_demo` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `plugins/base.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 27 | class | `Plugin` | `keep` | `Plugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 37 | method | `Plugin.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 57 | method | `Plugin.get_context_contract` | `keep` | `get_context_contract` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 67 | method | `Plugin.create_local_rng` | `keep` | `create_local_rng` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 91 | method | `Plugin.attach` | `keep` | `attach` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 95 | method | `Plugin.detach` | `keep` | `detach` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 99 | method | `Plugin.enable` | `keep` | `enable` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 103 | method | `Plugin.disable` | `keep` | `disable` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 107 | method | `Plugin.configure` | `keep` | `configure` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 111 | method | `Plugin.get_config` | `keep` | `get_config` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 116 | method | `Plugin.on_solver_init` | `keep` | `on_solver_init` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 119 | method | `Plugin.on_population_init` | `keep` | `on_population_init` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 122 | method | `Plugin.on_generation_start` | `keep` | `on_generation_start` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 125 | method | `Plugin.on_generation_end` | `keep` | `on_generation_end` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 128 | method | `Plugin.on_step` | `keep` | `on_step` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 131 | method | `Plugin.on_solver_finish` | `keep` | `on_solver_finish` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 134 | method | `Plugin.get_report` | `keep` | `get_report` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 152 | method | `Plugin.get_population_snapshot` | `keep` | `get_population_snapshot` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 272 | method | `Plugin.commit_population_snapshot` | `keep` | `commit_population_snapshot` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 363 | method | `Plugin.__repr__` | `keep` | `__repr__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 368 | class | `PluginManager` | `keep` | `PluginManager` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 371 | method | `PluginManager.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 387 | method | `PluginManager.set_event_hook` | `keep` | `set_event_hook` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 391 | method | `PluginManager._emit_event_hook` | `keep` | `_emit_event_hook` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 409 | method | `PluginManager._safe_values_differ` | `keep` | `_safe_values_differ` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 430 | method | `PluginManager._collect_changed_keys` | `keep` | `_collect_changed_keys` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 441 | method | `PluginManager.register` | `keep` | `register` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 452 | method | `PluginManager.unregister` | `keep` | `unregister` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 461 | method | `PluginManager.get` | `keep` | `get` | `high` | `-` | 通用存取方法，参数别名规则不适用。 |
| 465 | method | `PluginManager.enable` | `keep` | `enable` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 470 | method | `PluginManager.disable` | `keep` | `disable` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 475 | method | `PluginManager.set_execution_order` | `keep` | `set_execution_order` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 498 | method | `PluginManager.trigger` | `keep` | `trigger` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 576 | method | `PluginManager.dispatch` | `keep` | `dispatch` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 676 | method | `PluginManager.on_solver_init` | `keep` | `on_solver_init` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 699 | method | `PluginManager.on_population_init` | `keep` | `on_population_init` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 702 | method | `PluginManager.on_generation_start` | `keep` | `on_generation_start` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 705 | method | `PluginManager.on_generation_end` | `keep` | `on_generation_end` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 708 | method | `PluginManager.on_step` | `keep` | `on_step` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 711 | method | `PluginManager.on_solver_finish` | `keep` | `on_solver_finish` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 714 | method | `PluginManager.list_plugins` | `keep` | `list_plugins` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 720 | method | `PluginManager.clear` | `keep` | `clear` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 725 | method | `PluginManager.__len__` | `keep` | `__len__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 728 | method | `PluginManager.__repr__` | `keep` | `__repr__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |

### `plugins/evaluation/broyden_solver_plugin.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 17 | class | `BroydenSolverProviderPlugin` | `keep` | `BroydenSolverProviderPlugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 26 | method | `BroydenSolverProviderPlugin.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 29 | method | `BroydenSolverProviderPlugin.solve_backend` | `keep` | `solve_backend` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 39 | method | `BroydenSolverProviderPlugin.solve_backend._callback` | `keep` | `_callback` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `plugins/evaluation/evaluation_model.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 18 | class | `EvaluationModelConfig` | `keep` | `EvaluationModelConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 25 | class | `EvaluationModelProviderPlugin` | `keep` | `EvaluationModelProviderPlugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 36 | method | `EvaluationModelProviderPlugin.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 51 | method | `EvaluationModelProviderPlugin._scope_enabled` | `keep` | `_scope_enabled` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 57 | method | `EvaluationModelProviderPlugin._build_backend` | `keep` | `_build_backend` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 66 | method | `EvaluationModelProviderPlugin.evaluate_model` | `keep` | `evaluate_model` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 79 | method | `EvaluationModelProviderPlugin._update_metrics` | `keep` | `_update_metrics` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 98 | method | `EvaluationModelProviderPlugin.evaluate_individual_runtime` | `keep` | `evaluate_individual_runtime` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 147 | method | `EvaluationModelProviderPlugin.create_provider` | `keep` | `create_provider` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 150 | class | `EvaluationModelProviderPlugin.create_provider._Provider` | `keep` | `_Provider` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 155 | method | `EvaluationModelProviderPlugin._Provider.create_provider.can_handle_individual` | `keep` | `can_handle_individual` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 161 | method | `EvaluationModelProviderPlugin._Provider.create_provider.evaluate_individual` | `keep` | `evaluate_individual` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 169 | method | `EvaluationModelProviderPlugin._Provider.create_provider.can_handle_population` | `keep` | `can_handle_population` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 175 | method | `EvaluationModelProviderPlugin._Provider.create_provider.evaluate_population` | `keep` | `evaluate_population` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 181 | method | `EvaluationModelProviderPlugin._Provider.create_provider.evaluate_model` | `keep` | `evaluate_model` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `plugins/evaluation/gpu_evaluation_template.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 13 | class | `GpuEvaluationTemplateConfig` | `keep` | `GpuEvaluationTemplateConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 22 | class | `GpuEvaluationTemplateProviderPlugin` | `keep` | `GpuEvaluationTemplateProviderPlugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 34 | method | `GpuEvaluationTemplateProviderPlugin.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 46 | method | `GpuEvaluationTemplateProviderPlugin._select_backend` | `keep` | `_select_backend` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 67 | method | `GpuEvaluationTemplateProviderPlugin._evaluate_gpu_batch` | `keep` | `_evaluate_gpu_batch` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 74 | method | `GpuEvaluationTemplateProviderPlugin._evaluate_constraints` | `keep` | `_evaluate_constraints` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 88 | method | `GpuEvaluationTemplateProviderPlugin.evaluate_population_runtime` | `keep` | `evaluate_population_runtime` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 140 | method | `GpuEvaluationTemplateProviderPlugin.create_provider` | `keep` | `create_provider` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 143 | class | `GpuEvaluationTemplateProviderPlugin.create_provider._Provider` | `keep` | `_Provider` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 147 | method | `GpuEvaluationTemplateProviderPlugin._Provider.create_provider.can_handle_individual` | `keep` | `can_handle_individual` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 151 | method | `GpuEvaluationTemplateProviderPlugin._Provider.create_provider.evaluate_individual` | `keep` | `evaluate_individual` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 160 | method | `GpuEvaluationTemplateProviderPlugin._Provider.create_provider.can_handle_population` | `keep` | `can_handle_population` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 165 | method | `GpuEvaluationTemplateProviderPlugin._Provider.create_provider.evaluate_population` | `keep` | `evaluate_population` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `plugins/evaluation/multi_fidelity_evaluation.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 13 | class | `MultiFidelityEvaluationConfig` | `keep` | `MultiFidelityEvaluationConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 22 | class | `MultiFidelityEvaluationProviderPlugin` | `keep` | `MultiFidelityEvaluationProviderPlugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 35 | method | `MultiFidelityEvaluationProviderPlugin.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 48 | method | `MultiFidelityEvaluationProviderPlugin.evaluate_population_runtime` | `keep` | `evaluate_population_runtime` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 107 | method | `MultiFidelityEvaluationProviderPlugin._increment_evaluation_count` | `keep` | `_increment_evaluation_count` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 121 | method | `MultiFidelityEvaluationProviderPlugin._select_indices_for_high_fidelity` | `keep` | `_select_indices_for_high_fidelity` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 139 | method | `MultiFidelityEvaluationProviderPlugin._aggregate_objectives` | `keep` | `_aggregate_objectives` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 148 | method | `MultiFidelityEvaluationProviderPlugin.create_provider` | `keep` | `create_provider` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 151 | class | `MultiFidelityEvaluationProviderPlugin.create_provider._Provider` | `keep` | `_Provider` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 155 | method | `MultiFidelityEvaluationProviderPlugin._Provider.create_provider.can_handle_individual` | `keep` | `can_handle_individual` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 163 | method | `MultiFidelityEvaluationProviderPlugin._Provider.create_provider.evaluate_individual` | `keep` | `evaluate_individual` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 169 | method | `MultiFidelityEvaluationProviderPlugin._Provider.create_provider.can_handle_population` | `keep` | `can_handle_population` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 178 | method | `MultiFidelityEvaluationProviderPlugin._Provider.create_provider.evaluate_population` | `keep` | `evaluate_population` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `plugins/evaluation/newton_solver_plugin.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 17 | class | `NewtonSolverProviderPlugin` | `keep` | `NewtonSolverProviderPlugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 26 | method | `NewtonSolverProviderPlugin.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 29 | method | `NewtonSolverProviderPlugin.solve_backend` | `keep` | `solve_backend` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `plugins/evaluation/numerical_solver_base.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 30 | class | `NumericalSolveResult` | `keep` | `NumericalSolveResult` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 40 | class | `NumericalSolverConfig` | `keep` | `NumericalSolverConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 47 | class | `NumericalSolverProviderPlugin` | `keep` | `NumericalSolverProviderPlugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 64 | method | `NumericalSolverProviderPlugin.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 83 | method | `NumericalSolverProviderPlugin.solve_backend` | `keep` | `solve_backend` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 110 | method | `NumericalSolverProviderPlugin._extract_system` | `keep` | `_extract_system` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 131 | method | `NumericalSolverProviderPlugin._compute_violation` | `keep` | `_compute_violation` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 146 | method | `NumericalSolverProviderPlugin._apply_bias` | `keep` | `_apply_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 181 | method | `NumericalSolverProviderPlugin.evaluate_individual_runtime` | `keep` | `evaluate_individual_runtime` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 261 | method | `NumericalSolverProviderPlugin.get_report` | `keep` | `get_report` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 264 | method | `NumericalSolverProviderPlugin.create_provider` | `keep` | `create_provider` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 267 | class | `NumericalSolverProviderPlugin.create_provider._Provider` | `keep` | `_Provider` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 271 | method | `NumericalSolverProviderPlugin._Provider.create_provider.can_handle_individual` | `keep` | `can_handle_individual` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 276 | method | `NumericalSolverProviderPlugin._Provider.create_provider.evaluate_individual` | `keep` | `evaluate_individual` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 284 | method | `NumericalSolverProviderPlugin._Provider.create_provider.can_handle_population` | `keep` | `can_handle_population` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 290 | method | `NumericalSolverProviderPlugin._Provider.create_provider.evaluate_population` | `keep` | `evaluate_population` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `plugins/evaluation/surrogate_evaluation.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 22 | class | `SurrogateEvaluationConfig` | `keep` | `SurrogateEvaluationConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 45 | class | `SurrogateEvaluationProviderPlugin` | `keep` | `SurrogateEvaluationProviderPlugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 65 | method | `SurrogateEvaluationProviderPlugin.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 97 | method | `SurrogateEvaluationProviderPlugin.evaluate_population_runtime` | `keep` | `evaluate_population_runtime` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 186 | method | `SurrogateEvaluationProviderPlugin.create_provider` | `keep` | `create_provider` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 189 | class | `SurrogateEvaluationProviderPlugin.create_provider._Provider` | `keep` | `_Provider` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 193 | method | `SurrogateEvaluationProviderPlugin._Provider.create_provider.can_handle_individual` | `keep` | `can_handle_individual` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 198 | method | `SurrogateEvaluationProviderPlugin._Provider.create_provider.evaluate_individual` | `keep` | `evaluate_individual` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 204 | method | `SurrogateEvaluationProviderPlugin._Provider.create_provider.can_handle_population` | `keep` | `can_handle_population` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 209 | method | `SurrogateEvaluationProviderPlugin._Provider.create_provider.evaluate_population` | `keep` | `evaluate_population` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 218 | method | `SurrogateEvaluationProviderPlugin._append_training` | `keep` | `_append_training` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 228 | method | `SurrogateEvaluationProviderPlugin._maybe_retrain` | `keep` | `_maybe_retrain` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 239 | method | `SurrogateEvaluationProviderPlugin._select_indices_for_true_eval` | `keep` | `_select_indices_for_true_eval` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 265 | method | `SurrogateEvaluationProviderPlugin._aggregate_objectives` | `keep` | `_aggregate_objectives` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 274 | method | `SurrogateEvaluationProviderPlugin._true_evaluate` | `keep` | `_true_evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 319 | method | `SurrogateEvaluationProviderPlugin._increment_evaluation_count` | `keep` | `_increment_evaluation_count` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |


| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|


| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|

### `plugins/ops/benchmark_harness.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 31 | class | `BenchmarkHarnessConfig` | `keep` | `BenchmarkHarnessConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 46 | class | `BenchmarkHarnessPlugin` | `keep` | `BenchmarkHarnessPlugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 65 | method | `BenchmarkHarnessPlugin.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 82 | method | `BenchmarkHarnessPlugin.__del__` | `keep` | `__del__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 86 | method | `BenchmarkHarnessPlugin.on_solver_init` | `keep` | `on_solver_init` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 127 | method | `BenchmarkHarnessPlugin.on_generation_end` | `keep` | `on_generation_end` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 162 | method | `BenchmarkHarnessPlugin.on_solver_finish` | `keep` | `on_solver_finish` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 195 | method | `BenchmarkHarnessPlugin._close_writer` | `keep` | `_close_writer` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 207 | method | `BenchmarkHarnessPlugin._read_best_score` | `keep` | `_read_best_score` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 251 | method | `BenchmarkHarnessPlugin._read_phase` | `keep` | `_read_phase` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 265 | method | `BenchmarkHarnessPlugin._read_pareto_size` | `keep` | `_read_pareto_size` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 279 | method | `BenchmarkHarnessPlugin._read_adapter_projection` | `keep` | `_read_adapter_projection` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `plugins/ops/decision_trace.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 20 | class | `DecisionTraceConfig` | `keep` | `DecisionTraceConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 32 | class | `DecisionTracePlugin` | `keep` | `DecisionTracePlugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 41 | method | `DecisionTracePlugin.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 56 | method | `DecisionTracePlugin.on_solver_init` | `keep` | `on_solver_init` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 87 | method | `DecisionTracePlugin.on_generation_end` | `keep` | `on_generation_end` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 93 | method | `DecisionTracePlugin.on_solver_finish` | `keep` | `on_solver_finish` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 103 | method | `DecisionTracePlugin.record_decision` | `keep` | `record_decision` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 153 | method | `DecisionTracePlugin._wrap_method` | `keep` | `_wrap_method` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 166 | method | `DecisionTracePlugin._wrap_method._wrapped` | `keep` | `_wrapped` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 199 | method | `DecisionTracePlugin._restore_wrapped_methods` | `keep` | `_restore_wrapped_methods` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 207 | method | `DecisionTracePlugin._flush_summary` | `keep` | `_flush_summary` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `plugins/ops/module_report.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 24 | class | `ModuleReportConfig` | `keep` | `ModuleReportConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 30 | class | `ModuleReportPlugin` | `keep` | `ModuleReportPlugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 50 | method | `ModuleReportPlugin.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 61 | method | `ModuleReportPlugin.on_solver_init` | `keep` | `on_solver_init` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 67 | method | `ModuleReportPlugin.on_solver_finish` | `keep` | `on_solver_finish` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 113 | method | `ModuleReportPlugin._collect_modules` | `keep` | `_collect_modules` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 226 | method | `ModuleReportPlugin._collect_bias_contributions` | `keep` | `_collect_bias_contributions` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 254 | method | `ModuleReportPlugin._collect_bias_contributions._contrib` | `keep` | `_contrib` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 268 | method | `ModuleReportPlugin._render_bias_markdown` | `keep` | `_render_bias_markdown` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `plugins/ops/otel_tracing.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 16 | class | `OpenTelemetryTracingConfig` | `keep` | `OpenTelemetryTracingConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 27 | class | `OpenTelemetryTracingPlugin` | `keep` | `OpenTelemetryTracingPlugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 36 | method | `OpenTelemetryTracingPlugin.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 51 | method | `OpenTelemetryTracingPlugin.on_solver_init` | `keep` | `on_solver_init` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 100 | method | `OpenTelemetryTracingPlugin.on_solver_finish` | `keep` | `on_solver_finish` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 113 | method | `OpenTelemetryTracingPlugin._setup_tracer` | `keep` | `_setup_tracer` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 151 | method | `OpenTelemetryTracingPlugin._span_context` | `keep` | `_span_context` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 156 | class | `OpenTelemetryTracingPlugin._span_context._SpanCtx` | `keep` | `_SpanCtx` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 157 | method | `OpenTelemetryTracingPlugin._SpanCtx._span_context.__enter__` | `keep` | `__enter__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 167 | method | `OpenTelemetryTracingPlugin._SpanCtx._span_context.__exit__` | `keep` | `__exit__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 172 | method | `OpenTelemetryTracingPlugin._wrap_method` | `keep` | `_wrap_method` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 186 | method | `OpenTelemetryTracingPlugin._wrap_method._wrapped` | `keep` | `_wrapped` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 196 | method | `OpenTelemetryTracingPlugin._restore_wrapped_methods` | `keep` | `_restore_wrapped_methods` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `plugins/ops/profiler.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 24 | class | `ProfilerConfig` | `keep` | `ProfilerConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 31 | class | `ProfilerPlugin` | `keep` | `ProfilerPlugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 41 | method | `ProfilerPlugin.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 59 | method | `ProfilerPlugin.on_solver_init` | `keep` | `on_solver_init` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 73 | method | `ProfilerPlugin.on_generation_start` | `keep` | `on_generation_start` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 77 | method | `ProfilerPlugin.on_generation_end` | `keep` | `on_generation_end` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 117 | method | `ProfilerPlugin.on_solver_finish` | `keep` | `on_solver_finish` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 132 | method | `ProfilerPlugin._build_payload` | `keep` | `_build_payload` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 159 | method | `ProfilerPlugin._build_payload._pct` | `keep` | `_pct` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 186 | method | `ProfilerPlugin._read_adapter_projection` | `keep` | `_read_adapter_projection` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `plugins/ops/sensitivity_analysis.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 24 | function | `_set_attr_by_path` | `keep` | `_set_attr_by_path` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 44 | function | `_default_metric` | `keep` | `_default_metric` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 62 | class | `SensitivityParam` | `keep` | `SensitivityParam` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 71 | class | `SensitivityAnalysisConfig` | `keep` | `SensitivityAnalysisConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 81 | class | `SensitivityAnalysisPlugin` | `keep` | `SensitivityAnalysisPlugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 95 | method | `SensitivityAnalysisPlugin.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 105 | method | `SensitivityAnalysisPlugin.run_study` | `keep` | `run_study` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `plugins/ops/sequence_graph.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 19 | class | `SequenceGraphConfig` | `keep` | `SequenceGraphConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 38 | class | `SequenceGraphPlugin` | `keep` | `SequenceGraphPlugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 47 | method | `SequenceGraphPlugin.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 63 | method | `SequenceGraphPlugin.on_solver_init` | `keep` | `on_solver_init` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 90 | method | `SequenceGraphPlugin.on_solver_init._hook` | `keep` | `_hook` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 126 | method | `SequenceGraphPlugin.on_generation_end` | `keep` | `on_generation_end` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 137 | method | `SequenceGraphPlugin.on_solver_finish` | `keep` | `on_solver_finish` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 148 | method | `SequenceGraphPlugin.on_context_build` | `keep` | `on_context_build` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 153 | method | `SequenceGraphPlugin.record_event` | `keep` | `record_event` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 183 | method | `SequenceGraphPlugin._trace_start` | `keep` | `_trace_start` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 208 | method | `SequenceGraphPlugin._trace_end` | `keep` | `_trace_end` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 228 | method | `SequenceGraphPlugin._handle_plugin_event` | `keep` | `_handle_plugin_event` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 249 | method | `SequenceGraphPlugin._wrap_method` | `keep` | `_wrap_method` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 256 | method | `SequenceGraphPlugin._wrap_method._wrapped` | `keep` | `_wrapped` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 273 | method | `SequenceGraphPlugin._restore_wrapped_methods` | `keep` | `_restore_wrapped_methods` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 281 | method | `SequenceGraphPlugin._restore_event_hook` | `keep` | `_restore_event_hook` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 290 | method | `SequenceGraphPlugin._flush` | `keep` | `_flush` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |


| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|


| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 27 | class | `CompanionEventRules` | `keep` | `CompanionEventRules` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 36 | class | `CompanionOrchestratorConfig` | `keep` | `CompanionOrchestratorConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 62 | class | `CompanionTask` | `keep` | `CompanionTask` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 77 | class | `CompanionPhaseRun` | `keep` | `CompanionPhaseRun` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 92 | class | `CompanionPhaseScheduler` | `keep` | `CompanionPhaseScheduler` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 95 | method | `CompanionPhaseScheduler.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 98 | method | `CompanionPhaseScheduler.should_trigger` | `keep` | `should_trigger` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |


| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|

### `plugins/runtime/diversity_init.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 12 | class | `DiversityInitPlugin` | `keep` | `DiversityInitPlugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 25 | method | `DiversityInitPlugin.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 31 | method | `DiversityInitPlugin.on_solver_init` | `keep` | `on_solver_init` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 37 | method | `DiversityInitPlugin.on_population_init` | `keep` | `on_population_init` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 42 | method | `DiversityInitPlugin.on_generation_start` | `keep` | `on_generation_start` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 45 | method | `DiversityInitPlugin.on_generation_end` | `keep` | `on_generation_end` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 48 | method | `DiversityInitPlugin.on_solver_finish` | `keep` | `on_solver_finish` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 51 | method | `DiversityInitPlugin._compute_diversity` | `keep` | `_compute_diversity` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 70 | method | `DiversityInitPlugin.is_similar` | `keep` | `is_similar` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 81 | method | `DiversityInitPlugin.should_accept` | `keep` | `should_accept` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `plugins/runtime/dynamic_switch.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 13 | class | `DynamicSwitchPlugin` | `keep` | `DynamicSwitchPlugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 32 | method | `DynamicSwitchPlugin.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 50 | method | `DynamicSwitchPlugin.should_switch` | `keep` | `should_switch` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 53 | method | `DynamicSwitchPlugin.select_switch_mode` | `keep` | `select_switch_mode` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 58 | method | `DynamicSwitchPlugin.soft_switch` | `keep` | `soft_switch` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 63 | method | `DynamicSwitchPlugin.hard_switch` | `keep` | `hard_switch` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `plugins/runtime/elite_retention.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 18 | function | `_evaluate_candidate_with_solver` | `keep` | `_evaluate_candidate_with_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 38 | class | `BasicElitePlugin` | `keep` | `BasicElitePlugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 51 | method | `BasicElitePlugin.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 61 | method | `BasicElitePlugin.on_solver_init` | `keep` | `on_solver_init` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 68 | method | `BasicElitePlugin.on_population_init` | `keep` | `on_population_init` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 71 | method | `BasicElitePlugin.on_generation_start` | `keep` | `on_generation_start` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 74 | method | `BasicElitePlugin.on_context_build` | `keep` | `on_context_build` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 80 | method | `BasicElitePlugin.on_generation_end` | `keep` | `on_generation_end` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 92 | method | `BasicElitePlugin.on_solver_finish` | `keep` | `on_solver_finish` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 97 | method | `BasicElitePlugin._update_best_solution` | `keep` | `_update_best_solution` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 113 | method | `BasicElitePlugin._retain_elites` | `keep` | `_retain_elites` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 146 | class | `HistoricalElitePlugin` | `keep` | `HistoricalElitePlugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 159 | method | `HistoricalElitePlugin.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 174 | method | `HistoricalElitePlugin.on_solver_init` | `keep` | `on_solver_init` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 180 | method | `HistoricalElitePlugin.on_population_init` | `keep` | `on_population_init` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 183 | method | `HistoricalElitePlugin.on_generation_start` | `keep` | `on_generation_start` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 186 | method | `HistoricalElitePlugin.on_context_build` | `keep` | `on_context_build` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 192 | method | `HistoricalElitePlugin.on_generation_end` | `keep` | `on_generation_end` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 204 | method | `HistoricalElitePlugin.on_solver_finish` | `keep` | `on_solver_finish` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 208 | method | `HistoricalElitePlugin._update_best_and_archive` | `keep` | `_update_best_and_archive` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 246 | method | `HistoricalElitePlugin._historical_replacement` | `keep` | `_historical_replacement` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `plugins/runtime/pareto_archive.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 20 | class | `ParetoArchiveConfig` | `keep` | `ParetoArchiveConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 25 | class | `ParetoArchivePlugin` | `keep` | `ParetoArchivePlugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 39 | method | `ParetoArchivePlugin.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 51 | method | `ParetoArchivePlugin.on_generation_end` | `keep` | `on_generation_end` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 65 | method | `ParetoArchivePlugin._get_population` | `keep` | `_get_population` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 68 | method | `ParetoArchivePlugin._write_pareto_snapshot` | `keep` | `_write_pareto_snapshot` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 85 | method | `ParetoArchivePlugin._update_archive` | `keep` | `_update_archive` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 119 | method | `ParetoArchivePlugin._nondominated_mask` | `keep` | `_nondominated_mask` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 136 | method | `ParetoArchivePlugin._select_by_crowding` | `keep` | `_select_by_crowding` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `plugins/solver_backends/backend_contract.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 10 | class | `BackendSolveRequest` | `keep` | `BackendSolveRequest` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 18 | class | `BackendSolver` | `keep` | `BackendSolver` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 19 | method | `BackendSolver.solve` | `keep` | `solve` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 23 | function | `normalize_backend_output` | `keep` | `normalize_backend_output` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `plugins/solver_backends/contract_bridge.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 13 | class | `BridgeRule` | `keep` | `BridgeRule` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 20 | class | `ContractBridgePlugin` | `keep` | `ContractBridgePlugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 33 | method | `ContractBridgePlugin.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 46 | method | `ContractBridgePlugin._ensure_layers` | `keep` | `_ensure_layers` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 53 | method | `ContractBridgePlugin._ensure_log` | `keep` | `_ensure_log` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 60 | method | `ContractBridgePlugin.on_inner_result` | `keep` | `on_inner_result` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 123 | method | `ContractBridgePlugin.get_report` | `keep` | `get_report` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `plugins/solver_backends/copt_backend.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 23 | class | `CoptBackendConfig` | `keep` | `CoptBackendConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 33 | class | `CoptBackend` | `keep` | `CoptBackend` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 43 | method | `CoptBackend.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 69 | method | `CoptBackend._build_mock` | `keep` | `_build_mock` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 83 | method | `CoptBackend._resolve_callable` | `keep` | `_resolve_callable` | `high` | `-` | 该 resolve_* 属于推断/合并/派生语义，符合规范保留。 |
| 90 | method | `CoptBackend._resolve_mapping` | `keep` | `_resolve_mapping` | `high` | `-` | 该 resolve_* 属于推断/合并/派生语义，符合规范保留。 |
| 99 | method | `CoptBackend._as_1d` | `keep` | `_as_1d` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 105 | method | `CoptBackend._load_copt_module` | `keep` | `_load_copt_module` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 111 | method | `CoptBackend._set_parameter` | `keep` | `_set_parameter` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 119 | method | `CoptBackend._resolve_template_name` | `keep` | `_resolve_template_name` | `high` | `-` | 该 resolve_* 属于推断/合并/派生语义，符合规范保留。 |
| 128 | method | `CoptBackend._solve_linear_spec` | `keep` | `_solve_linear_spec` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 223 | method | `CoptBackend._solve_qp_spec` | `keep` | `_solve_qp_spec` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 340 | method | `CoptBackend._solve_by_template` | `keep` | `_solve_by_template` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 362 | method | `CoptBackend.solve` | `keep` | `solve` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `plugins/solver_backends/copt_templates/linear.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 24 | function | `solve_linear_template` | `keep` | `solve_linear_template` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `plugins/solver_backends/copt_templates/qp.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 26 | function | `solve_qp_template` | `keep` | `solve_qp_template` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `plugins/solver_backends/copt_templates/registry.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 10 | function | `build_default_templates` | `keep` | `build_default_templates` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 17 | function | `build_default_templates._linear` | `keep` | `_linear` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 26 | function | `build_default_templates._qp` | `keep` | `_qp` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `plugins/solver_backends/ngspice_backend.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 21 | function | `_decode_subprocess_bytes` | `keep` | `_decode_subprocess_bytes` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 44 | class | `NgspiceBackendConfig` | `keep` | `NgspiceBackendConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 53 | class | `NgspiceBackend` | `keep` | `NgspiceBackend` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 62 | method | `NgspiceBackend.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 73 | method | `NgspiceBackend._default_netlist` | `keep` | `_default_netlist` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 87 | method | `NgspiceBackend._parse_measure_lines` | `keep` | `_parse_measure_lines` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 99 | method | `NgspiceBackend._build_mock` | `keep` | `_build_mock` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 112 | method | `NgspiceBackend.solve` | `keep` | `solve` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `plugins/solver_backends/timeout_budget.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 11 | class | `TimeoutBudgetConfig` | `keep` | `TimeoutBudgetConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 18 | class | `TimeoutBudgetPlugin` | `keep` | `TimeoutBudgetPlugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 31 | method | `TimeoutBudgetPlugin.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 45 | method | `TimeoutBudgetPlugin.on_solver_init` | `keep` | `on_solver_init` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 53 | method | `TimeoutBudgetPlugin.on_inner_guard` | `keep` | `on_inner_guard` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 70 | method | `TimeoutBudgetPlugin.on_inner_result` | `keep` | `on_inner_result` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 77 | method | `TimeoutBudgetPlugin.get_report` | `keep` | `get_report` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `plugins/system/async_event_hub.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 13 | class | `AsyncEventHubConfig` | `keep` | `AsyncEventHubConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 21 | class | `AsyncEventHubPlugin` | `keep` | `AsyncEventHubPlugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 38 | method | `AsyncEventHubPlugin.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 48 | method | `AsyncEventHubPlugin.on_generation_start` | `keep` | `on_generation_start` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 51 | method | `AsyncEventHubPlugin.on_generation_end` | `keep` | `on_generation_end` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 55 | method | `AsyncEventHubPlugin.record_event` | `keep` | `record_event` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 100 | method | `AsyncEventHubPlugin.commit` | `keep` | `commit` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 122 | method | `AsyncEventHubPlugin.get_committed_context` | `keep` | `get_committed_context` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 125 | method | `AsyncEventHubPlugin.get_report` | `keep` | `get_report` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `plugins/system/boundary_guard.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 12 | class | `BoundaryGuardConfig` | `keep` | `BoundaryGuardConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 20 | class | `BoundaryGuardPlugin` | `keep` | `BoundaryGuardPlugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 35 | method | `BoundaryGuardPlugin.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 41 | method | `BoundaryGuardPlugin.on_generation_end` | `keep` | `on_generation_end` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 73 | method | `BoundaryGuardPlugin.get_report` | `keep` | `get_report` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `plugins/system/memory_optimize.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 13 | class | `MemoryPlugin` | `keep` | `MemoryPlugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 25 | method | `MemoryPlugin.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 31 | method | `MemoryPlugin.on_solver_init` | `keep` | `on_solver_init` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 35 | method | `MemoryPlugin.on_population_init` | `keep` | `on_population_init` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 38 | method | `MemoryPlugin.on_generation_start` | `keep` | `on_generation_start` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 41 | method | `MemoryPlugin.on_generation_end` | `keep` | `on_generation_end` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 46 | method | `MemoryPlugin.on_solver_finish` | `keep` | `on_solver_finish` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 51 | method | `MemoryPlugin._cleanup_memory` | `keep` | `_cleanup_memory` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 69 | method | `MemoryPlugin._optimize_arrays` | `keep` | `_optimize_arrays` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 80 | method | `MemoryPlugin._take_memory_snapshot` | `keep` | `_take_memory_snapshot` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 97 | method | `MemoryPlugin.get_memory_usage` | `keep` | `get_memory_usage` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `project/catalog.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 25 | function | `find_project_root` | `keep` | `find_project_root` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 36 | function | `_load_registry_module` | `keep` | `_load_registry_module` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 45 | function | `_coerce_entry` | `keep` | `_coerce_entry` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 53 | function | `_normalize_project_entries` | `keep` | `_normalize_project_entries` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 83 | function | `_load_project_toml_entries` | `keep` | `_load_project_toml_entries` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 110 | function | `load_project_entries` | `keep` | `load_project_entries` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 141 | function | `load_project_catalog` | `keep` | `load_project_catalog` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 153 | function | `export_project_entries` | `keep` | `export_project_entries` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `project/doctor_core/model.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 11 | class | `DoctorDiagnostic` | `keep` | `DoctorDiagnostic` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 21 | class | `DoctorReport` | `keep` | `DoctorReport` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 28 | method | `DoctorReport.error_count` | `keep` | `error_count` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 32 | method | `DoctorReport.warn_count` | `keep` | `warn_count` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 36 | method | `DoctorReport.info_count` | `keep` | `info_count` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 40 | function | `add_diagnostic` | `keep` | `add_diagnostic` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 57 | function | `format_doctor_report_text` | `keep` | `format_doctor_report_text` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 70 | function | `iter_diagnostics_by_level` | `keep` | `iter_diagnostics_by_level` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `project/doctor_core/rules/adapter_purity.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 12 | function | `check_adapter_layer_purity` | `keep` | `check_adapter_layer_purity` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `project/doctor_core/rules/broad_except.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 12 | function | `_is_broad_exception_type` | `keep` | `_is_broad_exception_type` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 22 | function | `_handler_body_is_swallow` | `keep` | `_handler_body_is_swallow` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 34 | function | `check_broad_exception_swallow` | `keep` | `check_broad_exception_swallow` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `project/doctor_core/rules/build_solver.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 13 | function | `_load_module_from_file` | `keep` | `_load_module_from_file` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 22 | function | `check_build_solver` | `keep` | `check_build_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `project/doctor_core/rules/component_catalog.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 11 | function | `collect_solver_components` | `keep` | `collect_solver_components` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 15 | function | `collect_solver_components._add` | `keep` | `_add` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 52 | function | `collect_bias_instances` | `keep` | `collect_bias_instances` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 80 | function | `_component_import_path` | `keep` | `_component_import_path` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 91 | function | `check_process_like_bias_usage` | `keep` | `check_process_like_bias_usage` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 126 | function | `check_component_catalog_registration` | `keep` | `check_component_catalog_registration` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `project/doctor_core/rules/component_order.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 15 | class | `_OrderAction` | `keep` | `_OrderAction` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 30 | class | `_PluginClassSpec` | `keep` | `_PluginClassSpec` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 43 | function | `_literal_string_set` | `keep` | `_literal_string_set` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 58 | function | `_literal_int` | `keep` | `_literal_int` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 64 | function | `_infer_call_name_and_priority` | `keep` | `_infer_call_name_and_priority` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 88 | class | `_OrderActionCollector` | `keep` | `_OrderActionCollector` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 89 | method | `_OrderActionCollector.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 92 | method | `_OrderActionCollector.visit_Call` | `keep` | `visit_Call` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 102 | method | `_OrderActionCollector._parse_add_plugin` | `keep` | `_parse_add_plugin` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 144 | method | `_OrderActionCollector._parse_set_plugin_order` | `keep` | `_parse_set_plugin_order` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 194 | function | `_classify_component_order_error` | `keep` | `_classify_component_order_error` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 209 | function | `_extract_class_string_list_assignments` | `keep` | `_extract_class_string_list_assignments` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 232 | function | `_extract_class_literal_int_assignments` | `keep` | `_extract_class_literal_int_assignments` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 247 | function | `_infer_component_name_and_priority` | `keep` | `_infer_component_name_and_priority` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 272 | function | `_collect_plugin_class_specs` | `keep` | `_collect_plugin_class_specs` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 312 | function | `_collect_declared_plugin_names` | `keep` | `_collect_declared_plugin_names` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 348 | function | `_check_plugin_class_order_declarations` | `keep` | `_check_plugin_class_order_declarations` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 428 | function | `check_component_order_constraints` | `keep` | `check_component_order_constraints` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `project/doctor_core/rules/contract_source.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 105 | function | `_class_has_contract` | `keep` | `_class_has_contract` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 118 | function | `_class_missing_core_contract_fields` | `keep` | `_class_missing_core_contract_fields` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 135 | function | `_extract_literal_string_values` | `keep` | `_extract_literal_string_values` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 155 | function | `_literal_str_value` | `keep` | `_literal_str_value` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 161 | function | `_iter_declared_contract_literals` | `keep` | `_iter_declared_contract_literals` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 197 | function | `_collect_declared_contract_keys` | `keep` | `_collect_declared_contract_keys` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 209 | function | `_is_known_context_key` | `keep` | `_is_known_context_key` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 220 | function | `_is_declared_key_covered` | `keep` | `_is_declared_key_covered` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 231 | function | `_collect_context_aliases` | `keep` | `_collect_context_aliases` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 259 | function | `_extract_context_subscript_key` | `keep` | `_extract_context_subscript_key` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 271 | function | `_extract_call_key` | `keep` | `_extract_call_key` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 281 | function | `_collect_target_context_writes` | `keep` | `_collect_target_context_writes` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 292 | function | `_extract_context_reads_writes` | `keep` | `_extract_context_reads_writes` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 358 | function | `_iter_class_attr_values` | `keep` | `_iter_class_attr_values` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 371 | function | `_check_class_metrics_fallback_literal` | `keep` | `_check_class_metrics_fallback_literal` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 407 | function | `_base_name` | `keep` | `_base_name` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 415 | function | `_is_component_class` | `keep` | `_is_component_class` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 434 | function | `_is_not_implemented_raise` | `keep` | `_is_not_implemented_raise` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 451 | function | `_has_abstractmethod_decorator` | `keep` | `_has_abstractmethod_decorator` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 460 | function | `_check_class_template_not_implemented` | `keep` | `_check_class_template_not_implemented` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 492 | function | `_check_class_contract_key_known` | `keep` | `_check_class_contract_key_known` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 524 | function | `_check_class_contract_impl_alignment` | `keep` | `_check_class_contract_impl_alignment` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 582 | function | `_class_defines_method` | `keep` | `_class_defines_method` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 589 | function | `_check_class_state_recovery_declaration` | `keep` | `_check_class_state_recovery_declaration` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 657 | function | `check_contract_source` | `keep` | `check_contract_source` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `project/doctor_core/rules/metrics_provider.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 11 | function | `_iter_metric_requires` | `keep` | `_iter_metric_requires` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 36 | function | `_read_metrics_fallback_value` | `keep` | `_read_metrics_fallback_value` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 46 | function | `_is_valid_metrics_fallback_value` | `keep` | `_is_valid_metrics_fallback_value` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 50 | function | `_has_metrics_fallback` | `keep` | `_has_metrics_fallback` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 60 | function | `check_metrics_provider_alignment` | `keep` | `check_metrics_provider_alignment` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `project/doctor_core/rules/registry_checks.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 12 | function | `_resolve_import_path` | `keep` | `_resolve_import_path` | `high` | `-` | 该 resolve_* 属于推断/合并/派生语义，符合规范保留。 |
| 23 | function | `check_registry` | `keep` | `check_registry` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `project/doctor_core/rules/runtime_governance.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 12 | function | `_iter_py_files` | `keep` | `_iter_py_files` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 23 | function | `_parse_file` | `keep` | `_parse_file` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 30 | function | `_is_plugin_class` | `keep` | `_is_plugin_class` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 39 | function | `check_no_plugin_evaluation_short_circuit` | `keep` | `check_no_plugin_evaluation_short_circuit` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 77 | function | `check_runtime_governance_runtime_state` | `keep` | `check_runtime_governance_runtime_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `project/doctor_core/rules/runtime_surface.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 13 | function | `_has_path_part` | `keep` | `_has_path_part` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 18 | function | `_is_python_test_file` | `keep` | `_is_python_test_file` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 23 | function | `_is_skip_path` | `keep` | `_is_skip_path` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 38 | function | `_iter_runtime_surface_files` | `keep` | `_iter_runtime_surface_files` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 80 | function | `check_runtime_private_surface` | `keep` | `check_runtime_private_surface` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `project/doctor_core/rules/scaffold.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 11 | function | `looks_like_scaffold_project` | `keep` | `looks_like_scaffold_project` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 15 | function | `check_structure` | `keep` | `check_structure` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `project/doctor_core/rules/snapshot_context_policy.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 33 | function | `_normalize_token` | `keep` | `_normalize_token` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 37 | function | `check_context_store_policy` | `keep` | `check_context_store_policy` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 132 | function | `check_snapshot_store_policy` | `keep` | `check_snapshot_store_policy` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 248 | function | `_safe_first_dim` | `keep` | `_safe_first_dim` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 264 | function | `check_snapshot_refs` | `keep` | `check_snapshot_refs` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 345 | function | `check_snapshot_refs._read_snapshot_cached` | `keep` | `_read_snapshot_cached` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 470 | function | `_extract_key_str` | `keep` | `_extract_key_str` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 479 | function | `_scan_py_file_for_large_context_writes` | `keep` | `_scan_py_file_for_large_context_writes` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 509 | function | `check_large_objects_in_context` | `keep` | `check_large_objects_in_context` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `project/scaffold.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 35 | function | `_write_file` | `keep` | `_write_file` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 41 | function | `_readme_for_folder` | `keep` | `_readme_for_folder` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 69 | function | `_root_readme` | `keep` | `_root_readme` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 102 | function | `_start_here` | `keep` | `_start_here` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 194 | function | `_component_registration_guide` | `keep` | `_component_registration_guide` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 243 | function | `_component_contract_template` | `keep` | `_component_contract_template` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 287 | function | `_component_test_matrix_readme` | `keep` | `_component_test_matrix_readme` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 303 | function | `_smoke_test_template` | `keep` | `_smoke_test_template` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 317 | function | `_contract_test_template` | `keep` | `_contract_test_template` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 331 | function | `_checkpoint_roundtrip_test_template` | `keep` | `_checkpoint_roundtrip_test_template` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 345 | function | `_strict_fault_test_template` | `keep` | `_strict_fault_test_template` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 359 | function | `_problem_template` | `keep` | `_problem_template` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 395 | function | `_problem_class_template` | `keep` | `_problem_class_template` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 436 | function | `_pipeline_template` | `keep` | `_pipeline_template` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 469 | function | `_pipeline_class_template` | `keep` | `_pipeline_class_template` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 531 | function | `_bias_template` | `keep` | `_bias_template` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 558 | function | `_bias_class_template` | `keep` | `_bias_class_template` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 596 | function | `_adapter_class_template` | `keep` | `_adapter_class_template` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 655 | function | `_plugin_template` | `keep` | `_plugin_template` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 711 | function | `_adapter_readme` | `keep` | `_adapter_readme` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 734 | function | `_plugin_readme` | `keep` | `_plugin_readme` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 756 | function | `_plugin_class_template` | `keep` | `_plugin_class_template` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 810 | function | `_project_registry_template` | `keep` | `_project_registry_template` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 830 | function | `_project_catalog_entries_template` | `keep` | `_project_catalog_entries_template` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 918 | function | `_build_solver_template` | `keep` | `_build_solver_template` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1239 | function | `_build_solver_registration_guide_template` | `keep` | `_build_solver_registration_guide_template` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1326 | function | `_vscode_snippets_template` | `keep` | `_vscode_snippets_template` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1425 | function | `init_project` | `keep` | `init_project` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `representation/base.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 15 | class | `EncodingPlugin` | `keep` | `EncodingPlugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 16 | method | `EncodingPlugin.encode` | `keep` | `encode` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 19 | method | `EncodingPlugin.decode` | `keep` | `decode` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 23 | class | `RepairPlugin` | `keep` | `RepairPlugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 24 | method | `RepairPlugin.repair` | `keep` | `repair` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 28 | class | `RepresentationComponentContract` | `keep` | `RepresentationComponentContract` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 38 | function | `_parallel_repair_task` | `keep` | `_parallel_repair_task` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 44 | class | `ParallelRepair` | `keep` | `ParallelRepair` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 58 | method | `ParallelRepair.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 82 | method | `ParallelRepair._report_error` | `keep` | `_report_error` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 98 | method | `ParallelRepair.repair` | `keep` | `repair` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 101 | method | `ParallelRepair.repair_batch` | `keep` | `repair_batch` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 179 | class | `InitPlugin` | `keep` | `InitPlugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 180 | method | `InitPlugin.initialize` | `keep` | `initialize` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 184 | class | `MutationPlugin` | `keep` | `MutationPlugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 185 | method | `MutationPlugin.mutate` | `keep` | `mutate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 189 | class | `CrossoverPlugin` | `keep` | `CrossoverPlugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 190 | method | `CrossoverPlugin.crossover` | `keep` | `crossover` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 195 | class | `RepresentationPipeline` | `keep` | `RepresentationPipeline` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 221 | method | `RepresentationPipeline.get_context_contract` | `keep` | `get_context_contract` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 261 | method | `RepresentationPipeline._maybe_lock` | `keep` | `_maybe_lock` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 264 | method | `RepresentationPipeline._prepare_context` | `keep` | `_prepare_context` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 274 | method | `RepresentationPipeline._prepare_input` | `keep` | `_prepare_input` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 281 | method | `RepresentationPipeline.init` | `keep` | `init` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 315 | method | `RepresentationPipeline.mutate` | `keep` | `mutate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 334 | method | `RepresentationPipeline.repair_one` | `keep` | `repair_one` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 352 | method | `RepresentationPipeline.encode_batch` | `keep` | `encode_batch` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 361 | method | `RepresentationPipeline.decode_batch` | `keep` | `decode_batch` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 370 | method | `RepresentationPipeline.repair_batch` | `keep` | `repair_batch` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 379 | method | `RepresentationPipeline.mutate_batch` | `keep` | `mutate_batch` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 389 | method | `RepresentationPipeline.decode` | `keep` | `decode` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 394 | method | `RepresentationPipeline.encode` | `keep` | `encode` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 402 | method | `RepresentationPipeline._choose_initializer` | `keep` | `_choose_initializer` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 414 | method | `RepresentationPipeline._is_feasible` | `keep` | `_is_feasible` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 427 | function | `_bounds_to_arrays` | `keep` | `_bounds_to_arrays` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 438 | class | `ContinuousRepresentation` | `keep` | `ContinuousRepresentation` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 446 | method | `ContinuousRepresentation.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 452 | method | `ContinuousRepresentation.add_constraint` | `keep` | `add_constraint` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 455 | method | `ContinuousRepresentation.check_constraints` | `keep` | `check_constraints` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 461 | method | `ContinuousRepresentation.encode` | `keep` | `encode` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 464 | method | `ContinuousRepresentation.decode` | `keep` | `decode` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 468 | method | `ContinuousRepresentation.repair` | `keep` | `repair` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 475 | class | `IntegerRepresentation` | `keep` | `IntegerRepresentation` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 483 | method | `IntegerRepresentation.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 489 | method | `IntegerRepresentation.add_constraint` | `keep` | `add_constraint` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 492 | method | `IntegerRepresentation.check_constraints` | `keep` | `check_constraints` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 498 | method | `IntegerRepresentation.encode` | `keep` | `encode` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 503 | method | `IntegerRepresentation.decode` | `keep` | `decode` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 509 | method | `IntegerRepresentation.repair` | `keep` | `repair` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 516 | class | `PermutationRepresentation` | `keep` | `PermutationRepresentation` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 524 | method | `PermutationRepresentation.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 529 | method | `PermutationRepresentation.encode` | `keep` | `encode` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 535 | method | `PermutationRepresentation.decode` | `keep` | `decode` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 541 | method | `PermutationRepresentation.generate_random` | `keep` | `generate_random` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 545 | class | `MixedRepresentation` | `keep` | `MixedRepresentation` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 552 | method | `MixedRepresentation.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 557 | method | `MixedRepresentation._rep_key` | `keep` | `_rep_key` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 563 | method | `MixedRepresentation._select_input` | `keep` | `_select_input` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 574 | method | `MixedRepresentation.encode` | `keep` | `encode` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 582 | method | `MixedRepresentation.decode` | `keep` | `decode` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 594 | function | `_fix_permutation` | `keep` | `_fix_permutation` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `representation/binary.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 18 | class | `BinaryInitializer` | `keep` | `BinaryInitializer` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 26 | method | `BinaryInitializer.__post_init__` | `keep` | `__post_init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 29 | method | `BinaryInitializer.initialize` | `keep` | `initialize` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 34 | class | `BitFlipMutation` | `keep` | `BitFlipMutation` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 42 | method | `BitFlipMutation.__post_init__` | `keep` | `__post_init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 45 | method | `BitFlipMutation.mutate` | `keep` | `mutate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 53 | class | `BinaryRepair` | `keep` | `BinaryRepair` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 61 | method | `BinaryRepair.repair` | `keep` | `repair` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 66 | class | `BinaryCapacityRepair` | `keep` | `BinaryCapacityRepair` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 75 | method | `BinaryCapacityRepair.__post_init__` | `keep` | `__post_init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 78 | method | `BinaryCapacityRepair.repair` | `keep` | `repair` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `representation/constraints.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 13 | function | `_bounds_to_arrays` | `keep` | `_bounds_to_arrays` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 20 | class | `BoundConstraint` | `keep` | `BoundConstraint` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 27 | method | `BoundConstraint.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 31 | method | `BoundConstraint.check` | `keep` | `check` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 35 | method | `BoundConstraint.repair` | `keep` | `repair` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `representation/context_mutators.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 20 | function | `_call_mutate` | `keep` | `_call_mutate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 28 | class | `ContextSelectMutator` | `keep` | `ContextSelectMutator` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 46 | method | `ContextSelectMutator.mutate` | `keep` | `mutate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 62 | class | `SerialMutator` | `keep` | `SerialMutator` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 75 | method | `SerialMutator.mutate` | `keep` | `mutate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 90 | class | `ContextDispatchMutator` | `keep` | `ContextDispatchMutator` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 105 | method | `ContextDispatchMutator.mutate` | `keep` | `mutate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `representation/continuous.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 16 | function | `_as_bound_array` | `keep` | `_as_bound_array` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 27 | function | `_resolve_bounds` | `keep` | `_resolve_bounds` | `high` | `-` | 该 resolve_* 属于推断/合并/派生语义，符合规范保留。 |
| 73 | class | `UniformInitializer` | `keep` | `UniformInitializer` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 82 | method | `UniformInitializer.__post_init__` | `keep` | `__post_init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 85 | method | `UniformInitializer.initialize` | `keep` | `initialize` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 90 | class | `GaussianMutation` | `keep` | `GaussianMutation` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 100 | method | `GaussianMutation.__post_init__` | `keep` | `__post_init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 103 | method | `GaussianMutation.mutate` | `keep` | `mutate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 111 | class | `PolynomialMutation` | `keep` | `PolynomialMutation` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 124 | method | `PolynomialMutation.__post_init__` | `keep` | `__post_init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 127 | method | `PolynomialMutation.mutate` | `keep` | `mutate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 155 | class | `ContextGaussianMutation` | `keep` | `ContextGaussianMutation` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 174 | method | `ContextGaussianMutation.__post_init__` | `keep` | `__post_init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 177 | method | `ContextGaussianMutation.mutate` | `keep` | `mutate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 191 | class | `SBXCrossover` | `keep` | `SBXCrossover` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 203 | method | `SBXCrossover.__post_init__` | `keep` | `__post_init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 206 | method | `SBXCrossover.crossover` | `keep` | `crossover` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 228 | class | `ClipRepair` | `keep` | `ClipRepair` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 237 | method | `ClipRepair.repair` | `keep` | `repair` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 241 | function | `_project_to_simplex` | `keep` | `_project_to_simplex` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 261 | class | `ProjectionRepair` | `keep` | `ProjectionRepair` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 283 | method | `ProjectionRepair.repair` | `keep` | `repair` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `representation/dynamic.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 15 | class | `DynamicRepair` | `keep` | `DynamicRepair` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 29 | method | `DynamicRepair.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 32 | method | `DynamicRepair.repair` | `keep` | `repair` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `representation/graph.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 17 | class | `GraphEdgeInitializer` | `keep` | `GraphEdgeInitializer` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 26 | method | `GraphEdgeInitializer.__post_init__` | `keep` | `__post_init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 29 | method | `GraphEdgeInitializer.initialize` | `keep` | `initialize` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 44 | class | `GraphEdgeMutation` | `keep` | `GraphEdgeMutation` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 52 | method | `GraphEdgeMutation.__post_init__` | `keep` | `__post_init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 55 | method | `GraphEdgeMutation.mutate` | `keep` | `mutate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 62 | function | `_edge_index_to_pair` | `keep` | `_edge_index_to_pair` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 72 | function | `_pair_to_edge_index` | `keep` | `_pair_to_edge_index` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 85 | class | `GraphConnectivityRepair` | `keep` | `GraphConnectivityRepair` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 92 | method | `GraphConnectivityRepair.__post_init__` | `keep` | `__post_init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 95 | method | `GraphConnectivityRepair.repair` | `keep` | `repair` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 139 | class | `GraphDegreeRepair` | `keep` | `GraphDegreeRepair` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 148 | method | `GraphDegreeRepair.__post_init__` | `keep` | `__post_init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 151 | method | `GraphDegreeRepair.repair` | `keep` | `repair` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `representation/integer.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 16 | function | `_get_bounds` | `keep` | `_get_bounds` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 42 | class | `IntegerInitializer` | `keep` | `IntegerInitializer` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 51 | method | `IntegerInitializer.__post_init__` | `keep` | `__post_init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 54 | method | `IntegerInitializer.initialize` | `keep` | `initialize` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 68 | class | `IntegerRepair` | `keep` | `IntegerRepair` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 77 | method | `IntegerRepair.repair` | `keep` | `repair` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 97 | class | `IntegerMutation` | `keep` | `IntegerMutation` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 107 | method | `IntegerMutation.__post_init__` | `keep` | `__post_init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 110 | method | `IntegerMutation.mutate` | `keep` | `mutate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `representation/matrix.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 24 | function | `_shape_from_context` | `keep` | `_shape_from_context` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 36 | class | `IntegerMatrixInitializer` | `keep` | `IntegerMatrixInitializer` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 47 | method | `IntegerMatrixInitializer.__post_init__` | `keep` | `__post_init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 50 | method | `IntegerMatrixInitializer.initialize` | `keep` | `initialize` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 60 | class | `IntegerMatrixMutation` | `keep` | `IntegerMatrixMutation` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 70 | method | `IntegerMatrixMutation.__post_init__` | `keep` | `__post_init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 73 | method | `IntegerMatrixMutation.mutate` | `keep` | `mutate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 80 | class | `MatrixRowColSumRepair` | `keep` | `MatrixRowColSumRepair` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 90 | method | `MatrixRowColSumRepair.repair` | `keep` | `repair` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 142 | class | `MatrixSparsityRepair` | `keep` | `MatrixSparsityRepair` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 151 | method | `MatrixSparsityRepair.repair` | `keep` | `repair` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 172 | class | `MatrixBlockSumRepair` | `keep` | `MatrixBlockSumRepair` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 184 | method | `MatrixBlockSumRepair.__post_init__` | `keep` | `__post_init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 187 | method | `MatrixBlockSumRepair.repair` | `keep` | `repair` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `representation/orchestrator.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 18 | function | `_call_operator` | `keep` | `_call_operator` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 26 | class | `OrchestrationPolicy` | `keep` | `OrchestrationPolicy` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 52 | method | `OrchestrationPolicy.__post_init__` | `keep` | `__post_init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 59 | class | `PipelineOrchestrator` | `keep` | `PipelineOrchestrator` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 80 | method | `PipelineOrchestrator.mutate` | `keep` | `mutate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 84 | method | `PipelineOrchestrator.repair` | `keep` | `repair` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 87 | method | `PipelineOrchestrator._run_policy` | `keep` | `_run_policy` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `representation/permutation.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 16 | class | `RandomKeyPermutationDecoder` | `keep` | `RandomKeyPermutationDecoder` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 23 | method | `RandomKeyPermutationDecoder.decode` | `keep` | `decode` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 26 | method | `RandomKeyPermutationDecoder.encode` | `keep` | `encode` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 31 | class | `RandomKeyInitializer` | `keep` | `RandomKeyInitializer` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 40 | method | `RandomKeyInitializer.__post_init__` | `keep` | `__post_init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 43 | method | `RandomKeyInitializer.initialize` | `keep` | `initialize` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 48 | class | `RandomKeyMutation` | `keep` | `RandomKeyMutation` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 58 | method | `RandomKeyMutation.__post_init__` | `keep` | `__post_init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 61 | method | `RandomKeyMutation.mutate` | `keep` | `mutate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 67 | class | `PermutationInitializer` | `keep` | `PermutationInitializer` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 74 | method | `PermutationInitializer.__post_init__` | `keep` | `__post_init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 77 | method | `PermutationInitializer.initialize` | `keep` | `initialize` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 85 | class | `PermutationSwapMutation` | `keep` | `PermutationSwapMutation` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 92 | method | `PermutationSwapMutation.__post_init__` | `keep` | `__post_init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 95 | method | `PermutationSwapMutation.mutate` | `keep` | `mutate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 105 | class | `PermutationInversionMutation` | `keep` | `PermutationInversionMutation` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 112 | method | `PermutationInversionMutation.__post_init__` | `keep` | `__post_init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 115 | method | `PermutationInversionMutation.mutate` | `keep` | `mutate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 125 | class | `PermutationRepair` | `keep` | `PermutationRepair` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 132 | method | `PermutationRepair.__post_init__` | `keep` | `__post_init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 135 | method | `PermutationRepair.repair` | `keep` | `repair` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 145 | class | `PermutationFixRepair` | `keep` | `PermutationFixRepair` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 152 | method | `PermutationFixRepair.repair` | `keep` | `repair` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 169 | class | `TwoOptMutation` | `keep` | `TwoOptMutation` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 177 | method | `TwoOptMutation.__post_init__` | `keep` | `__post_init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 180 | method | `TwoOptMutation.mutate` | `keep` | `mutate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 202 | class | `OrderCrossover` | `keep` | `OrderCrossover` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 209 | method | `OrderCrossover.__post_init__` | `keep` | `__post_init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 212 | method | `OrderCrossover.crossover` | `keep` | `crossover` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 221 | class | `PMXCrossover` | `keep` | `PMXCrossover` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 228 | method | `PMXCrossover.__post_init__` | `keep` | `__post_init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 231 | method | `PMXCrossover.crossover` | `keep` | `crossover` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 239 | function | `_tour_distance` | `keep` | `_tour_distance` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 247 | function | `_order_child` | `keep` | `_order_child` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 259 | function | `_pmx_child` | `keep` | `_pmx_child` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `runs/release/nsgablack_repro_v0.10.0-dev_20260217_024113/tools/schema_tool.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 12 | class | `SchemaIssue` | `keep` | `SchemaIssue` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 18 | function | `_ensure_repo_parent_on_sys_path` | `keep` | `_ensure_repo_parent_on_sys_path` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 24 | function | `_infer_schema_name` | `keep` | `_infer_schema_name` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 37 | function | `_iter_json_files` | `keep` | `_iter_json_files` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 49 | function | `check_files` | `keep` | `check_files` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 73 | function | `main` | `keep` | `main` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `scripts/organize_project.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 16 | function | `create_directories` | `keep` | `create_directories` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 34 | function | `move_demo_files` | `keep` | `move_demo_files` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 54 | function | `move_test_files` | `keep` | `move_test_files` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 73 | function | `move_result_files` | `keep` | `move_result_files` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 93 | function | `clean_examples_dir` | `keep` | `clean_examples_dir` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 106 | function | `remove_temp_files` | `keep` | `remove_temp_files` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 119 | function | `update_gitignore` | `keep` | `update_gitignore` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 144 | function | `create_readme_for_dirs` | `keep` | `create_readme_for_dirs` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 160 | function | `main` | `keep` | `main` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `scripts/scan_snapshot_violations.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 59 | class | `Violation` | `keep` | `Violation` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 68 | function | `_is_context_subscript_write` | `keep` | `_is_context_subscript_write` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 87 | function | `_is_large_key_string` | `keep` | `_is_large_key_string` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 95 | function | `_extract_string_value` | `keep` | `_extract_string_value` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 108 | function | `scan_file` | `keep` | `scan_file` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 138 | function | `scan_directory` | `keep` | `scan_directory` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 157 | function | `format_report` | `keep` | `format_report` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 200 | function | `main` | `keep` | `main` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `tests/conftest.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 14 | function | `sample_problem` | `out-of-scope` | `sample_problem` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 24 | class | `sample_problem.SimpleSphere` | `out-of-scope` | `SimpleSphere` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 25 | method | `SimpleSphere.sample_problem.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 32 | method | `SimpleSphere.sample_problem.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 39 | function | `temp_dir` | `out-of-scope` | `temp_dir` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 52 | function | `sample_solutions` | `out-of-scope` | `sample_solutions` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 65 | function | `sample_bias` | `out-of-scope` | `sample_bias` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 78 | function | `sample_bias.constraint_penalty` | `out-of-scope` | `constraint_penalty` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_adapter_state_recovery_contract.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 23 | function | `_iter_adapter_classes` | `out-of-scope` | `_iter_adapter_classes` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 36 | function | `_class_attrs` | `out-of-scope` | `_class_attrs` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 48 | function | `_literal_str` | `out-of-scope` | `_literal_str` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 54 | function | `_class_methods` | `out-of-scope` | `_class_methods` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 66 | function | `test_stateful_adapters_declare_recovery_level_and_roundtrip_methods` | `out-of-scope` | `test_stateful_adapters_declare_recovery_level_and_roundtrip_methods` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 83 | function | `test_non_l0_stateful_adapters_declare_recovery_notes` | `out-of-scope` | `test_non_l0_stateful_adapters_declare_recovery_notes` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 98 | function | `test_l2_adapters_define_population_methods` | `out-of-scope` | `test_l2_adapters_define_population_methods` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 129 | function | `test_adapters_level_values_are_valid` | `out-of-scope` | `test_adapters_level_values_are_valid` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 148 | function | `_make_adapter` | `out-of-scope` | `_make_adapter` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 169 | function | `test_l2_get_population_returns_triple_before_init` | `out-of-scope` | `test_l2_get_population_returns_triple_before_init` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 183 | function | `test_l2_set_population_returns_true_on_valid_input` | `out-of-scope` | `test_l2_set_population_returns_true_on_valid_input` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 193 | function | `test_l2_population_roundtrip_shape_and_values` | `out-of-scope` | `test_l2_population_roundtrip_shape_and_values` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 212 | function | `test_l2_get_state_set_state_roundtrip` | `out-of-scope` | `test_l2_get_state_set_state_roundtrip` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 231 | function | `test_moead_declares_l2` | `out-of-scope` | `test_moead_declares_l2` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 238 | function | `test_moead_has_get_state_and_set_state` | `out-of-scope` | `test_moead_has_get_state_and_set_state` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 245 | function | `test_moead_get_state_schema` | `out-of-scope` | `test_moead_get_state_schema` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 255 | function | `test_moead_set_state_roundtrip` | `out-of-scope` | `test_moead_set_state_roundtrip` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 268 | function | `test_nsga3_explicitly_declares_l2` | `out-of-scope` | `test_nsga3_explicitly_declares_l2` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 278 | function | `test_nsga3_inherits_population_methods` | `out-of-scope` | `test_nsga3_inherits_population_methods` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_algorithm_biases.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 20 | class | `_DummyProblem` | `out-of-scope` | `_DummyProblem` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 24 | class | `_DummySolver` | `out-of-scope` | `_DummySolver` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 25 | method | `_DummySolver.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 32 | method | `_DummySolver.init_candidate` | `out-of-scope` | `init_candidate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 36 | method | `_DummySolver.mutate_candidate` | `out-of-scope` | `mutate_candidate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 40 | method | `_DummySolver.repair_candidate` | `out-of-scope` | `repair_candidate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 45 | function | `_evaluate` | `out-of-scope` | `_evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 67 | function | `test_process_adapters_follow_propose_update_contract` | `out-of-scope` | `test_process_adapters_follow_propose_update_contract` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 90 | function | `test_population_based_adapters_support_set_population_contract` | `out-of-scope` | `test_population_based_adapters_support_set_population_contract` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 101 | function | `test_nsga3_projection_contains_reference_points` | `out-of-scope` | `test_nsga3_projection_contains_reference_points` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_algorithm_biases_integration.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 12 | function | `test_catalog_uses_adapter_entries_for_process_algorithms` | `out-of-scope` | `test_catalog_uses_adapter_entries_for_process_algorithms` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 41 | function | `test_adapter_layer_contains_no_bias_style_classes_or_compute_api` | `out-of-scope` | `test_adapter_layer_contains_no_bias_style_classes_or_compute_api` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 54 | function | `test_algorithm_adapter_subclasses_have_propose_and_update` | `out-of-scope` | `test_algorithm_adapter_subclasses_have_propose_and_update` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 75 | function | `test_doctor_strict_has_no_adapter_layer_purity_error` | `out-of-scope` | `test_doctor_strict_has_no_adapter_layer_purity_error` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_astar_moa_contracts.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 10 | class | `_TwoObjectiveSphere` | `out-of-scope` | `_TwoObjectiveSphere` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 11 | method | `_TwoObjectiveSphere.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 14 | method | `_TwoObjectiveSphere.get_num_objectives` | `out-of-scope` | `get_num_objectives` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 17 | method | `_TwoObjectiveSphere.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 22 | function | `_grid_neighbors` | `out-of-scope` | `_grid_neighbors` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 28 | function | `_goal_near_zero` | `out-of-scope` | `_goal_near_zero` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 32 | function | `test_astar_adapter_smoke_run` | `out-of-scope` | `test_astar_adapter_smoke_run` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 47 | function | `test_astar_adapter_contract_propose_update_and_checkpoint_roundtrip` | `out-of-scope` | `test_astar_adapter_contract_propose_update_and_checkpoint_roundtrip` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 79 | function | `test_astar_adapter_tolerates_faulty_heuristic` | `out-of-scope` | `test_astar_adapter_tolerates_faulty_heuristic` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 80 | function | `test_astar_adapter_tolerates_faulty_heuristic._bad_heuristic` | `out-of-scope` | `_bad_heuristic` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 96 | function | `test_moa_star_adapter_smoke_and_checkpoint_roundtrip` | `out-of-scope` | `test_moa_star_adapter_smoke_and_checkpoint_roundtrip` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_async_event_driven_adapter.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 4 | function | `_build_pipeline` | `out-of-scope` | `_build_pipeline` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 15 | function | `test_async_event_driven_adapter_runs` | `out-of-scope` | `test_async_event_driven_adapter_runs` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 57 | function | `test_async_event_direct_wiring_wires_plugins` | `out-of-scope` | `test_async_event_direct_wiring_wires_plugins` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_authoritative_examples_smoke.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 7 | function | `test_authoritative_examples_import_and_execute_smoke` | `out-of-scope` | `test_authoritative_examples_import_and_execute_smoke` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_benchmark_harness_plugin.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 5 | function | `test_benchmark_harness_writes_csv_and_summary` | `out-of-scope` | `test_benchmark_harness_writes_csv_and_summary` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_best_context_keys.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 6 | function | `test_composable_solver_exposes_best_context_keys` | `out-of-scope` | `test_composable_solver_exposes_best_context_keys` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 31 | function | `test_nsga2_solver_exposes_best_context_keys` | `out-of-scope` | `test_nsga2_solver_exposes_best_context_keys` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_bias.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 18 | class | `TestBiasModule` | `out-of-scope` | `TestBiasModule` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 21 | method | `TestBiasModule.test_init` | `out-of-scope` | `test_init` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 28 | method | `TestBiasModule.test_add_penalty` | `out-of-scope` | `test_add_penalty` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 34 | method | `TestBiasModule.test_add_callable_penalty_bias` | `out-of-scope` | `test_add_callable_penalty_bias` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 38 | method | `TestBiasModule.test_add_callable_penalty_bias.simple_penalty` | `out-of-scope` | `simple_penalty` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 44 | method | `TestBiasModule.test_add_reward` | `out-of-scope` | `test_add_reward` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 50 | method | `TestBiasModule.test_add_callable_reward_bias` | `out-of-scope` | `test_add_callable_reward_bias` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 54 | method | `TestBiasModule.test_add_callable_reward_bias.simple_reward` | `out-of-scope` | `simple_reward` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 60 | method | `TestBiasModule.test_compute_bias_with_penalty` | `out-of-scope` | `test_compute_bias_with_penalty` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 65 | method | `TestBiasModule.test_compute_bias_with_penalty.bounds_penalty` | `out-of-scope` | `bounds_penalty` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 83 | method | `TestBiasModule.test_compute_bias_with_reward` | `out-of-scope` | `test_compute_bias_with_reward` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 88 | method | `TestBiasModule.test_compute_bias_with_reward.origin_reward` | `out-of-scope` | `origin_reward` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 101 | method | `TestBiasModule.test_compute_bias_combined` | `out-of-scope` | `test_compute_bias_combined` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 105 | method | `TestBiasModule.test_compute_bias_combined.penalty_func` | `out-of-scope` | `penalty_func` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 108 | method | `TestBiasModule.test_compute_bias_combined.reward_func` | `out-of-scope` | `reward_func` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 129 | method | `TestBiasModule.test_history_tracking` | `out-of-scope` | `test_history_tracking` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 146 | method | `TestBiasModule.test_clear` | `out-of-scope` | `test_clear` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 159 | class | `TestRewardFunctions` | `out-of-scope` | `TestRewardFunctions` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 162 | method | `TestRewardFunctions.test_proximity_reward` | `out-of-scope` | `test_proximity_reward` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 177 | method | `TestRewardFunctions.test_improvement_reward` | `out-of-scope` | `test_improvement_reward` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 194 | class | `TestBiasIntegration` | `out-of-scope` | `TestBiasIntegration` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 197 | method | `TestBiasIntegration.test_constraint_bias` | `out-of-scope` | `test_constraint_bias` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 202 | method | `TestBiasIntegration.test_constraint_bias.constraint_penalty` | `out-of-scope` | `constraint_penalty` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 233 | method | `TestBiasIntegration.test_complex_bias_scenario` | `out-of-scope` | `test_complex_bias_scenario` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 257 | function | `test_sphere_objective` | `out-of-scope` | `test_sphere_objective` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_bias_runtime_contract_guard.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 11 | class | `_MetricsBias` | `out-of-scope` | `_MetricsBias` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 14 | method | `_MetricsBias.compute` | `out-of-scope` | `compute` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 18 | function | `_ctx` | `out-of-scope` | `_ctx` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 29 | function | `test_missing_required_metrics_warns_once_per_generation` | `out-of-scope` | `test_missing_required_metrics_warns_once_per_generation` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 41 | function | `test_missing_required_metrics_error_policy_raises` | `out-of-scope` | `test_missing_required_metrics_error_policy_raises` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 49 | function | `test_required_metrics_present_runs_without_warning` | `out-of-scope` | `test_required_metrics_present_runs_without_warning` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_bias_vector.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 7 | function | `test_compute_bias_vector_matches_scalar_calls` | `out-of-scope` | `test_compute_bias_vector_matches_scalar_calls` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 10 | function | `test_compute_bias_vector_matches_scalar_calls.penalty` | `out-of-scope` | `penalty` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 14 | function | `test_compute_bias_vector_matches_scalar_calls.reward` | `out-of-scope` | `reward` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 31 | function | `test_compute_bias_batch_shapes` | `out-of-scope` | `test_compute_bias_batch_shapes` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_catalog.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 4 | function | `test_catalog_search_basic` | `out-of-scope` | `test_catalog_search_basic` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 14 | function | `test_catalog_entry_load_smoke` | `out-of-scope` | `test_catalog_entry_load_smoke` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 23 | function | `test_catalog_companions_integrity` | `out-of-scope` | `test_catalog_companions_integrity` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_catalog_context_contracts.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 6 | function | `test_plugin_context_contracts_are_enriched_in_catalog` | `out-of-scope` | `test_plugin_context_contracts_are_enriched_in_catalog` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 14 | function | `test_catalog_integrity_checker_strict_plugin_context_passes` | `out-of-scope` | `test_catalog_integrity_checker_strict_plugin_context_passes` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 26 | function | `test_catalog_integrity_checker_context_conflict_waiver_passes` | `out-of-scope` | `test_catalog_integrity_checker_context_conflict_waiver_passes` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_catalog_docs.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 4 | function | `test_catalog_has_doc_entries` | `out-of-scope` | `test_catalog_has_doc_entries` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 13 | function | `test_cli_catalog_list_doc_kind` | `out-of-scope` | `test_cli_catalog_list_doc_kind` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 23 | function | `test_cli_catalog_list_multi_kind` | `out-of-scope` | `test_cli_catalog_list_multi_kind` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_catalog_external_entries.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 7 | function | `test_catalog_can_load_external_entries_from_env` | `out-of-scope` | `test_catalog_can_load_external_entries_from_env` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 33 | function | `test_catalog_can_load_external_entries_from_env_directory` | `out-of-scope` | `test_catalog_can_load_external_entries_from_env_directory` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 59 | function | `test_catalog_index_detail_split_loads_details_on_demand` | `out-of-scope` | `test_catalog_index_detail_split_loads_details_on_demand` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_catalog_quick_add.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 6 | function | `test_build_entry_payload_fills_explicit_usage_fields` | `out-of-scope` | `test_build_entry_payload_fills_explicit_usage_fields` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 22 | function | `test_upsert_catalog_entry_replaces_same_key` | `out-of-scope` | `test_upsert_catalog_entry_replaces_same_key` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 56 | function | `test_upsert_writes_context_contract_fields` | `out-of-scope` | `test_upsert_writes_context_contract_fields` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_catalog_source_sync.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 11 | function | `test_source_sync_scan_read_and_apply` | `out-of-scope` | `test_source_sync_scan_read_and_apply` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 60 | function | `test_expand_marked_bias_template_in_scaffold_project` | `out-of-scope` | `test_expand_marked_bias_template_in_scaffold_project` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 90 | function | `test_expand_template_rejects_outside_project_or_framework` | `out-of-scope` | `test_expand_template_rejects_outside_project_or_framework` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_catalog_usage.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 5 | function | `test_build_usage_profile_infers_plugin_wiring` | `out-of-scope` | `test_build_usage_profile_infers_plugin_wiring` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 18 | function | `test_build_usage_profile_infers_adapter_control_plane_wiring` | `out-of-scope` | `test_build_usage_profile_infers_adapter_control_plane_wiring` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 31 | function | `test_catalog_search_usage_field_matches_use_when` | `out-of-scope` | `test_catalog_search_usage_field_matches_use_when` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 45 | function | `test_global_catalog_entries_have_usage_contracts` | `out-of-scope` | `test_global_catalog_entries_have_usage_contracts` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_catalog_view_scope.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 4 | function | `test_scope_from_key_project_prefix` | `out-of-scope` | `test_scope_from_key_project_prefix` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 8 | function | `test_scope_from_key_framework_default` | `out-of-scope` | `test_scope_from_key_framework_default` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 12 | function | `test_context_role_match_requires` | `out-of-scope` | `test_context_role_match_requires` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 22 | function | `test_context_role_match_providers_include_mutates` | `out-of-scope` | `test_context_role_match_providers_include_mutates` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_checkpoint_resume_plugin.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 9 | function | `_build_composable_solver` | `out-of-scope` | `_build_composable_solver` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 28 | function | `test_checkpoint_resume_composable_solver` | `out-of-scope` | `test_checkpoint_resume_composable_solver` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 71 | function | `test_checkpoint_retention_keeps_last_n` | `out-of-scope` | `test_checkpoint_retention_keeps_last_n` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 93 | function | `test_checkpoint_resume_nsga2_solver` | `out-of-scope` | `test_checkpoint_resume_nsga2_solver` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 140 | function | `test_checkpoint_resume_hmac_roundtrip` | `out-of-scope` | `test_checkpoint_resume_hmac_roundtrip` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 180 | function | `test_checkpoint_resume_blocks_unsigned_when_hmac_key_present` | `out-of-scope` | `test_checkpoint_resume_blocks_unsigned_when_hmac_key_present` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 225 | function | `test_checkpoint_resume_allows_unsigned_when_explicitly_unsafe` | `out-of-scope` | `test_checkpoint_resume_allows_unsigned_when_explicitly_unsafe` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 265 | function | `test_checkpoint_strict_requires_hmac_and_forbids_unsafe` | `out-of-scope` | `test_checkpoint_strict_requires_hmac_and_forbids_unsafe` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 311 | function | `test_attach_checkpoint_resume_trust_checkpoint_maps_to_unsafe` | `out-of-scope` | `test_attach_checkpoint_resume_trust_checkpoint_maps_to_unsafe` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 325 | function | `test_attach_checkpoint_resume_strict_conflicts_with_trust_checkpoint` | `out-of-scope` | `test_attach_checkpoint_resume_strict_conflicts_with_trust_checkpoint` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_cli_catalog.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 4 | function | `test_cli_catalog_search_smoke` | `out-of-scope` | `test_cli_catalog_search_smoke` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 13 | function | `test_cli_catalog_add_upsert` | `out-of-scope` | `test_cli_catalog_add_upsert` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_companion_orchestrator_plugin.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 18 | class | `_LineMOProblem` | `out-of-scope` | `_LineMOProblem` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 19 | method | `_LineMOProblem.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 27 | method | `_LineMOProblem.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 33 | class | `_FixedAdapter` | `out-of-scope` | `_FixedAdapter` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 34 | method | `_FixedAdapter.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 39 | method | `_FixedAdapter.propose` | `out-of-scope` | `propose` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 43 | method | `_FixedAdapter.update` | `out-of-scope` | `update` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 48 | function | `_make_solver` | `out-of-scope` | `_make_solver` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 58 | function | `_contains_ndarray` | `out-of-scope` | `_contains_ndarray` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 68 | function | `test_scheduler_mixed_periodic_event_cooldown_and_cap` | `out-of-scope` | `test_scheduler_mixed_periodic_event_cooldown_and_cap` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 129 | function | `test_companion_blocking_phase_does_not_advance_generation` | `out-of-scope` | `test_companion_blocking_phase_does_not_advance_generation` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 155 | function | `test_multi_phase_lineage_has_versioned_entries` | `out-of-scope` | `test_multi_phase_lineage_has_versioned_entries` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 184 | function | `test_phase_end_injection_consistency` | `out-of-scope` | `test_phase_end_injection_consistency` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 218 | function | `test_storage_writes_small_context_and_large_snapshot_refs` | `out-of-scope` | `test_storage_writes_small_context_and_large_snapshot_refs` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_config_loader.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 13 | function | `test_load_config_from_dict` | `out-of-scope` | `test_load_config_from_dict` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 18 | function | `test_load_config_from_file` | `out-of-scope` | `test_load_config_from_file` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 25 | function | `test_merge_dicts_deep` | `out-of-scope` | `test_merge_dicts_deep` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 33 | function | `test_apply_config_strict_unknown` | `out-of-scope` | `test_apply_config_strict_unknown` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 34 | class | `test_apply_config_strict_unknown.Dummy` | `out-of-scope` | `Dummy` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 35 | method | `Dummy.test_apply_config_strict_unknown.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 50 | function | `test_build_dataclass_config` | `out-of-scope` | `test_build_dataclass_config` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_constraints.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 7 | class | `BrokenConstraintProblem` | `out-of-scope` | `BrokenConstraintProblem` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 8 | method | `BrokenConstraintProblem.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 12 | method | `BrokenConstraintProblem.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 15 | method | `BrokenConstraintProblem.evaluate_constraints` | `out-of-scope` | `evaluate_constraints` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 19 | function | `test_constraint_failures_are_handled` | `out-of-scope` | `test_constraint_failures_are_handled` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_context_conflict_detection.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 7 | function | `test_detect_context_conflicts_reports_multi_writer_key` | `out-of-scope` | `test_detect_context_conflicts_reports_multi_writer_key` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 17 | function | `test_detect_context_conflicts_ignores_single_writer_key` | `out-of-scope` | `test_detect_context_conflicts_ignores_single_writer_key` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_context_key_alignment.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 18 | function | `_iter_py_files` | `out-of-scope` | `_iter_py_files` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 25 | function | `test_no_raw_context_literal_key_access` | `out-of-scope` | `test_no_raw_context_literal_key_access` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 45 | function | `test_contract_key_literals_are_canonical` | `out-of-scope` | `test_contract_key_literals_are_canonical` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_context_schema.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 6 | function | `test_build_and_validate_minimal_context` | `out-of-scope` | `test_build_and_validate_minimal_context` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 28 | function | `test_validate_minimal_context_missing_required_key_raises` | `out-of-scope` | `test_validate_minimal_context_missing_required_key_raises` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_context_store_backends.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 17 | class | `_Sphere` | `out-of-scope` | `_Sphere` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 18 | method | `_Sphere.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 21 | method | `_Sphere.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 26 | function | `test_inmemory_context_store_ttl_expires` | `out-of-scope` | `test_inmemory_context_store_ttl_expires` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 34 | function | `test_blank_solver_context_store_roundtrip` | `out-of-scope` | `test_blank_solver_context_store_roundtrip` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 42 | function | `test_create_context_store_rejects_unknown_backend` | `out-of-scope` | `test_create_context_store_rejects_unknown_backend` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 51 | function | `test_solver_uses_configured_context_store_backend_memory` | `out-of-scope` | `test_solver_uses_configured_context_store_backend_memory` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 60 | function | `test_redis_context_store_ttl_10s_smoke` | `out-of-scope` | `test_redis_context_store_ttl_10s_smoke` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_copt_backend_template.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 6 | function | `test_copt_backend_mock_when_module_unavailable` | `out-of-scope` | `test_copt_backend_mock_when_module_unavailable` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 20 | function | `test_copt_backend_custom_solve_fn_path` | `out-of-scope` | `test_copt_backend_custom_solve_fn_path` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 26 | class | `test_copt_backend_custom_solve_fn_path._CP` | `out-of-scope` | `_CP` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 31 | function | `test_copt_backend_custom_solve_fn_path._solve_fn` | `out-of-scope` | `_solve_fn` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 52 | function | `test_copt_backend_template_linear_inline_spec` | `out-of-scope` | `test_copt_backend_template_linear_inline_spec` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 56 | class | `test_copt_backend_template_linear_inline_spec._FakeVar` | `out-of-scope` | `_FakeVar` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 57 | method | `_FakeVar.test_copt_backend_template_linear_inline_spec.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 60 | method | `_FakeVar.test_copt_backend_template_linear_inline_spec.__rmul__` | `out-of-scope` | `__rmul__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 63 | method | `_FakeVar.test_copt_backend_template_linear_inline_spec.__mul__` | `out-of-scope` | `__mul__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 66 | class | `test_copt_backend_template_linear_inline_spec._FakeModel` | `out-of-scope` | `_FakeModel` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 67 | method | `_FakeModel.test_copt_backend_template_linear_inline_spec.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 71 | method | `_FakeModel.test_copt_backend_template_linear_inline_spec.setParam` | `out-of-scope` | `setParam` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 75 | method | `_FakeModel.test_copt_backend_template_linear_inline_spec.addVar` | `out-of-scope` | `addVar` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 82 | method | `_FakeModel.test_copt_backend_template_linear_inline_spec.setObjective` | `out-of-scope` | `setObjective` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 86 | method | `_FakeModel.test_copt_backend_template_linear_inline_spec.addConstr` | `out-of-scope` | `addConstr` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 89 | method | `_FakeModel.test_copt_backend_template_linear_inline_spec.solve` | `out-of-scope` | `solve` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 92 | class | `test_copt_backend_template_linear_inline_spec._FakeEnv` | `out-of-scope` | `_FakeEnv` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 93 | method | `_FakeEnv.test_copt_backend_template_linear_inline_spec.createModel` | `out-of-scope` | `createModel` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 97 | class | `test_copt_backend_template_linear_inline_spec._FakeCOPT` | `out-of-scope` | `_FakeCOPT` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 106 | class | `test_copt_backend_template_linear_inline_spec._FakeCP` | `out-of-scope` | `_FakeCP` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 110 | method | `_FakeCP.test_copt_backend_template_linear_inline_spec.Envr` | `out-of-scope` | `Envr` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 114 | method | `_FakeCP.test_copt_backend_template_linear_inline_spec.quicksum` | `out-of-scope` | `quicksum` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 139 | function | `test_copt_backend_template_unknown_template_strict` | `out-of-scope` | `test_copt_backend_template_unknown_template_strict` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 143 | class | `test_copt_backend_template_unknown_template_strict._CP` | `out-of-scope` | `_CP` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 162 | function | `test_copt_backend_template_qp_inline_spec` | `out-of-scope` | `test_copt_backend_template_qp_inline_spec` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 166 | class | `test_copt_backend_template_qp_inline_spec._FakeVar` | `out-of-scope` | `_FakeVar` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 167 | method | `_FakeVar.test_copt_backend_template_qp_inline_spec.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 170 | method | `_FakeVar.test_copt_backend_template_qp_inline_spec.__rmul__` | `out-of-scope` | `__rmul__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 173 | method | `_FakeVar.test_copt_backend_template_qp_inline_spec.__mul__` | `out-of-scope` | `__mul__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 176 | class | `test_copt_backend_template_qp_inline_spec._FakeModel` | `out-of-scope` | `_FakeModel` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 177 | method | `_FakeModel.test_copt_backend_template_qp_inline_spec.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 181 | method | `_FakeModel.test_copt_backend_template_qp_inline_spec.setParam` | `out-of-scope` | `setParam` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 185 | method | `_FakeModel.test_copt_backend_template_qp_inline_spec.addVar` | `out-of-scope` | `addVar` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 192 | method | `_FakeModel.test_copt_backend_template_qp_inline_spec.setObjective` | `out-of-scope` | `setObjective` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 196 | method | `_FakeModel.test_copt_backend_template_qp_inline_spec.addConstr` | `out-of-scope` | `addConstr` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 199 | method | `_FakeModel.test_copt_backend_template_qp_inline_spec.solve` | `out-of-scope` | `solve` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 202 | class | `test_copt_backend_template_qp_inline_spec._FakeEnv` | `out-of-scope` | `_FakeEnv` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 203 | method | `_FakeEnv.test_copt_backend_template_qp_inline_spec.createModel` | `out-of-scope` | `createModel` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 207 | class | `test_copt_backend_template_qp_inline_spec._FakeCOPT` | `out-of-scope` | `_FakeCOPT` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 216 | class | `test_copt_backend_template_qp_inline_spec._FakeCP` | `out-of-scope` | `_FakeCP` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 220 | method | `_FakeCP.test_copt_backend_template_qp_inline_spec.Envr` | `out-of-scope` | `Envr` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 224 | method | `_FakeCP.test_copt_backend_template_qp_inline_spec.quicksum` | `out-of-scope` | `quicksum` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_critical_regressions_round2.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 15 | class | `_ToyMOProblem` | `out-of-scope` | `_ToyMOProblem` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 16 | method | `_ToyMOProblem.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 19 | method | `_ToyMOProblem.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 24 | function | `test_environmental_selection_uses_full_front_ranking` | `out-of-scope` | `test_environmental_selection_uses_full_front_ranking` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 59 | function | `test_crowding_distance_marks_true_boundaries` | `out-of-scope` | `test_crowding_distance_marks_true_boundaries` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 77 | function | `test_adaptive_manager_diversity_and_improvement_are_non_degenerate` | `out-of-scope` | `test_adaptive_manager_diversity_and_improvement_are_non_degenerate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 91 | function | `test_memory_optimizer_report_does_not_raise_on_cache_recommendation` | `out-of-scope` | `test_memory_optimizer_report_does_not_raise_on_cache_recommendation` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 92 | class | `test_memory_optimizer_report_does_not_raise_on_cache_recommendation._DummySolver` | `out-of-scope` | `_DummySolver` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 103 | function | `test_meta_learning_selector_handles_dict_scores_and_aligned_training_data` | `out-of-scope` | `test_meta_learning_selector_handles_dict_scores_and_aligned_training_data` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 106 | function | `test_meta_learning_selector_handles_dict_scores_and_aligned_training_data._features` | `out-of-scope` | `_features` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 145 | function | `test_bias_module_clear_resets_context_cache` | `out-of-scope` | `test_bias_module_clear_resets_context_cache` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_decision_trace_plugin.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 9 | class | `_PM` | `out-of-scope` | `_PM` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 10 | method | `_PM.trigger` | `out-of-scope` | `trigger` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 14 | class | `_Adapter` | `out-of-scope` | `_Adapter` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 15 | method | `_Adapter.propose` | `out-of-scope` | `propose` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 18 | method | `_Adapter.update` | `out-of-scope` | `update` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 22 | class | `_Solver` | `out-of-scope` | `_Solver` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 23 | method | `_Solver.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 30 | method | `_Solver.evaluate_individual` | `out-of-scope` | `evaluate_individual` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 33 | method | `_Solver.evaluate_population` | `out-of-scope` | `evaluate_population` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 37 | function | `test_decision_trace_plugin_records_and_replays` | `out-of-scope` | `test_decision_trace_plugin_records_and_replays` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_default_observability_suite.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 10 | class | `_ToyProblem` | `out-of-scope` | `_ToyProblem` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 11 | method | `_ToyProblem.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 14 | method | `_ToyProblem.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 19 | function | `test_attach_default_observability_plugins_idempotent` | `out-of-scope` | `test_attach_default_observability_plugins_idempotent` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 44 | function | `test_attach_observability_profile_quickstart_profile` | `out-of-scope` | `test_attach_observability_profile_quickstart_profile` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 61 | function | `test_resolve_observability_preset_rejects_unknown_profile` | `out-of-scope` | `test_resolve_observability_preset_rejects_unknown_profile` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_doctor_broad_except.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 6 | function | `test_doctor_flags_broad_except_swallow_in_core_as_error` | `out-of-scope` | `test_doctor_flags_broad_except_swallow_in_core_as_error` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 25 | function | `test_doctor_flags_broad_except_swallow_in_non_core_as_warn` | `out-of-scope` | `test_doctor_flags_broad_except_swallow_in_non_core_as_warn` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_doctor_cli_output.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 11 | function | `test_project_doctor_json_output_is_machine_readable` | `out-of-scope` | `test_project_doctor_json_output_is_machine_readable` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 22 | function | `test_problem_lines_extract_line_number_patterns` | `out-of-scope` | `test_problem_lines_extract_line_number_patterns` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 56 | function | `test_project_doctor_parser_accepts_watch_and_format_flags` | `out-of-scope` | `test_project_doctor_parser_accepts_watch_and_format_flags` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_doctor_component_order_constraints.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 6 | function | `_build_solver_header` | `out-of-scope` | `_build_solver_header` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 24 | function | `test_doctor_component_order_unknown_reference_strict_error` | `out-of-scope` | `test_doctor_component_order_unknown_reference_strict_error` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 38 | function | `test_doctor_component_order_cycle_strict_error` | `out-of-scope` | `test_doctor_component_order_cycle_strict_error` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 54 | function | `test_doctor_component_order_priority_conflict_strict_error` | `out-of-scope` | `test_doctor_component_order_priority_conflict_strict_error` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 69 | function | `test_doctor_component_order_non_strict_warn` | `out-of-scope` | `test_doctor_component_order_non_strict_warn` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 83 | function | `test_doctor_component_order_plugin_class_cycle_strict_error` | `out-of-scope` | `test_doctor_component_order_plugin_class_cycle_strict_error` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 108 | function | `test_doctor_component_order_plugin_class_priority_conflict_strict_error` | `out-of-scope` | `test_doctor_component_order_plugin_class_priority_conflict_strict_error` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_doctor_l3_l4_runtime_governance.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 6 | function | `test_doctor_flags_plugin_eval_short_circuit_in_strict` | `out-of-scope` | `test_doctor_flags_plugin_eval_short_circuit_in_strict` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_doctor_runtime_private_surface.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 4 | function | `_runtime_private_call_source` | `out-of-scope` | `_runtime_private_call_source` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 11 | function | `test_runtime_private_surface_scans_working_files` | `out-of-scope` | `test_runtime_private_surface_scans_working_files` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 22 | function | `test_runtime_private_surface_scans_build_solver_file` | `out-of-scope` | `test_runtime_private_surface_scans_build_solver_file` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 40 | function | `test_runtime_private_surface_scans_utils_when_present` | `out-of-scope` | `test_runtime_private_surface_scans_utils_when_present` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 52 | function | `test_runtime_private_surface_skips_tests_by_default` | `out-of-scope` | `test_runtime_private_surface_skips_tests_by_default` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_doctor_snapshot_policy.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 6 | function | `_write_build_solver` | `out-of-scope` | `_write_build_solver` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 21 | function | `test_doctor_warns_when_snapshot_redis_uses_pickle_unsafe` | `out-of-scope` | `test_doctor_warns_when_snapshot_redis_uses_pickle_unsafe` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 29 | function | `test_doctor_strict_escalates_snapshot_redis_pickle_unsafe` | `out-of-scope` | `test_doctor_strict_escalates_snapshot_redis_pickle_unsafe` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_doctor_view_guards.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 9 | function | `test_count_doctor_guard_issues_counts_both_guard_codes` | `out-of-scope` | `test_count_doctor_guard_issues_counts_both_guard_codes` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 23 | function | `test_count_doctor_guard_issues_handles_missing_diagnostics` | `out-of-scope` | `test_count_doctor_guard_issues_handles_missing_diagnostics` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 30 | function | `test_build_doctor_visual_hints_maps_new_rule_codes` | `out-of-scope` | `test_build_doctor_visual_hints_maps_new_rule_codes` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 49 | function | `test_build_doctor_visual_hints_aggregates_and_escalates_warn_in_strict` | `out-of-scope` | `test_build_doctor_visual_hints_aggregates_and_escalates_warn_in_strict` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_e2e_scaffold_flow.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 11 | function | `test_e2e_scaffold_register_search_build_run_doctor` | `out-of-scope` | `test_e2e_scaffold_register_search_build_run_doctor` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 87 | function | `test_project_catalog_can_load_split_kind_toml` | `out-of-scope` | `test_project_catalog_can_load_split_kind_toml` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_elite_retention_context_writeback.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 8 | class | `_Adapter` | `out-of-scope` | `_Adapter` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 9 | method | `_Adapter.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 15 | method | `_Adapter.get_population` | `out-of-scope` | `get_population` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 18 | method | `_Adapter.set_population` | `out-of-scope` | `set_population` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 26 | class | `_Solver` | `out-of-scope` | `_Solver` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 27 | method | `_Solver.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 38 | method | `_Solver.evaluate_individual` | `out-of-scope` | `evaluate_individual` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 45 | function | `test_basic_elite_plugin_writes_back_via_adapter_set_population` | `out-of-scope` | `test_basic_elite_plugin_writes_back_via_adapter_set_population` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_evaluation_shape_validation.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 22 | function | `test_individual_valid_shape_1d` | `out-of-scope` | `test_individual_valid_shape_1d` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 34 | function | `test_individual_valid_shape_2d_single_row` | `out-of-scope` | `test_individual_valid_shape_2d_single_row` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 45 | function | `test_individual_scalar_objective` | `out-of-scope` | `test_individual_scalar_objective` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 56 | function | `test_individual_shape_mismatch_strict` | `out-of-scope` | `test_individual_shape_mismatch_strict` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 65 | function | `test_individual_shape_mismatch_soft` | `out-of-scope` | `test_individual_shape_mismatch_soft` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 94 | function | `test_individual_invalid_dtype` | `out-of-scope` | `test_individual_invalid_dtype` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 111 | function | `test_individual_invalid_violation_type` | `out-of-scope` | `test_individual_invalid_violation_type` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 131 | function | `test_population_valid_shape` | `out-of-scope` | `test_population_valid_shape` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 150 | function | `test_population_single_objective_1d` | `out-of-scope` | `test_population_single_objective_1d` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 164 | function | `test_population_size_mismatch_strict` | `out-of-scope` | `test_population_size_mismatch_strict` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 178 | function | `test_population_size_mismatch_soft_pad` | `out-of-scope` | `test_population_size_mismatch_soft_pad` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 204 | function | `test_population_size_mismatch_soft_truncate` | `out-of-scope` | `test_population_size_mismatch_soft_truncate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 227 | function | `test_population_objectives_mismatch` | `out-of-scope` | `test_population_objectives_mismatch` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 264 | function | `test_population_violations_shape_mismatch` | `out-of-scope` | `test_population_violations_shape_mismatch` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 289 | function | `test_plugin_short_circuit_none` | `out-of-scope` | `test_plugin_short_circuit_none` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 297 | function | `test_plugin_short_circuit_individual_mode` | `out-of-scope` | `test_plugin_short_circuit_individual_mode` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 312 | function | `test_plugin_short_circuit_population_mode` | `out-of-scope` | `test_plugin_short_circuit_population_mode` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 327 | function | `test_plugin_short_circuit_invalid_return_type` | `out-of-scope` | `test_plugin_short_circuit_invalid_return_type` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 337 | function | `test_plugin_short_circuit_invalid_tuple_length` | `out-of-scope` | `test_plugin_short_circuit_invalid_tuple_length` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 350 | function | `test_plugin_short_circuit_missing_population_size` | `out-of-scope` | `test_plugin_short_circuit_missing_population_size` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 369 | function | `test_snapshot_roundtrip_consistency` | `out-of-scope` | `test_snapshot_roundtrip_consistency` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_extension_contracts.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 5 | function | `test_composable_solver_rejects_wrong_candidate_shape` | `out-of-scope` | `test_composable_solver_rejects_wrong_candidate_shape` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 11 | class | `test_composable_solver_rejects_wrong_candidate_shape.P` | `out-of-scope` | `P` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 12 | method | `P.test_composable_solver_rejects_wrong_candidate_shape.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 15 | method | `P.test_composable_solver_rejects_wrong_candidate_shape.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 19 | class | `test_composable_solver_rejects_wrong_candidate_shape.BadAdapter` | `out-of-scope` | `BadAdapter` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 20 | method | `BadAdapter.test_composable_solver_rejects_wrong_candidate_shape.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 23 | method | `BadAdapter.test_composable_solver_rejects_wrong_candidate_shape.propose` | `out-of-scope` | `propose` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 32 | function | `test_plugin_return_value_warns_by_default` | `out-of-scope` | `test_plugin_return_value_warns_by_default` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 35 | class | `test_plugin_return_value_warns_by_default.BadPlugin` | `out-of-scope` | `BadPlugin` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 36 | method | `BadPlugin.test_plugin_return_value_warns_by_default.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 39 | method | `BadPlugin.test_plugin_return_value_warns_by_default.on_generation_start` | `out-of-scope` | `on_generation_start` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_extension_point_contract_enforcement.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 32 | function | `_make` | `out-of-scope` | `_make` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 59 | function | `_get_all_adapter_classes` | `out-of-scope` | `_get_all_adapter_classes` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 71 | function | `test_adapter_declares_core_contract_fields` | `out-of-scope` | `test_adapter_declares_core_contract_fields` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 83 | function | `test_adapter_core_contract_fields_are_iterable` | `out-of-scope` | `test_adapter_core_contract_fields_are_iterable` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 102 | function | `test_plugin_base_declares_core_contract_fields` | `out-of-scope` | `test_plugin_base_declares_core_contract_fields` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 112 | function | `_iter_plugin_classes_from_files` | `out-of-scope` | `_iter_plugin_classes_from_files` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 132 | function | `test_plugin_inherits_core_contract_fields` | `out-of-scope` | `test_plugin_inherits_core_contract_fields` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 151 | class | `TestVerifyComponentContract` | `out-of-scope` | `TestVerifyComponentContract` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 153 | method | `TestVerifyComponentContract.test_fully_declared_returns_empty` | `out-of-scope` | `test_fully_declared_returns_empty` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 160 | method | `TestVerifyComponentContract.test_missing_field_detected` | `out-of-scope` | `test_missing_field_detected` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 163 | class | `TestVerifyComponentContract.test_missing_field_detected.BadAdapter` | `out-of-scope` | `BadAdapter` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 174 | method | `TestVerifyComponentContract.test_strict_raises_on_missing` | `out-of-scope` | `test_strict_raises_on_missing` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 177 | class | `TestVerifyComponentContract.test_strict_raises_on_missing.PartialAdapter` | `out-of-scope` | `PartialAdapter` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 185 | method | `TestVerifyComponentContract.test_fully_declared_strict_does_not_raise` | `out-of-scope` | `test_fully_declared_strict_does_not_raise` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 191 | method | `TestVerifyComponentContract.test_none_value_treated_as_missing` | `out-of-scope` | `test_none_value_treated_as_missing` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 195 | class | `TestVerifyComponentContract.test_none_value_treated_as_missing.NoneFieldAdapter` | `out-of-scope` | `NoneFieldAdapter` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 204 | method | `TestVerifyComponentContract.test_empty_tuple_is_valid` | `out-of-scope` | `test_empty_tuple_is_valid` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 208 | class | `TestVerifyComponentContract.test_empty_tuple_is_valid.EmptyAdapter` | `out-of-scope` | `EmptyAdapter` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 222 | class | `TestVerifySolverContracts` | `out-of-scope` | `TestVerifySolverContracts` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 224 | method | `TestVerifySolverContracts._make_minimal_solver` | `out-of-scope` | `_make_minimal_solver` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 231 | class | `TestVerifySolverContracts._make_minimal_solver.MinProblem` | `out-of-scope` | `MinProblem` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 232 | method | `TestVerifySolverContracts.MinProblem._make_minimal_solver.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 236 | method | `TestVerifySolverContracts.MinProblem._make_minimal_solver.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 241 | method | `TestVerifySolverContracts.test_clean_solver_returns_empty` | `out-of-scope` | `test_clean_solver_returns_empty` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 249 | method | `TestVerifySolverContracts.test_bad_adapter_detected` | `out-of-scope` | `test_bad_adapter_detected` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 256 | class | `TestVerifySolverContracts.test_bad_adapter_detected.P` | `out-of-scope` | `P` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 257 | method | `TestVerifySolverContracts.P.test_bad_adapter_detected.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 261 | method | `TestVerifySolverContracts.P.test_bad_adapter_detected.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 264 | class | `TestVerifySolverContracts.test_bad_adapter_detected.IncompleteAdapter` | `out-of-scope` | `IncompleteAdapter` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 267 | method | `TestVerifySolverContracts.IncompleteAdapter.test_bad_adapter_detected.propose` | `out-of-scope` | `propose` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 280 | function | `test_doctor_core_contract_keys_contains_all_four_fields` | `out-of-scope` | `test_doctor_core_contract_keys_contains_all_four_fields` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 312 | function | `test_get_component_contract_does_not_raise` | `out-of-scope` | `test_get_component_contract_does_not_raise` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 330 | function | `test_get_component_contract_returns_contract_instance` | `out-of-scope` | `test_get_component_contract_returns_contract_instance` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_gpu_eval_template_plugin.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 8 | class | `_DummyProblem` | `out-of-scope` | `_DummyProblem` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 9 | method | `_DummyProblem.evaluate_gpu_batch` | `out-of-scope` | `evaluate_gpu_batch` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 15 | class | `_DummySolver` | `out-of-scope` | `_DummySolver` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 16 | method | `_DummySolver.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 21 | method | `_DummySolver.get_context` | `out-of-scope` | `get_context` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 24 | method | `_DummySolver.set_context` | `out-of-scope` | `set_context` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 28 | function | `test_gpu_eval_template_returns_none_when_backend_unavailable` | `out-of-scope` | `test_gpu_eval_template_returns_none_when_backend_unavailable` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 38 | function | `test_gpu_eval_template_short_circuit_path` | `out-of-scope` | `test_gpu_eval_template_short_circuit_path` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_high_priority_fixes.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 15 | class | `_DummyMCProblem` | `out-of-scope` | `_DummyMCProblem` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 16 | method | `_DummyMCProblem.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 19 | method | `_DummyMCProblem.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 24 | method | `_DummyMCProblem.evaluate_constraints` | `out-of-scope` | `evaluate_constraints` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 29 | class | `_DummyMCSolver` | `out-of-scope` | `_DummyMCSolver` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 30 | method | `_DummyMCSolver.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 37 | method | `_DummyMCSolver.build_context` | `out-of-scope` | `build_context` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 41 | method | `_DummyMCSolver._apply_bias` | `out-of-scope` | `_apply_bias` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 46 | function | `_rng_states_equal` | `out-of-scope` | `_rng_states_equal` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 56 | function | `test_monte_carlo_plugin_does_not_pollute_global_numpy_rng` | `out-of-scope` | `test_monte_carlo_plugin_does_not_pollute_global_numpy_rng` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 73 | function | `test_differential_evolution_adapter_tracks_best_score_in_projection` | `out-of-scope` | `test_differential_evolution_adapter_tracks_best_score_in_projection` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 74 | class | `test_differential_evolution_adapter_tracks_best_score_in_projection._Solver` | `out-of-scope` | `_Solver` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 75 | method | `_Solver.test_differential_evolution_adapter_tracks_best_score_in_projection.repair_candidate` | `out-of-scope` | `repair_candidate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 100 | class | `_Cfg` | `out-of-scope` | `_Cfg` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 101 | method | `_Cfg.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 105 | class | `_PluginWithRunId` | `out-of-scope` | `_PluginWithRunId` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 106 | method | `_PluginWithRunId.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 110 | class | `_PM` | `out-of-scope` | `_PM` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 111 | method | `_PM.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 114 | method | `_PM.list_plugins` | `out-of-scope` | `list_plugins` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 119 | class | `_Solver` | `out-of-scope` | `_Solver` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 120 | method | `_Solver.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 124 | function | `test_mysql_run_logger_resolves_run_id_from_plugin_configs` | `out-of-scope` | `test_mysql_run_logger_resolves_run_id_from_plugin_configs` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 131 | function | `test_mysql_run_logger_connection_error_is_not_masked` | `out-of-scope` | `test_mysql_run_logger_connection_error_is_not_masked` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 142 | function | `test_mysql_run_logger_connection_error_is_not_masked.fake_import` | `out-of-scope` | `fake_import` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 154 | function | `test_mysql_run_logger_raises_driver_error_only_when_drivers_missing` | `out-of-scope` | `test_mysql_run_logger_raises_driver_error_only_when_drivers_missing` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 160 | function | `test_mysql_run_logger_raises_driver_error_only_when_drivers_missing.fake_import` | `out-of-scope` | `fake_import` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 170 | function | `test_mysql_run_logger_to_jsonable_handles_ndarray` | `out-of-scope` | `test_mysql_run_logger_to_jsonable_handles_ndarray` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 183 | function | `test_mysql_run_logger_print_latest_summary` | `out-of-scope` | `test_mysql_run_logger_print_latest_summary` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 184 | class | `test_mysql_run_logger_print_latest_summary._Cursor` | `out-of-scope` | `_Cursor` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 185 | method | `_Cursor.test_mysql_run_logger_print_latest_summary.execute` | `out-of-scope` | `execute` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 188 | method | `_Cursor.test_mysql_run_logger_print_latest_summary.fetchone` | `out-of-scope` | `fetchone` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 191 | method | `_Cursor.test_mysql_run_logger_print_latest_summary.close` | `out-of-scope` | `close` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 194 | class | `test_mysql_run_logger_print_latest_summary._Conn` | `out-of-scope` | `_Conn` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 195 | method | `_Conn.test_mysql_run_logger_print_latest_summary.cursor` | `out-of-scope` | `cursor` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_inner_solver_backend_contract.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 6 | function | `test_inner_solver_backend_retry_and_timeout_strategy` | `out-of-scope` | `test_inner_solver_backend_retry_and_timeout_strategy` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 13 | class | `test_inner_solver_backend_retry_and_timeout_strategy._RetryBackend` | `out-of-scope` | `_RetryBackend` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 14 | method | `_RetryBackend.test_inner_solver_backend_retry_and_timeout_strategy.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 17 | method | `_RetryBackend.test_inner_solver_backend_retry_and_timeout_strategy.solve` | `out-of-scope` | `solve` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 24 | class | `test_inner_solver_backend_retry_and_timeout_strategy._Problem` | `out-of-scope` | `_Problem` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 25 | method | `_Problem.test_inner_solver_backend_retry_and_timeout_strategy.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 28 | method | `_Problem.test_inner_solver_backend_retry_and_timeout_strategy.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 32 | method | `_Problem.test_inner_solver_backend_retry_and_timeout_strategy.build_inner_problem` | `out-of-scope` | `build_inner_problem` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 36 | class | `test_inner_solver_backend_retry_and_timeout_strategy._Adapter` | `out-of-scope` | `_Adapter` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 37 | method | `_Adapter.test_inner_solver_backend_retry_and_timeout_strategy.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 40 | method | `_Adapter.test_inner_solver_backend_retry_and_timeout_strategy.propose` | `out-of-scope` | `propose` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_l0_l3_l4_runtime_refactor.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 14 | class | `_Problem` | `out-of-scope` | `_Problem` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 15 | method | `_Problem.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 23 | method | `_Problem.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 27 | method | `_Problem.evaluate_constraints` | `out-of-scope` | `evaluate_constraints` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 32 | class | `_StopCtl` | `out-of-scope` | `_StopCtl` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 36 | method | `_StopCtl.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 39 | method | `_StopCtl.propose` | `out-of-scope` | `propose` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 51 | class | `_ExactProvider` | `out-of-scope` | `_ExactProvider` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 55 | method | `_ExactProvider.can_handle_individual` | `out-of-scope` | `can_handle_individual` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 61 | method | `_ExactProvider.evaluate_individual` | `out-of-scope` | `evaluate_individual` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 67 | method | `_ExactProvider.can_handle_population` | `out-of-scope` | `can_handle_population` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 73 | method | `_ExactProvider.evaluate_population` | `out-of-scope` | `evaluate_population` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 80 | class | `_ApproxProvider` | `out-of-scope` | `_ApproxProvider` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 84 | method | `_ApproxProvider.evaluate_individual` | `out-of-scope` | `evaluate_individual` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 92 | class | `_InnerSolver` | `out-of-scope` | `_InnerSolver` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 95 | method | `_InnerSolver.run` | `out-of-scope` | `run` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 105 | function | `test_acceleration_registry_default_backend` | `out-of-scope` | `test_acceleration_registry_default_backend` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 111 | function | `test_runtime_controller_domain_owner_conflict` | `out-of-scope` | `test_runtime_controller_domain_owner_conflict` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 118 | function | `test_evaluation_mediator_disallow_approximate` | `out-of-scope` | `test_evaluation_mediator_disallow_approximate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 129 | function | `test_solver_uses_l4_provider_instead_of_plugin_short_circuit` | `out-of-scope` | `test_solver_uses_l4_provider_instead_of_plugin_short_circuit` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 137 | function | `test_problem_inner_runtime_evaluator_contract_and_budget` | `out-of-scope` | `test_problem_inner_runtime_evaluator_contract_and_budget` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_logging_config.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 7 | function | `test_json_formatter_fields` | `out-of-scope` | `test_json_formatter_fields` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 24 | function | `test_configure_logging_json` | `out-of-scope` | `test_configure_logging_json` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_make_v010_repro_package.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 8 | function | `test_build_repro_package_smoke` | `out-of-scope` | `test_build_repro_package_smoke` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_medium_priority_fixes.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 14 | class | `_DummySolver` | `out-of-scope` | `_DummySolver` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 15 | method | `_DummySolver.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 22 | function | `test_convergence_stagnation_count_increments_by_one` | `out-of-scope` | `test_convergence_stagnation_count_increments_by_one` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 40 | function | `test_mas_model_plugin_caps_training_buffer` | `out-of-scope` | `test_mas_model_plugin_caps_training_buffer` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 56 | function | `test_pareto_archive_truncates_with_crowding` | `out-of-scope` | `test_pareto_archive_truncates_with_crowding` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 69 | class | `_ToyProblem` | `out-of-scope` | `_ToyProblem` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 70 | method | `_ToyProblem.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 73 | method | `_ToyProblem.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 78 | function | `test_solver_sbx_can_generate_non_linear_offspring_when_eta_small` | `out-of-scope` | `test_solver_sbx_can_generate_non_linear_offspring_when_eta_small` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 92 | function | `test_update_pareto_solutions_keeps_front_boundaries_with_crowding` | `out-of-scope` | `test_update_pareto_solutions_keeps_front_boundaries_with_crowding` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 105 | function | `test_moead_equal_decomposition_value_does_not_replace` | `out-of-scope` | `test_moead_equal_decomposition_value_does_not_replace` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 114 | function | `test_vns_sigma_is_capped` | `out-of-scope` | `test_vns_sigma_is_capped` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_medium_priority_regressions2.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 14 | class | `_AlgoBias` | `out-of-scope` | `_AlgoBias` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 15 | method | `_AlgoBias.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 18 | method | `_AlgoBias.compute` | `out-of-scope` | `compute` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 23 | class | `_DomainBias` | `out-of-scope` | `_DomainBias` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 24 | method | `_DomainBias.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 28 | method | `_DomainBias.compute` | `out-of-scope` | `compute` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 33 | class | `_Ctx` | `out-of-scope` | `_Ctx` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 34 | method | `_Ctx.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 38 | method | `_Ctx.set_constraint_violation` | `out-of-scope` | `set_constraint_violation` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 42 | function | `test_moead_update_uses_per_candidate_modes_and_projection_is_batch` | `out-of-scope` | `test_moead_update_uses_per_candidate_modes_and_projection_is_batch` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 70 | function | `test_adaptive_manager_caps_exploration_weights` | `out-of-scope` | `test_adaptive_manager_caps_exploration_weights` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 86 | function | `test_adaptive_manager_diversity_large_population_uses_sampling_path` | `out-of-scope` | `test_adaptive_manager_diversity_large_population_uses_sampling_path` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 95 | function | `test_memory_optimizer_keeps_history_in_chronological_order` | `out-of-scope` | `test_memory_optimizer_keeps_history_in_chronological_order` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 96 | class | `test_memory_optimizer_keeps_history_in_chronological_order._Solver` | `out-of-scope` | `_Solver` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 97 | method | `_Solver.test_memory_optimizer_keeps_history_in_chronological_order.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 107 | function | `test_domain_bias_violation_rate_uses_real_evaluation_count` | `out-of-scope` | `test_domain_bias_violation_rate_uses_real_evaluation_count` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 117 | function | `test_universal_bias_history_is_bounded` | `out-of-scope` | `test_universal_bias_history_is_bounded` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 128 | function | `test_parallel_evaluator_non_balanced_path_does_not_enter_executor_context` | `out-of-scope` | `test_parallel_evaluator_non_balanced_path_does_not_enter_executor_context` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 129 | class | `test_parallel_evaluator_non_balanced_path_does_not_enter_executor_context._DummyExecutor` | `out-of-scope` | `_DummyExecutor` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 130 | method | `_DummyExecutor.test_parallel_evaluator_non_balanced_path_does_not_enter_executor_context.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 133 | method | `_DummyExecutor.test_parallel_evaluator_non_balanced_path_does_not_enter_executor_context.__enter__` | `out-of-scope` | `__enter__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 137 | method | `_DummyExecutor.test_parallel_evaluator_non_balanced_path_does_not_enter_executor_context.__exit__` | `out-of-scope` | `__exit__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 141 | method | `_DummyExecutor.test_parallel_evaluator_non_balanced_path_does_not_enter_executor_context.map` | `out-of-scope` | `map` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_module_report_plugin.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 5 | function | `test_module_report_writes_reports_and_injects_artifacts` | `out-of-scope` | `test_module_report_writes_reports_and_injects_artifacts` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_moead_adapter.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 5 | function | `test_moead_adapter_runs_and_updates_archive` | `out-of-scope` | `test_moead_adapter_runs_and_updates_archive` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 13 | class | `test_moead_adapter_runs_and_updates_archive.BiSphere` | `out-of-scope` | `BiSphere` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 14 | method | `BiSphere.test_moead_adapter_runs_and_updates_archive.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 23 | method | `BiSphere.test_moead_adapter_runs_and_updates_archive.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 57 | function | `test_moead_adapter_rejects_legacy_nsga_loop_solver` | `out-of-scope` | `test_moead_adapter_rejects_legacy_nsga_loop_solver` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 60 | class | `test_moead_adapter_rejects_legacy_nsga_loop_solver._LegacyLikeSolver` | `out-of-scope` | `_LegacyLikeSolver` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 63 | method | `_LegacyLikeSolver.test_moead_adapter_rejects_legacy_nsga_loop_solver.selection` | `out-of-scope` | `selection` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 66 | method | `_LegacyLikeSolver.test_moead_adapter_rejects_legacy_nsga_loop_solver.environmental_selection` | `out-of-scope` | `environmental_selection` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_moead_suite.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 4 | function | `test_moead_adapter_direct_wiring_installs_archive` | `out-of-scope` | `test_moead_adapter_direct_wiring_installs_archive` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 12 | class | `test_moead_adapter_direct_wiring_installs_archive.BiSphere` | `out-of-scope` | `BiSphere` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 13 | method | `BiSphere.test_moead_adapter_direct_wiring_installs_archive.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 22 | method | `BiSphere.test_moead_adapter_direct_wiring_installs_archive.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_my_project_vns_no_suite_wiring.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 8 | function | `_run_build_solver_check` | `out-of-scope` | `_run_build_solver_check` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 22 | function | `test_my_project_default_strategy_is_nsga2` | `out-of-scope` | `test_my_project_default_strategy_is_nsga2` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 27 | function | `test_my_project_vns_strategy_wires_without_suite_entrypoint` | `out-of-scope` | `test_my_project_vns_strategy_wires_without_suite_entrypoint` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_nested_inner_plugins.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 4 | function | `test_inner_solver_and_bridge_plugins_write_layer_context` | `out-of-scope` | `test_inner_solver_and_bridge_plugins_write_layer_context` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 11 | class | `test_inner_solver_and_bridge_plugins_write_layer_context.OuterProblem` | `out-of-scope` | `OuterProblem` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 12 | method | `OuterProblem.test_inner_solver_and_bridge_plugins_write_layer_context.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 15 | method | `OuterProblem.test_inner_solver_and_bridge_plugins_write_layer_context.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 19 | method | `OuterProblem.test_inner_solver_and_bridge_plugins_write_layer_context.build_inner_task` | `out-of-scope` | `build_inner_task` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 24 | class | `test_inner_solver_and_bridge_plugins_write_layer_context.FixedAdapter` | `out-of-scope` | `FixedAdapter` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 25 | method | `FixedAdapter.test_inner_solver_and_bridge_plugins_write_layer_context.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 28 | method | `FixedAdapter.test_inner_solver_and_bridge_plugins_write_layer_context.propose` | `out-of-scope` | `propose` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 54 | function | `test_inner_timeout_budget_blocks_calls` | `out-of-scope` | `test_inner_timeout_budget_blocks_calls` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 64 | class | `test_inner_timeout_budget_blocks_calls.OuterProblem` | `out-of-scope` | `OuterProblem` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 65 | method | `OuterProblem.test_inner_timeout_budget_blocks_calls.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 68 | method | `OuterProblem.test_inner_timeout_budget_blocks_calls.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 71 | method | `OuterProblem.test_inner_timeout_budget_blocks_calls.build_inner_task` | `out-of-scope` | `build_inner_task` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 75 | class | `test_inner_timeout_budget_blocks_calls.FixedAdapter` | `out-of-scope` | `FixedAdapter` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 76 | method | `FixedAdapter.test_inner_timeout_budget_blocks_calls.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 79 | method | `FixedAdapter.test_inner_timeout_budget_blocks_calls.propose` | `out-of-scope` | `propose` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_ngspice_backend_template.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 6 | function | `test_ngspice_backend_mock_mode_runs_without_binary` | `out-of-scope` | `test_ngspice_backend_mock_mode_runs_without_binary` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 24 | function | `test_ngspice_backend_error_output_decode_fallback` | `out-of-scope` | `test_ngspice_backend_error_output_decode_fallback` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 29 | class | `test_ngspice_backend_error_output_decode_fallback._Proc` | `out-of-scope` | `_Proc` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_optional_numba_import_guard.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 10 | function | `test_import_performance_module_when_numba_import_crashes` | `out-of-scope` | `test_import_performance_module_when_numba_import_crashes` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_optional_numba_probe.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 8 | function | `test_has_numba_handles_non_importerror_failures` | `out-of-scope` | `test_has_numba_handles_non_importerror_failures` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 11 | function | `test_has_numba_handles_non_importerror_failures.broken_import` | `out-of-scope` | `broken_import` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_otel_tracing_plugin.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 8 | function | `test_otel_tracing_plugin_wraps_and_restores_methods` | `out-of-scope` | `test_otel_tracing_plugin_wraps_and_restores_methods` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 11 | class | `test_otel_tracing_plugin_wraps_and_restores_methods._Adapter` | `out-of-scope` | `_Adapter` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 12 | method | `_Adapter.test_otel_tracing_plugin_wraps_and_restores_methods.propose` | `out-of-scope` | `propose` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 16 | method | `_Adapter.test_otel_tracing_plugin_wraps_and_restores_methods.update` | `out-of-scope` | `update` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 20 | class | `test_otel_tracing_plugin_wraps_and_restores_methods._PM` | `out-of-scope` | `_PM` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 21 | method | `_PM.test_otel_tracing_plugin_wraps_and_restores_methods.trigger` | `out-of-scope` | `trigger` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 25 | class | `test_otel_tracing_plugin_wraps_and_restores_methods._Solver` | `out-of-scope` | `_Solver` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 26 | method | `_Solver.test_otel_tracing_plugin_wraps_and_restores_methods.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 30 | method | `_Solver.test_otel_tracing_plugin_wraps_and_restores_methods.evaluate_individual` | `out-of-scope` | `evaluate_individual` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 34 | method | `_Solver.test_otel_tracing_plugin_wraps_and_restores_methods.evaluate_population` | `out-of-scope` | `evaluate_population` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 42 | function | `test_otel_tracing_plugin_wraps_and_restores_methods._fake_setup` | `out-of-scope` | `_fake_setup` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_parallel_engineering_safeguards.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 9 | function | `test_parallel_process_precheck_falls_back_to_thread_when_unpicklable` | `out-of-scope` | `test_parallel_process_precheck_falls_back_to_thread_when_unpicklable` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 10 | class | `test_parallel_process_precheck_falls_back_to_thread_when_unpicklable.LocalSphere` | `out-of-scope` | `LocalSphere` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 11 | method | `LocalSphere.test_parallel_process_precheck_falls_back_to_thread_when_unpicklable.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 15 | method | `LocalSphere.test_parallel_process_precheck_falls_back_to_thread_when_unpicklable.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 47 | function | `test_parallel_process_precheck_strict_raises_when_unpicklable` | `out-of-scope` | `test_parallel_process_precheck_strict_raises_when_unpicklable` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 48 | class | `test_parallel_process_precheck_strict_raises_when_unpicklable.LocalSphere` | `out-of-scope` | `LocalSphere` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 49 | method | `LocalSphere.test_parallel_process_precheck_strict_raises_when_unpicklable.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 53 | method | `LocalSphere.test_parallel_process_precheck_strict_raises_when_unpicklable.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 78 | function | `test_thread_backend_deepcopy_bias_isolation_keeps_original_state` | `out-of-scope` | `test_thread_backend_deepcopy_bias_isolation_keeps_original_state` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 79 | class | `test_thread_backend_deepcopy_bias_isolation_keeps_original_state.LocalSphere` | `out-of-scope` | `LocalSphere` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 80 | method | `LocalSphere.test_thread_backend_deepcopy_bias_isolation_keeps_original_state.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 83 | method | `LocalSphere.test_thread_backend_deepcopy_bias_isolation_keeps_original_state.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 86 | class | `test_thread_backend_deepcopy_bias_isolation_keeps_original_state.CountingBias` | `out-of-scope` | `CountingBias` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 87 | method | `CountingBias.test_thread_backend_deepcopy_bias_isolation_keeps_original_state.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 91 | method | `CountingBias.test_thread_backend_deepcopy_bias_isolation_keeps_original_state.compute_bias` | `out-of-scope` | `compute_bias` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 111 | function | `test_thread_backend_disable_cache_temporarily_and_restore` | `out-of-scope` | `test_thread_backend_disable_cache_temporarily_and_restore` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 112 | class | `test_thread_backend_disable_cache_temporarily_and_restore.LocalSphere` | `out-of-scope` | `LocalSphere` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 113 | method | `LocalSphere.test_thread_backend_disable_cache_temporarily_and_restore.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 116 | method | `LocalSphere.test_thread_backend_disable_cache_temporarily_and_restore.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 119 | class | `test_thread_backend_disable_cache_temporarily_and_restore.CountingBias` | `out-of-scope` | `CountingBias` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 120 | method | `CountingBias.test_thread_backend_disable_cache_temporarily_and_restore.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 124 | method | `CountingBias.test_thread_backend_disable_cache_temporarily_and_restore.compute_bias` | `out-of-scope` | `compute_bias` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_parallel_integration.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 7 | class | `TinySphere` | `out-of-scope` | `TinySphere` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 8 | method | `TinySphere.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 12 | method | `TinySphere.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 16 | function | `test_parallel_evaluation_matches_serial` | `out-of-scope` | `test_parallel_evaluation_matches_serial` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_parallel_wrapper_blank_composable.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 10 | class | `TinySphere` | `out-of-scope` | `TinySphere` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 11 | method | `TinySphere.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 15 | method | `TinySphere.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 20 | function | `test_parallel_wrapper_blank_matches_serial` | `out-of-scope` | `test_parallel_wrapper_blank_matches_serial` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 44 | class | `FixedCandidatesAdapter` | `out-of-scope` | `FixedCandidatesAdapter` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 45 | method | `FixedCandidatesAdapter.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 49 | method | `FixedCandidatesAdapter.propose` | `out-of-scope` | `propose` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 53 | function | `test_parallel_wrapper_composable_evaluates` | `out-of-scope` | `test_parallel_wrapper_composable_evaluates` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_pipeline_orchestrator.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 6 | function | `test_pipeline_orchestrator_serial_mutate_chain` | `out-of-scope` | `test_pipeline_orchestrator_serial_mutate_chain` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 9 | class | `test_pipeline_orchestrator_serial_mutate_chain.AddOne` | `out-of-scope` | `AddOne` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 10 | method | `AddOne.test_pipeline_orchestrator_serial_mutate_chain.mutate` | `out-of-scope` | `mutate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 14 | class | `test_pipeline_orchestrator_serial_mutate_chain.TimesTwo` | `out-of-scope` | `TimesTwo` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 15 | method | `TimesTwo.test_pipeline_orchestrator_serial_mutate_chain.mutate` | `out-of-scope` | `mutate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 26 | function | `test_pipeline_orchestrator_switch_by_context_index` | `out-of-scope` | `test_pipeline_orchestrator_switch_by_context_index` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 29 | class | `test_pipeline_orchestrator_switch_by_context_index.AddOne` | `out-of-scope` | `AddOne` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 30 | method | `AddOne.test_pipeline_orchestrator_switch_by_context_index.mutate` | `out-of-scope` | `mutate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 34 | class | `test_pipeline_orchestrator_switch_by_context_index.AddThree` | `out-of-scope` | `AddThree` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 35 | method | `AddThree.test_pipeline_orchestrator_switch_by_context_index.mutate` | `out-of-scope` | `mutate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 52 | function | `test_pipeline_orchestrator_router_by_context_key` | `out-of-scope` | `test_pipeline_orchestrator_router_by_context_key` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 55 | class | `test_pipeline_orchestrator_router_by_context_key.Explore` | `out-of-scope` | `Explore` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 56 | method | `Explore.test_pipeline_orchestrator_router_by_context_key.mutate` | `out-of-scope` | `mutate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 60 | class | `test_pipeline_orchestrator_router_by_context_key.Exploit` | `out-of-scope` | `Exploit` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 61 | method | `Exploit.test_pipeline_orchestrator_router_by_context_key.mutate` | `out-of-scope` | `mutate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 81 | function | `test_pipeline_orchestrator_dynamic_repair_by_generation` | `out-of-scope` | `test_pipeline_orchestrator_dynamic_repair_by_generation` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 84 | class | `test_pipeline_orchestrator_dynamic_repair_by_generation.ClipLow` | `out-of-scope` | `ClipLow` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 85 | method | `ClipLow.test_pipeline_orchestrator_dynamic_repair_by_generation.repair` | `out-of-scope` | `repair` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 90 | class | `test_pipeline_orchestrator_dynamic_repair_by_generation.ClipHigh` | `out-of-scope` | `ClipHigh` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 91 | method | `ClipHigh.test_pipeline_orchestrator_dynamic_repair_by_generation.repair` | `out-of-scope` | `repair` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_plugin_attach_failure_strategy.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 15 | class | `SimpleProblem` | `out-of-scope` | `SimpleProblem` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 16 | method | `SimpleProblem.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 19 | method | `SimpleProblem.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 22 | method | `SimpleProblem.get_num_objectives` | `out-of-scope` | `get_num_objectives` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 26 | class | `FaultyAttachPlugin` | `out-of-scope` | `FaultyAttachPlugin` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 29 | method | `FaultyAttachPlugin.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 34 | method | `FaultyAttachPlugin.attach` | `out-of-scope` | `attach` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 37 | method | `FaultyAttachPlugin.on_solver_init` | `out-of-scope` | `on_solver_init` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 41 | class | `WorkingPlugin` | `out-of-scope` | `WorkingPlugin` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 44 | method | `WorkingPlugin.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 49 | method | `WorkingPlugin.attach` | `out-of-scope` | `attach` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 53 | method | `WorkingPlugin.on_solver_init` | `out-of-scope` | `on_solver_init` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 56 | method | `WorkingPlugin.on_generation_start` | `out-of-scope` | `on_generation_start` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 60 | function | `test_plugin_attach_failure_soft_mode` | `out-of-scope` | `test_plugin_attach_failure_soft_mode` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 82 | function | `test_plugin_attach_failure_strict_mode` | `out-of-scope` | `test_plugin_attach_failure_strict_mode` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 96 | function | `test_plugin_lifecycle_skip_failed_attach` | `out-of-scope` | `test_plugin_lifecycle_skip_failed_attach` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 121 | function | `test_multiple_plugins_mixed_failures` | `out-of-scope` | `test_multiple_plugins_mixed_failures` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 158 | function | `test_plugin_attach_state_inspection` | `out-of-scope` | `test_plugin_attach_state_inspection` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 184 | function | `test_plugin_attach_error_message_preserved` | `out-of-scope` | `test_plugin_attach_error_message_preserved` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 199 | function | `test_plugin_method_chaining_preserved` | `out-of-scope` | `test_plugin_method_chaining_preserved` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 219 | function | `test_plugin_strict_mode_prevents_registration` | `out-of-scope` | `test_plugin_strict_mode_prevents_registration` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 243 | function | `test_plugin_soft_mode_allows_inspection` | `out-of-scope` | `test_plugin_soft_mode_allows_inspection` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_plugin_context_snapshot.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 13 | class | `_DummyPlugin` | `out-of-scope` | `_DummyPlugin` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 14 | method | `_DummyPlugin.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 18 | function | `test_get_population_snapshot_prefers_adapter_get_population` | `out-of-scope` | `test_get_population_snapshot_prefers_adapter_get_population` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 19 | class | `test_get_population_snapshot_prefers_adapter_get_population._Adapter` | `out-of-scope` | `_Adapter` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 20 | method | `_Adapter.test_get_population_snapshot_prefers_adapter_get_population.get_population` | `out-of-scope` | `get_population` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 26 | class | `test_get_population_snapshot_prefers_adapter_get_population._Solver` | `out-of-scope` | `_Solver` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 40 | function | `test_get_population_snapshot_prefers_solver_snapshot` | `out-of-scope` | `test_get_population_snapshot_prefers_solver_snapshot` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 41 | class | `test_get_population_snapshot_prefers_solver_snapshot._Solver` | `out-of-scope` | `_Solver` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 42 | method | `_Solver.test_get_population_snapshot_prefers_solver_snapshot.read_snapshot` | `out-of-scope` | `read_snapshot` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 57 | function | `test_get_population_snapshot_falls_back_to_solver_state` | `out-of-scope` | `test_get_population_snapshot_falls_back_to_solver_state` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 58 | class | `test_get_population_snapshot_falls_back_to_solver_state._Solver` | `out-of-scope` | `_Solver` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 71 | function | `test_commit_population_snapshot_uses_adapter_setter` | `out-of-scope` | `test_commit_population_snapshot_uses_adapter_setter` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 72 | class | `test_commit_population_snapshot_uses_adapter_setter._Adapter` | `out-of-scope` | `_Adapter` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 73 | method | `_Adapter.test_commit_population_snapshot_uses_adapter_setter.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 77 | method | `_Adapter.test_commit_population_snapshot_uses_adapter_setter.set_population` | `out-of-scope` | `set_population` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 86 | class | `test_commit_population_snapshot_uses_adapter_setter._Solver` | `out-of-scope` | `_Solver` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 87 | method | `_Solver.test_commit_population_snapshot_uses_adapter_setter.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_plugin_order_scheduler.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 11 | class | `_Problem` | `out-of-scope` | `_Problem` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 12 | method | `_Problem.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 15 | method | `_Problem.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 20 | class | `_OrderPlugin` | `out-of-scope` | `_OrderPlugin` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 21 | method | `_OrderPlugin.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 25 | class | `_RequestOrderPlugin` | `out-of-scope` | `_RequestOrderPlugin` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 26 | method | `_RequestOrderPlugin.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 29 | method | `_RequestOrderPlugin.on_generation_end` | `out-of-scope` | `on_generation_end` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 34 | function | `_names` | `out-of-scope` | `_names` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 38 | function | `test_plugin_order_default_priority_and_stability` | `out-of-scope` | `test_plugin_order_default_priority_and_stability` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 47 | function | `test_plugin_order_priority_conflict_is_rejected` | `out-of-scope` | `test_plugin_order_priority_conflict_is_rejected` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 58 | function | `test_plugin_order_unknown_reference_is_rejected_immediately` | `out-of-scope` | `test_plugin_order_unknown_reference_is_rejected_immediately` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 66 | function | `test_add_plugin_rejects_unknown_order_reference` | `out-of-scope` | `test_add_plugin_rejects_unknown_order_reference` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 73 | function | `test_plugin_order_cycle_detection_and_rollback` | `out-of-scope` | `test_plugin_order_cycle_detection_and_rollback` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 88 | function | `test_run_precheck_blocks_invalid_order` | `out-of-scope` | `test_run_precheck_blocks_invalid_order` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 98 | function | `test_set_plugin_order_rejected_while_running` | `out-of-scope` | `test_set_plugin_order_rejected_while_running` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 109 | function | `test_request_plugin_order_applies_at_next_generation_boundary` | `out-of-scope` | `test_request_plugin_order_applies_at_next_generation_boundary` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_production_scheduling_case_smoke.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 8 | function | `test_production_scheduling_case_runs_quickly` | `out-of-scope` | `test_production_scheduling_case_runs_quickly` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_project_scaffold_registration_guide.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 4 | function | `test_init_project_creates_component_registration_guide` | `out-of-scope` | `test_init_project_creates_component_registration_guide` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 36 | function | `test_init_project_creates_contract_and_test_matrix_templates` | `out-of-scope` | `test_init_project_creates_contract_and_test_matrix_templates` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 42 | function | `test_project_doctor_warns_when_registration_guide_missing` | `out-of-scope` | `test_project_doctor_warns_when_registration_guide_missing` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 52 | function | `test_project_doctor_warns_when_component_contract_template_missing` | `out-of-scope` | `test_project_doctor_warns_when_component_contract_template_missing` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 62 | function | `test_project_doctor_warns_when_component_test_matrix_template_missing` | `out-of-scope` | `test_project_doctor_warns_when_component_test_matrix_template_missing` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 72 | function | `test_project_doctor_skips_scaffold_checks_for_non_scaffold_folder` | `out-of-scope` | `test_project_doctor_skips_scaffold_checks_for_non_scaffold_folder` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 81 | function | `test_project_doctor_parses_utf8_sig_python_source` | `out-of-scope` | `test_project_doctor_parses_utf8_sig_python_source` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 92 | function | `test_project_doctor_strict_escalates_missing_contract_to_error` | `out-of-scope` | `test_project_doctor_strict_escalates_missing_contract_to_error` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 104 | function | `test_project_doctor_warns_when_core_contract_keys_missing` | `out-of-scope` | `test_project_doctor_warns_when_core_contract_keys_missing` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 121 | function | `test_project_doctor_strict_blocks_template_not_implemented` | `out-of-scope` | `test_project_doctor_strict_blocks_template_not_implemented` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 142 | function | `test_project_doctor_strict_blocks_solver_mirror_writes` | `out-of-scope` | `test_project_doctor_strict_blocks_solver_mirror_writes` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 163 | function | `test_project_doctor_non_strict_warns_solver_mirror_writes` | `out-of-scope` | `test_project_doctor_non_strict_warns_solver_mirror_writes` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 184 | function | `test_project_doctor_strict_blocks_runtime_bypass_writes` | `out-of-scope` | `test_project_doctor_strict_blocks_runtime_bypass_writes` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 205 | function | `test_project_doctor_strict_allows_runtime_api_calls` | `out-of-scope` | `test_project_doctor_strict_allows_runtime_api_calls` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 225 | function | `test_project_doctor_strict_blocks_runtime_private_calls` | `out-of-scope` | `test_project_doctor_strict_blocks_runtime_private_calls` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 246 | function | `test_project_doctor_strict_blocks_missing_state_recovery_level` | `out-of-scope` | `test_project_doctor_strict_blocks_missing_state_recovery_level` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 269 | function | `test_project_doctor_accepts_valid_state_recovery_level` | `out-of-scope` | `test_project_doctor_accepts_valid_state_recovery_level` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 292 | function | `test_project_doctor_strict_blocks_plugin_direct_solver_state_access` | `out-of-scope` | `test_project_doctor_strict_blocks_plugin_direct_solver_state_access` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 314 | function | `test_project_doctor_strict_blocks_examples_direct_solver_control_writes` | `out-of-scope` | `test_project_doctor_strict_blocks_examples_direct_solver_control_writes` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 330 | function | `test_project_doctor_accepts_examples_using_solver_control_plane_methods` | `out-of-scope` | `test_project_doctor_accepts_examples_using_solver_control_plane_methods` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 346 | function | `test_project_doctor_strict_blocks_missing_metrics_provider` | `out-of-scope` | `test_project_doctor_strict_blocks_missing_metrics_provider` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 384 | function | `test_project_doctor_allows_requires_metrics_with_explicit_fallback` | `out-of-scope` | `test_project_doctor_allows_requires_metrics_with_explicit_fallback` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 421 | function | `test_project_doctor_does_not_treat_notes_as_metrics_fallback` | `out-of-scope` | `test_project_doctor_does_not_treat_notes_as_metrics_fallback` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 459 | function | `test_project_doctor_strict_blocks_invalid_metrics_fallback_literal` | `out-of-scope` | `test_project_doctor_strict_blocks_invalid_metrics_fallback_literal` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 479 | function | `test_project_doctor_strict_blocks_nonliteral_metrics_fallback` | `out-of-scope` | `test_project_doctor_strict_blocks_nonliteral_metrics_fallback` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 499 | function | `test_project_doctor_strict_blocks_invalid_metrics_fallback_in_build_solver` | `out-of-scope` | `test_project_doctor_strict_blocks_invalid_metrics_fallback_in_build_solver` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 538 | function | `test_project_doctor_strict_blocks_process_like_algorithm_as_bias` | `out-of-scope` | `test_project_doctor_strict_blocks_process_like_algorithm_as_bias` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 584 | function | `test_project_doctor_does_not_flag_normal_bias_as_process_like` | `out-of-scope` | `test_project_doctor_does_not_flag_normal_bias_as_process_like` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 627 | function | `test_project_doctor_strict_blocks_redis_key_prefix_without_project_token` | `out-of-scope` | `test_project_doctor_strict_blocks_redis_key_prefix_without_project_token` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 650 | function | `test_project_doctor_warns_when_redis_ttl_policy_is_implicit` | `out-of-scope` | `test_project_doctor_warns_when_redis_ttl_policy_is_implicit` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 673 | function | `test_project_doctor_strict_blocks_framework_component_missing_catalog_entry` | `out-of-scope` | `test_project_doctor_strict_blocks_framework_component_missing_catalog_entry` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 701 | function | `test_project_doctor_reports_unregistered_project_components_as_info` | `out-of-scope` | `test_project_doctor_reports_unregistered_project_components_as_info` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 729 | function | `test_project_doctor_warns_unknown_contract_keys` | `out-of-scope` | `test_project_doctor_warns_unknown_contract_keys` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 749 | function | `test_project_doctor_warns_contract_impl_mismatch` | `out-of-scope` | `test_project_doctor_warns_contract_impl_mismatch` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 774 | function | `test_project_doctor_warns_large_object_context_write` | `out-of-scope` | `test_project_doctor_warns_large_object_context_write` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 795 | function | `test_project_doctor_warns_snapshot_ref_unreadable` | `out-of-scope` | `test_project_doctor_warns_snapshot_ref_unreadable` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 830 | function | `test_project_doctor_warns_snapshot_payload_shape_mismatch` | `out-of-scope` | `test_project_doctor_warns_snapshot_payload_shape_mismatch` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_ray_backend_optional.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 7 | function | `test_parallel_evaluator_ray_backend_smoke` | `out-of-scope` | `test_parallel_evaluator_ray_backend_smoke` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 15 | class | `test_parallel_evaluator_ray_backend_smoke.SphereProblem` | `out-of-scope` | `SphereProblem` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 19 | method | `SphereProblem.test_parallel_evaluator_ray_backend_smoke.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 23 | method | `SphereProblem.test_parallel_evaluator_ray_backend_smoke.get_num_objectives` | `out-of-scope` | `get_num_objectives` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 26 | function | `test_parallel_evaluator_ray_backend_smoke.problem_factory` | `out-of-scope` | `problem_factory` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_refactoring.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 11 | class | `SimpleTestProblem` | `out-of-scope` | `SimpleTestProblem` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 12 | method | `SimpleTestProblem.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 15 | method | `SimpleTestProblem.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 19 | class | `MockBiasModule` | `out-of-scope` | `MockBiasModule` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 20 | method | `MockBiasModule.compute_bias` | `out-of-scope` | `compute_bias` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 23 | method | `MockBiasModule.add_bias` | `out-of-scope` | `add_bias` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 26 | method | `MockBiasModule.is_enabled` | `out-of-scope` | `is_enabled` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 29 | method | `MockBiasModule.enable` | `out-of-scope` | `enable` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 32 | method | `MockBiasModule.disable` | `out-of-scope` | `disable` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 36 | function | `test_core_import_and_basic_solver_creation` | `out-of-scope` | `test_core_import_and_basic_solver_creation` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 46 | function | `test_dependency_injection_and_backward_compatibility` | `out-of-scope` | `test_dependency_injection_and_backward_compatibility` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 58 | function | `test_interface_and_lazy_loading_checks` | `out-of-scope` | `test_interface_and_lazy_loading_checks` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 68 | function | `test_solver_runs_small_problem` | `out-of-scope` | `test_solver_runs_small_problem` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_representation.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 23 | class | `TestContinuousRepresentation` | `out-of-scope` | `TestContinuousRepresentation` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 26 | method | `TestContinuousRepresentation.test_init` | `out-of-scope` | `test_init` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 36 | method | `TestContinuousRepresentation.test_encode` | `out-of-scope` | `test_encode` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 49 | method | `TestContinuousRepresentation.test_decode` | `out-of-scope` | `test_decode` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 62 | method | `TestContinuousRepresentation.test_clip_to_bounds` | `out-of-scope` | `test_clip_to_bounds` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 78 | class | `TestIntegerRepresentation` | `out-of-scope` | `TestIntegerRepresentation` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 81 | method | `TestIntegerRepresentation.test_init` | `out-of-scope` | `test_init` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 90 | method | `TestIntegerRepresentation.test_encode_rounds_to_int` | `out-of-scope` | `test_encode_rounds_to_int` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 103 | method | `TestIntegerRepresentation.test_decode_returns_integers` | `out-of-scope` | `test_decode_returns_integers` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 117 | class | `TestPermutationRepresentation` | `out-of-scope` | `TestPermutationRepresentation` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 120 | method | `TestPermutationRepresentation.test_init` | `out-of-scope` | `test_init` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 127 | method | `TestPermutationRepresentation.test_encode_creates_permutation` | `out-of-scope` | `test_encode_creates_permutation` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 139 | method | `TestPermutationRepresentation.test_decode_preserves_permutation` | `out-of-scope` | `test_decode_preserves_permutation` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 149 | method | `TestPermutationRepresentation.test_random_permutation_is_valid` | `out-of-scope` | `test_random_permutation_is_valid` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 159 | class | `TestMixedRepresentation` | `out-of-scope` | `TestMixedRepresentation` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 162 | method | `TestMixedRepresentation.test_init` | `out-of-scope` | `test_init` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 175 | method | `TestMixedRepresentation.test_encode_combines_all` | `out-of-scope` | `test_encode_combines_all` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 194 | method | `TestMixedRepresentation.test_decode_separates_all` | `out-of-scope` | `test_decode_separates_all` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 211 | class | `TestRepresentationConstraints` | `out-of-scope` | `TestRepresentationConstraints` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 214 | method | `TestRepresentationConstraints.test_continuous_with_constraint` | `out-of-scope` | `test_continuous_with_constraint` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 234 | method | `TestRepresentationConstraints.test_repair_infeasible_solution` | `out-of-scope` | `test_repair_infeasible_solution` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 259 | class | `TestRepresentationPerformance` | `out-of-scope` | `TestRepresentationPerformance` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 262 | method | `TestRepresentationPerformance.test_large_permutation_encoding` | `out-of-scope` | `test_large_permutation_encoding` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 275 | method | `TestRepresentationPerformance.test_high_dimensional_continuous` | `out-of-scope` | `test_high_dimensional_continuous` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 296 | function | `test_continuous_various_dimensions` | `out-of-scope` | `test_continuous_various_dimensions` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_representation_pipeline_engineering.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 6 | class | `InPlaceAddMutator` | `out-of-scope` | `InPlaceAddMutator` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 7 | method | `InPlaceAddMutator.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 10 | method | `InPlaceAddMutator.mutate` | `out-of-scope` | `mutate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 16 | class | `RaisingRepair` | `out-of-scope` | `RaisingRepair` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 17 | method | `RaisingRepair.repair` | `out-of-scope` | `repair` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 21 | class | `IdentityRepair` | `out-of-scope` | `IdentityRepair` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 22 | method | `IdentityRepair.repair` | `out-of-scope` | `repair` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 26 | function | `test_transactional_mutate_rolls_back_on_repair_error` | `out-of-scope` | `test_transactional_mutate_rolls_back_on_repair_error` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 42 | function | `test_protect_input_prevents_inplace_mutation` | `out-of-scope` | `test_protect_input_prevents_inplace_mutation` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 57 | function | `test_mutate_batch_falls_back_and_matches_per_item` | `out-of-scope` | `test_mutate_batch_falls_back_and_matches_per_item` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_representation_simple.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 12 | function | `_check_representation_files` | `out-of-scope` | `_check_representation_files` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 30 | function | `_check_representation_content` | `out-of-scope` | `_check_representation_content` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 36 | function | `test_representation_files` | `out-of-scope` | `test_representation_files` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 40 | function | `test_representation_content` | `out-of-scope` | `test_representation_content` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_repro_bundle.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 16 | class | `_DummySolver` | `out-of-scope` | `_DummySolver` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 17 | method | `_DummySolver.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 24 | method | `_DummySolver.set_random_seed` | `out-of-scope` | `set_random_seed` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 28 | function | `test_repro_bundle_build_write_load` | `out-of-scope` | `test_repro_bundle_build_write_load` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 106 | function | `test_compare_repro_bundle_detects_drift` | `out-of-scope` | `test_compare_repro_bundle_detects_drift` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 127 | function | `test_apply_bundle_to_solver_sets_seed_and_limits` | `out-of-scope` | `test_apply_bundle_to_solver_sets_seed_and_limits` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 149 | function | `test_run_cmd_handles_non_default_encoded_bytes` | `out-of-scope` | `test_run_cmd_handles_non_default_encoded_bytes` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 150 | class | `test_run_cmd_handles_non_default_encoded_bytes._Proc` | `out-of-scope` | `_Proc` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 151 | method | `_Proc.test_run_cmd_handles_non_default_encoded_bytes.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 156 | function | `test_run_cmd_handles_non_default_encoded_bytes._fake_run` | `out-of-scope` | `_fake_run` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 165 | function | `test_run_cmd_supports_chinese_cwd_and_gbk_output` | `out-of-scope` | `test_run_cmd_supports_chinese_cwd_and_gbk_output` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 170 | class | `test_run_cmd_supports_chinese_cwd_and_gbk_output._Proc` | `out-of-scope` | `_Proc` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 171 | method | `_Proc.test_run_cmd_supports_chinese_cwd_and_gbk_output.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 176 | function | `test_run_cmd_supports_chinese_cwd_and_gbk_output._fake_run` | `out-of-scope` | `_fake_run` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_requires_metrics_fallback_declared.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 7 | function | `test_nonempty_requires_metrics_has_explicit_fallback_or_policy` | `out-of-scope` | `test_nonempty_requires_metrics_has_explicit_fallback_or_policy` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_robustness_bias.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 4 | function | `test_robustness_bias_penalizes_high_mc_std` | `out-of-scope` | `test_robustness_bias_penalizes_high_mc_std` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 11 | class | `test_robustness_bias_penalizes_high_mc_std.HeteroscedasticNoisySphere` | `out-of-scope` | `HeteroscedasticNoisySphere` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 12 | method | `HeteroscedasticNoisySphere.test_robustness_bias_penalizes_high_mc_std.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 19 | method | `HeteroscedasticNoisySphere.test_robustness_bias_penalizes_high_mc_std.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 27 | class | `test_robustness_bias_penalizes_high_mc_std.TwoCandidatesOnce` | `out-of-scope` | `TwoCandidatesOnce` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 28 | method | `TwoCandidatesOnce.test_robustness_bias_penalizes_high_mc_std.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 31 | method | `TwoCandidatesOnce.test_robustness_bias_penalizes_high_mc_std.propose` | `out-of-scope` | `propose` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 52 | function | `test_robustness_bias_is_noop_without_mc_stats` | `out-of-scope` | `test_robustness_bias_is_noop_without_mc_stats` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 59 | class | `test_robustness_bias_is_noop_without_mc_stats.DeterministicSphere` | `out-of-scope` | `DeterministicSphere` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 60 | method | `DeterministicSphere.test_robustness_bias_is_noop_without_mc_stats.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 63 | method | `DeterministicSphere.test_robustness_bias_is_noop_without_mc_stats.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 82 | function | `test_direct_wiring_monte_carlo_robustness_runs` | `out-of-scope` | `test_direct_wiring_monte_carlo_robustness_runs` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 89 | class | `test_direct_wiring_monte_carlo_robustness_runs.NoisySphere` | `out-of-scope` | `NoisySphere` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 90 | method | `NoisySphere.test_direct_wiring_monte_carlo_robustness_runs.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 93 | method | `NoisySphere.test_direct_wiring_monte_carlo_robustness_runs.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 98 | class | `test_direct_wiring_monte_carlo_robustness_runs.Fixed` | `out-of-scope` | `Fixed` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 99 | method | `Fixed.test_direct_wiring_monte_carlo_robustness_runs.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 102 | method | `Fixed.test_direct_wiring_monte_carlo_robustness_runs.propose` | `out-of-scope` | `propose` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_role_adapters.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 4 | function | `test_role_adapter_contract_strict_requires_keys` | `out-of-scope` | `test_role_adapter_contract_strict_requires_keys` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 7 | class | `test_role_adapter_contract_strict_requires_keys.Dummy` | `out-of-scope` | `Dummy` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 8 | method | `Dummy.test_role_adapter_contract_strict_requires_keys.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 11 | method | `Dummy.test_role_adapter_contract_strict_requires_keys.propose` | `out-of-scope` | `propose` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 28 | function | `test_multi_role_controller_adapter_runs_with_composable_solver` | `out-of-scope` | `test_multi_role_controller_adapter_runs_with_composable_solver` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 35 | class | `test_multi_role_controller_adapter_runs_with_composable_solver.Sphere` | `out-of-scope` | `Sphere` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 36 | method | `Sphere.test_multi_role_controller_adapter_runs_with_composable_solver.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 40 | method | `Sphere.test_multi_role_controller_adapter_runs_with_composable_solver.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 44 | class | `test_multi_role_controller_adapter_runs_with_composable_solver.Explorer` | `out-of-scope` | `Explorer` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 45 | method | `Explorer.test_multi_role_controller_adapter_runs_with_composable_solver.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 48 | method | `Explorer.test_multi_role_controller_adapter_runs_with_composable_solver.propose` | `out-of-scope` | `propose` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 51 | class | `test_multi_role_controller_adapter_runs_with_composable_solver.Exploiter` | `out-of-scope` | `Exploiter` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 52 | method | `Exploiter.test_multi_role_controller_adapter_runs_with_composable_solver.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 55 | method | `Exploiter.test_multi_role_controller_adapter_runs_with_composable_solver.propose` | `out-of-scope` | `propose` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_run_semantics_unified.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 22 | class | `SimpleProblem` | `out-of-scope` | `SimpleProblem` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 24 | method | `SimpleProblem.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 28 | method | `SimpleProblem.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 31 | method | `SimpleProblem.get_num_objectives` | `out-of-scope` | `get_num_objectives` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 35 | class | `HookRecorderPlugin` | `out-of-scope` | `HookRecorderPlugin` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 38 | method | `HookRecorderPlugin.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 44 | method | `HookRecorderPlugin.reset` | `out-of-scope` | `reset` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 49 | method | `HookRecorderPlugin.on_solver_init` | `out-of-scope` | `on_solver_init` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 52 | method | `HookRecorderPlugin.on_population_init` | `out-of-scope` | `on_population_init` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 55 | method | `HookRecorderPlugin.on_generation_start` | `out-of-scope` | `on_generation_start` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 60 | method | `HookRecorderPlugin.on_step` | `out-of-scope` | `on_step` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 63 | method | `HookRecorderPlugin.on_generation_end` | `out-of-scope` | `on_generation_end` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 68 | method | `HookRecorderPlugin.on_solver_finish` | `out-of-scope` | `on_solver_finish` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 71 | method | `HookRecorderPlugin.attach` | `out-of-scope` | `attach` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 75 | class | `GenerationCounterPlugin` | `out-of-scope` | `GenerationCounterPlugin` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 78 | method | `GenerationCounterPlugin.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 82 | method | `GenerationCounterPlugin.on_generation_start` | `out-of-scope` | `on_generation_start` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 85 | method | `GenerationCounterPlugin.on_generation_end` | `out-of-scope` | `on_generation_end` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 88 | method | `GenerationCounterPlugin.all_consistent` | `out-of-scope` | `all_consistent` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 93 | class | `FixedAdapter` | `out-of-scope` | `FixedAdapter` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 96 | method | `FixedAdapter.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 100 | method | `FixedAdapter.propose` | `out-of-scope` | `propose` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 104 | method | `FixedAdapter.update` | `out-of-scope` | `update` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 109 | class | `FaultyProblem` | `out-of-scope` | `FaultyProblem` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 112 | method | `FaultyProblem.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 117 | method | `FaultyProblem.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 123 | method | `FaultyProblem.get_num_objectives` | `out-of-scope` | `get_num_objectives` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 131 | function | `test_hook_order_consistency_blank_solver` | `out-of-scope` | `test_hook_order_consistency_blank_solver` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 135 | class | `test_hook_order_consistency_blank_solver.TestSolver` | `out-of-scope` | `TestSolver` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 136 | method | `TestSolver.test_hook_order_consistency_blank_solver.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 140 | method | `TestSolver.test_hook_order_consistency_blank_solver.step` | `out-of-scope` | `step` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 164 | function | `test_hook_order_consistency_evolution_solver` | `out-of-scope` | `test_hook_order_consistency_evolution_solver` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 195 | function | `test_hook_order_consistency_evolution_vs_composable` | `out-of-scope` | `test_hook_order_consistency_evolution_vs_composable` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 221 | function | `test_generation_counter_consistency_evolution_solver` | `out-of-scope` | `test_generation_counter_consistency_evolution_solver` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 244 | function | `test_max_steps_parameter_compatibility` | `out-of-scope` | `test_max_steps_parameter_compatibility` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 248 | class | `test_max_steps_parameter_compatibility.TestSolver` | `out-of-scope` | `TestSolver` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 249 | method | `TestSolver.test_max_steps_parameter_compatibility.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 253 | method | `TestSolver.test_max_steps_parameter_compatibility.step` | `out-of-scope` | `step` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 277 | function | `test_stop_requested_behavior` | `out-of-scope` | `test_stop_requested_behavior` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 280 | class | `test_stop_requested_behavior.EarlyStopPlugin` | `out-of-scope` | `EarlyStopPlugin` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 281 | method | `EarlyStopPlugin.test_stop_requested_behavior.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 285 | method | `EarlyStopPlugin.test_stop_requested_behavior.on_generation_start` | `out-of-scope` | `on_generation_start` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 289 | method | `EarlyStopPlugin.test_stop_requested_behavior.attach` | `out-of-scope` | `attach` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 306 | function | `test_exception_handling_soft_mode` | `out-of-scope` | `test_exception_handling_soft_mode` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 313 | class | `test_exception_handling_soft_mode.TestSolver` | `out-of-scope` | `TestSolver` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 314 | method | `TestSolver.test_exception_handling_soft_mode.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 319 | method | `TestSolver.test_exception_handling_soft_mode.step` | `out-of-scope` | `step` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 345 | function | `test_return_type_consistency` | `out-of-scope` | `test_return_type_consistency` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 351 | class | `test_return_type_consistency.TestSolver` | `out-of-scope` | `TestSolver` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 352 | method | `TestSolver.test_return_type_consistency.step` | `out-of-scope` | `step` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 379 | function | `test_history_management_consistency` | `out-of-scope` | `test_history_management_consistency` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 400 | function | `test_run_count_tracking` | `out-of-scope` | `test_run_count_tracking` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 417 | function | `test_plugin_on_step_hook_availability` | `out-of-scope` | `test_plugin_on_step_hook_availability` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 423 | class | `test_plugin_on_step_hook_availability.StepCounterPlugin` | `out-of-scope` | `StepCounterPlugin` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 424 | method | `StepCounterPlugin.test_plugin_on_step_hook_availability.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 428 | method | `StepCounterPlugin.test_plugin_on_step_hook_availability.on_step` | `out-of-scope` | `on_step` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 446 | class | `test_plugin_on_step_hook_availability.TestSolver` | `out-of-scope` | `TestSolver` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 447 | method | `TestSolver.test_plugin_on_step_hook_availability.step` | `out-of-scope` | `step` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_run_view_context_store_snapshot.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 6 | function | `test_context_store_snapshot_masks_redis_password` | `out-of-scope` | `test_context_store_snapshot_masks_redis_password` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 22 | function | `test_structure_hash_changes_when_context_store_changes` | `out-of-scope` | `test_structure_hash_changes_when_context_store_changes` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 45 | function | `test_parse_seed_override_accepts_empty_and_int` | `out-of-scope` | `test_parse_seed_override_accepts_empty_and_int` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 52 | function | `test_parse_seed_override_rejects_non_int` | `out-of-scope` | `test_parse_seed_override_rejects_non_int` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_runtime_facade.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 9 | class | `_Sphere` | `out-of-scope` | `_Sphere` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 10 | method | `_Sphere.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 13 | method | `_Sphere.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 18 | function | `test_solver_control_plane_snapshot_and_context_calls` | `out-of-scope` | `test_solver_control_plane_snapshot_and_context_calls` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 33 | function | `test_solver_control_plane_updates_state` | `out-of-scope` | `test_solver_control_plane_updates_state` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_runtime_semantics_and_strictness.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 7 | function | `test_composable_solver_always_triggers_on_step` | `out-of-scope` | `test_composable_solver_always_triggers_on_step` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 13 | class | `test_composable_solver_always_triggers_on_step._Problem` | `out-of-scope` | `_Problem` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 14 | method | `_Problem.test_composable_solver_always_triggers_on_step.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 17 | method | `_Problem.test_composable_solver_always_triggers_on_step.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 21 | class | `test_composable_solver_always_triggers_on_step._Adapter` | `out-of-scope` | `_Adapter` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 22 | method | `_Adapter.test_composable_solver_always_triggers_on_step.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 25 | method | `_Adapter.test_composable_solver_always_triggers_on_step.propose` | `out-of-scope` | `propose` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 29 | class | `test_composable_solver_always_triggers_on_step._StepCounter` | `out-of-scope` | `_StepCounter` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 30 | method | `_StepCounter.test_composable_solver_always_triggers_on_step.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 34 | method | `_StepCounter.test_composable_solver_always_triggers_on_step.on_step` | `out-of-scope` | `on_step` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 48 | function | `test_plugin_manager_strict_mode_fails_fast` | `out-of-scope` | `test_plugin_manager_strict_mode_fails_fast` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 51 | class | `test_plugin_manager_strict_mode_fails_fast._Boom` | `out-of-scope` | `_Boom` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 52 | method | `_Boom.test_plugin_manager_strict_mode_fails_fast.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 55 | method | `_Boom.test_plugin_manager_strict_mode_fails_fast.on_generation_start` | `out-of-scope` | `on_generation_start` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 65 | function | `test_parallel_repair_per_item_fallback_and_error_report` | `out-of-scope` | `test_parallel_repair_per_item_fallback_and_error_report` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 68 | class | `test_parallel_repair_per_item_fallback_and_error_report._Repair` | `out-of-scope` | `_Repair` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 69 | method | `_Repair.test_parallel_repair_per_item_fallback_and_error_report.repair` | `out-of-scope` | `repair` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 85 | function | `test_parallel_repair_reports_errors_to_context_metrics` | `out-of-scope` | `test_parallel_repair_reports_errors_to_context_metrics` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 88 | class | `test_parallel_repair_reports_errors_to_context_metrics._Repair` | `out-of-scope` | `_Repair` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 89 | method | `_Repair.test_parallel_repair_reports_errors_to_context_metrics.repair` | `out-of-scope` | `repair` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_sa_adapter.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 4 | function | `test_simulated_annealing_adapter_runs_and_cools` | `out-of-scope` | `test_simulated_annealing_adapter_runs_and_cools` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 39 | function | `test_sa_direct_wiring_smoke` | `out-of-scope` | `test_sa_direct_wiring_smoke` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_schema_version.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 7 | function | `test_stamp_schema_and_check_ok` | `out-of-scope` | `test_stamp_schema_and_check_ok` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 15 | function | `test_schema_check_reports_version_mismatch` | `out-of-scope` | `test_schema_check_reports_version_mismatch` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 22 | function | `test_schema_tool_checks_known_json_patterns` | `out-of-scope` | `test_schema_tool_checks_known_json_patterns` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 30 | function | `test_schema_tool_checks_repro_bundle_pattern` | `out-of-scope` | `test_schema_tool_checks_repro_bundle_pattern` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 38 | function | `test_schema_tool_skips_runs_by_default` | `out-of-scope` | `test_schema_tool_skips_runs_by_default` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 48 | function | `test_schema_tool_can_include_runs_explicitly` | `out-of-scope` | `test_schema_tool_can_include_runs_explicitly` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 58 | function | `test_schema_tool_scans_explicit_historical_root` | `out-of-scope` | `test_schema_tool_scans_explicit_historical_root` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_sequence_graph_plugin.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 10 | class | `_Adapter` | `out-of-scope` | `_Adapter` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 11 | method | `_Adapter.propose` | `out-of-scope` | `propose` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 14 | method | `_Adapter.update` | `out-of-scope` | `update` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 18 | class | `_Solver` | `out-of-scope` | `_Solver` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 19 | method | `_Solver.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 25 | method | `_Solver.evaluate_population` | `out-of-scope` | `evaluate_population` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 29 | function | `test_sequence_graph_plugin_records_and_writes` | `out-of-scope` | `test_sequence_graph_plugin_records_and_writes` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 58 | function | `test_sequence_graph_plugin_trace_fields` | `out-of-scope` | `test_sequence_graph_plugin_trace_fields` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_single_trajectory_adaptive_adapter.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 4 | function | `_pipeline` | `out-of-scope` | `_pipeline` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 15 | function | `test_single_trajectory_adapter_runs` | `out-of-scope` | `test_single_trajectory_adapter_runs` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 34 | function | `test_single_trajectory_direct_wiring` | `out-of-scope` | `test_single_trajectory_direct_wiring` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_snapshot_store.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 8 | function | `test_snapshot_store_memory_roundtrip` | `out-of-scope` | `test_snapshot_store_memory_roundtrip` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 23 | function | `test_snapshot_store_file_roundtrip` | `out-of-scope` | `test_snapshot_store_file_roundtrip` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_solver.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 17 | class | `SimpleSphere` | `out-of-scope` | `SimpleSphere` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 20 | method | `SimpleSphere.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 27 | method | `SimpleSphere.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 32 | class | `SimpleRastrigin` | `out-of-scope` | `SimpleRastrigin` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 35 | method | `SimpleRastrigin.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 42 | method | `SimpleRastrigin.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 48 | class | `TestBlackBoxProblem` | `out-of-scope` | `TestBlackBoxProblem` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 51 | method | `TestBlackBoxProblem.test_problem_initialization` | `out-of-scope` | `test_problem_initialization` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 59 | method | `TestBlackBoxProblem.test_bounds_checking` | `out-of-scope` | `test_bounds_checking` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 71 | method | `TestBlackBoxProblem.test_evaluate` | `out-of-scope` | `test_evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 82 | class | `TestSolverInitialization` | `out-of-scope` | `TestSolverInitialization` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 85 | method | `TestSolverInitialization.test_solver_creation` | `out-of-scope` | `test_solver_creation` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 93 | method | `TestSolverInitialization.test_solver_default_params` | `out-of-scope` | `test_solver_default_params` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 103 | class | `TestSolverBasicOperations` | `out-of-scope` | `TestSolverBasicOperations` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 106 | method | `TestSolverBasicOperations.test_initialize_population` | `out-of-scope` | `test_initialize_population` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 122 | method | `TestSolverBasicOperations.test_evaluate_population` | `out-of-scope` | `test_evaluate_population` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 134 | class | `TestSolverOptimization` | `out-of-scope` | `TestSolverOptimization` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 137 | method | `TestSolverOptimization.test_simple_optimization` | `out-of-scope` | `test_simple_optimization` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 154 | method | `TestSolverOptimization.test_rastrigin_optimization` | `out-of-scope` | `test_rastrigin_optimization` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 172 | class | `TestSolverWithBias` | `out-of-scope` | `TestSolverWithBias` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 175 | method | `TestSolverWithBias.test_solver_with_penalty_bias` | `out-of-scope` | `test_solver_with_penalty_bias` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 183 | method | `TestSolverWithBias.test_solver_with_penalty_bias.far_from_origin_penalty` | `out-of-scope` | `far_from_origin_penalty` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 202 | method | `TestSolverWithBias.test_solver_with_convergence_bias` | `out-of-scope` | `test_solver_with_convergence_bias` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 222 | class | `TestSolverReproducibility` | `out-of-scope` | `TestSolverReproducibility` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 225 | method | `TestSolverReproducibility.test_fixed_seed_reproducibility` | `out-of-scope` | `test_fixed_seed_reproducibility` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 247 | class | `TestSolverIntegration` | `out-of-scope` | `TestSolverIntegration` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 250 | method | `TestSolverIntegration.test_multi_start_optimization` | `out-of-scope` | `test_multi_start_optimization` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 268 | method | `TestSolverIntegration.test_high_dimensional_optimization` | `out-of-scope` | `test_high_dimensional_optimization` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_solver_naming.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 5 | function | `test_evolution_solver_is_solver_base_subclass` | `out-of-scope` | `test_evolution_solver_is_solver_base_subclass` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 9 | function | `test_runtime_import_core_exposes_new_solver_symbols` | `out-of-scope` | `test_runtime_import_core_exposes_new_solver_symbols` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_stable_api_smoke.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 4 | function | `test_stable_top_level_imports` | `out-of-scope` | `test_stable_top_level_imports` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 11 | function | `test_stable_catalog_entry_points_importable` | `out-of-scope` | `test_stable_catalog_entry_points_importable` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 21 | function | `test_profiler_plugin_importable` | `out-of-scope` | `test_profiler_plugin_importable` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_suites_plugin_strict.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 4 | function | `test_set_plugin_strict_helper` | `out-of-scope` | `test_set_plugin_strict_helper` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 9 | class | `test_set_plugin_strict_helper._P` | `out-of-scope` | `_P` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 10 | method | `_P.test_set_plugin_strict_helper.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 13 | method | `_P.test_set_plugin_strict_helper.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 22 | function | `test_set_parallel_thread_bias_isolation_helper` | `out-of-scope` | `test_set_parallel_thread_bias_isolation_helper` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 28 | class | `test_set_parallel_thread_bias_isolation_helper._P` | `out-of-scope` | `_P` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 29 | method | `_P.test_set_parallel_thread_bias_isolation_helper.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 32 | method | `_P.test_set_parallel_thread_bias_isolation_helper.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_surrogate.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 15 | class | `TestSurrogateTrainer` | `out-of-scope` | `TestSurrogateTrainer` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 19 | method | `TestSurrogateTrainer.sample_data` | `out-of-scope` | `sample_data` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 26 | method | `TestSurrogateTrainer.test_trainer_initialization` | `out-of-scope` | `test_trainer_initialization` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 37 | method | `TestSurrogateTrainer.test_train_and_predict` | `out-of-scope` | `test_train_and_predict` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 55 | class | `TestSurrogateManager` | `out-of-scope` | `TestSurrogateManager` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 58 | method | `TestSurrogateManager.test_manager_initialization` | `out-of-scope` | `test_manager_initialization` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 67 | method | `TestSurrogateManager.test_add_surrogate_model` | `out-of-scope` | `test_add_surrogate_model` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 77 | method | `TestSurrogateManager.test_manager_training_and_prediction` | `out-of-scope` | `test_manager_training_and_prediction` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 98 | class | `TestSurrogateStrategies` | `out-of-scope` | `TestSurrogateStrategies` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 101 | method | `TestSurrogateStrategies.test_uncertainty_sampling` | `out-of-scope` | `test_uncertainty_sampling` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 117 | method | `TestSurrogateStrategies.test_exploitation_exploration_tradeoff` | `out-of-scope` | `test_exploitation_exploration_tradeoff` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 131 | class | `TestSurrogateIntegration` | `out-of-scope` | `TestSurrogateIntegration` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 135 | method | `TestSurrogateIntegration.test_surrogate_assisted_optimization` | `out-of-scope` | `test_surrogate_assisted_optimization` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 141 | class | `TestSurrogateIntegration.test_surrogate_assisted_optimization.ExpensiveProblem` | `out-of-scope` | `ExpensiveProblem` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 142 | method | `TestSurrogateIntegration.ExpensiveProblem.test_surrogate_assisted_optimization.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 149 | method | `TestSurrogateIntegration.ExpensiveProblem.test_surrogate_assisted_optimization.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 181 | function | `test_different_surrogate_models` | `out-of-scope` | `test_different_surrogate_models` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_tomli_fallback.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 7 | function | `test_tomli_fallback_for_project_and_catalog_registry` | `out-of-scope` | `test_tomli_fallback_for_project_and_catalog_registry` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_trust_region_adapters.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 18 | class | `_Problem` | `out-of-scope` | `_Problem` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 19 | method | `_Problem.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 23 | class | `_Solver` | `out-of-scope` | `_Solver` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 24 | method | `_Solver.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 32 | function | `test_trust_region_dfo_basic_cycle` | `out-of-scope` | `test_trust_region_dfo_basic_cycle` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 48 | function | `test_trust_region_nonsmooth_scores_linf` | `out-of-scope` | `test_trust_region_nonsmooth_scores_linf` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 62 | function | `test_trust_region_subspace_state_roundtrip_keeps_basis_and_steps` | `out-of-scope` | `test_trust_region_subspace_state_roundtrip_keeps_basis_and_steps` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 80 | function | `test_trust_region_mo_dfo_uses_context_weights_and_persists_them` | `out-of-scope` | `test_trust_region_mo_dfo_uses_context_weights_and_persists_them` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_vns_adapter.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 4 | function | `test_vns_adapter_improves_sphere` | `out-of-scope` | `test_vns_adapter_improves_sphere` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 11 | class | `test_vns_adapter_improves_sphere.Sphere` | `out-of-scope` | `Sphere` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 12 | method | `Sphere.test_vns_adapter_improves_sphere.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 16 | method | `Sphere.test_vns_adapter_improves_sphere.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/test_vscode_doctor_integration_config.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 10 | function | `_load_json` | `out-of-scope` | `_load_json` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 14 | function | `test_vscode_tasks_contains_doctor_problem_task` | `out-of-scope` | `test_vscode_tasks_contains_doctor_problem_task` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 30 | function | `test_vscode_settings_contains_trigger_task_on_save` | `out-of-scope` | `test_vscode_settings_contains_trigger_task_on_save` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 50 | function | `test_trigger_task_label_matches_existing_task` | `out-of-scope` | `test_trigger_task_label_matches_existing_task` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/verify_algorithm_biases.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 21 | class | `_Problem` | `out-of-scope` | `_Problem` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 25 | class | `_Solver` | `out-of-scope` | `_Solver` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 26 | method | `_Solver.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 33 | method | `_Solver.init_candidate` | `out-of-scope` | `init_candidate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 37 | method | `_Solver.mutate_candidate` | `out-of-scope` | `mutate_candidate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 41 | method | `_Solver.repair_candidate` | `out-of-scope` | `repair_candidate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 46 | function | `_eval` | `out-of-scope` | `_eval` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 55 | function | `test_imports` | `out-of-scope` | `test_imports` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 64 | function | `test_all_process_algorithms_run_as_adapters` | `out-of-scope` | `test_all_process_algorithms_run_as_adapters` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 87 | function | `test_population_contract_for_population_based_adapters` | `out-of-scope` | `test_population_contract_for_population_based_adapters` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/verify_biases.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 15 | function | `test_bias_imports_are_signal_level` | `out-of-scope` | `test_bias_imports_are_signal_level` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 22 | function | `test_tabu_and_diversity_bias_compute_scalar` | `out-of-scope` | `test_tabu_and_diversity_bias_compute_scalar` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 43 | function | `test_catalog_keeps_process_algorithms_in_adapter_layer` | `out-of-scope` | `test_catalog_keeps_process_algorithms_in_adapter_layer` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/verify_compatibility.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 15 | class | `SimpleProblem` | `out-of-scope` | `SimpleProblem` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 18 | method | `SimpleProblem.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 22 | method | `SimpleProblem.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 26 | method | `SimpleProblem.evaluate_constraints` | `out-of-scope` | `evaluate_constraints` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 31 | function | `test_bias_module_import` | `out-of-scope` | `test_bias_module_import` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 46 | function | `test_universal_manager_import` | `out-of-scope` | `test_universal_manager_import` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 63 | function | `test_bias_module_creation` | `out-of-scope` | `test_bias_module_creation` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 87 | function | `test_universal_manager_creation` | `out-of-scope` | `test_universal_manager_creation` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 111 | function | `test_from_universal_manager` | `out-of-scope` | `test_from_universal_manager` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 141 | function | `test_bias_computation` | `out-of-scope` | `test_bias_computation` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 187 | function | `test_solver_integration` | `out-of-scope` | `test_solver_integration` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 198 | class | `test_solver_integration.TestProblem` | `out-of-scope` | `TestProblem` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 199 | method | `TestProblem.test_solver_integration.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 202 | method | `TestProblem.test_solver_integration.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 234 | function | `test_enable_disable` | `out-of-scope` | `test_enable_disable` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 263 | function | `main` | `out-of-scope` | `main` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/verify_guide_code.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 40 | class | `VehicleRoutingProblem` | `out-of-scope` | `VehicleRoutingProblem` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 43 | method | `VehicleRoutingProblem.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 67 | method | `VehicleRoutingProblem._compute_distance_matrix` | `out-of-scope` | `_compute_distance_matrix` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 78 | method | `VehicleRoutingProblem.decode_solution` | `out-of-scope` | `decode_solution` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 98 | method | `VehicleRoutingProblem.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 158 | class | `VRPHybridInitializer` | `out-of-scope` | `VRPHybridInitializer` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 159 | method | `VRPHybridInitializer.initialize` | `out-of-scope` | `initialize` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 202 | class | `VRPHybridMutator` | `out-of-scope` | `VRPHybridMutator` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 203 | method | `VRPHybridMutator.mutate` | `out-of-scope` | `mutate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 252 | class | `VRPDomainBias` | `out-of-scope` | `VRPDomainBias` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 255 | method | `VRPDomainBias.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 259 | method | `VRPDomainBias.compute` | `out-of-scope` | `compute` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/verify_guide_concepts.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 31 | class | `VehicleRoutingProblem` | `out-of-scope` | `VehicleRoutingProblem` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 32 | method | `VehicleRoutingProblem.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 47 | method | `VehicleRoutingProblem._compute_distance_matrix` | `out-of-scope` | `_compute_distance_matrix` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 57 | method | `VehicleRoutingProblem.decode_solution` | `out-of-scope` | `decode_solution` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 69 | method | `VehicleRoutingProblem.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 115 | class | `VRPHybridInitializer` | `out-of-scope` | `VRPHybridInitializer` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 116 | method | `VRPHybridInitializer.initialize` | `out-of-scope` | `initialize` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 149 | class | `VRPDomainBias` | `out-of-scope` | `VRPDomainBias` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 150 | method | `VRPDomainBias.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 154 | method | `VRPDomainBias.compute` | `out-of-scope` | `compute` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/verify_guide_full.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 34 | class | `VehicleRoutingProblem` | `out-of-scope` | `VehicleRoutingProblem` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 37 | method | `VehicleRoutingProblem.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 67 | method | `VehicleRoutingProblem._compute_distance_matrix` | `out-of-scope` | `_compute_distance_matrix` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 78 | method | `VehicleRoutingProblem.decode_solution` | `out-of-scope` | `decode_solution` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 99 | method | `VehicleRoutingProblem.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 121 | method | `VehicleRoutingProblem.evaluate_constraints` | `out-of-scope` | `evaluate_constraints` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 178 | class | `VRPHybridInitializer` | `out-of-scope` | `VRPHybridInitializer` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 181 | method | `VRPHybridInitializer.initialize` | `out-of-scope` | `initialize` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 201 | class | `VRPHybridMutator` | `out-of-scope` | `VRPHybridMutator` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 204 | method | `VRPHybridMutator.mutate` | `out-of-scope` | `mutate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 259 | class | `VRPDomainBias` | `out-of-scope` | `VRPDomainBias` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 262 | method | `VRPDomainBias.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 266 | method | `VRPDomainBias.compute` | `out-of-scope` | `compute` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tests/verify_how_to_build_guide.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 34 | class | `VehicleRoutingProblem` | `out-of-scope` | `VehicleRoutingProblem` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 37 | method | `VehicleRoutingProblem.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 61 | method | `VehicleRoutingProblem._compute_distance_matrix` | `out-of-scope` | `_compute_distance_matrix` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 72 | method | `VehicleRoutingProblem.decode_solution` | `out-of-scope` | `decode_solution` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 92 | method | `VehicleRoutingProblem.evaluate` | `out-of-scope` | `evaluate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 114 | method | `VehicleRoutingProblem.evaluate_constraints` | `out-of-scope` | `evaluate_constraints` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 151 | class | `VRPHybridInitializer` | `out-of-scope` | `VRPHybridInitializer` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 152 | method | `VRPHybridInitializer.initialize` | `out-of-scope` | `initialize` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 168 | class | `VRPHybridMutator` | `out-of-scope` | `VRPHybridMutator` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 169 | method | `VRPHybridMutator.mutate` | `out-of-scope` | `mutate` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 220 | class | `VRPDomainBias` | `out-of-scope` | `VRPDomainBias` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 223 | method | `VRPDomainBias.__init__` | `out-of-scope` | `__init__` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |
| 227 | method | `VRPDomainBias.compute` | `out-of-scope` | `compute` | `high` | `-` | 测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。 |

### `tools/build_catalog.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 12 | function | `_read_text` | `keep` | `_read_text` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 16 | function | `_extract_defs` | `keep` | `_extract_defs` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 51 | function | `_module_summary` | `keep` | `_module_summary` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 69 | function | `_iter_py_files` | `keep` | `_iter_py_files` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 80 | function | `_format_defs` | `keep` | `_format_defs` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 91 | function | `_write_file` | `keep` | `_write_file` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 95 | function | `_header` | `keep` | `_header` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 105 | function | `build_tools_index` | `keep` | `build_tools_index` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 136 | function | `build_bias_index` | `keep` | `build_bias_index` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 173 | function | `build_representation_index` | `keep` | `build_representation_index` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 194 | function | `build_examples_index` | `keep` | `build_examples_index` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 223 | function | `build_catalog_index` | `keep` | `build_catalog_index` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 243 | function | `main` | `keep` | `main` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `tools/build_engineering_book_docx.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 22 | function | `_add_code_block` | `keep` | `_add_code_block` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 29 | function | `_append_md` | `keep` | `_append_md` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 76 | function | `_load_manifest` | `keep` | `_load_manifest` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 86 | function | `build` | `keep` | `build` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 101 | function | `main` | `keep` | `main` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `tools/catalog_integrity_checker.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 11 | class | `CheckFailure` | `keep` | `CheckFailure` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 19 | class | `CheckWarning` | `keep` | `CheckWarning` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 27 | class | `CheckResult` | `keep` | `CheckResult` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 36 | class | `CatalogIntegrityChecker` | `keep` | `CatalogIntegrityChecker` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 55 | method | `CatalogIntegrityChecker.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 78 | method | `CatalogIntegrityChecker.run` | `keep` | `run` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 167 | method | `CatalogIntegrityChecker._has_any_contract` | `keep` | `_has_any_contract` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 181 | method | `CatalogIntegrityChecker._has_context_notes` | `keep` | `_has_context_notes` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 189 | method | `CatalogIntegrityChecker._normalize_values` | `keep` | `_normalize_values` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 207 | method | `CatalogIntegrityChecker._missing_usage_fields` | `keep` | `_missing_usage_fields` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 219 | method | `CatalogIntegrityChecker._load_context_conflict_waiver` | `keep` | `_load_context_conflict_waiver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 234 | function | `_ensure_repo_parent_on_sys_path` | `keep` | `_ensure_repo_parent_on_sys_path` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 241 | function | `_print_result` | `keep` | `_print_result` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 269 | function | `main` | `keep` | `main` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `tools/check_repo_root_hygiene.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 8 | function | `_find_violations` | `keep` | `_find_violations` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 22 | function | `main` | `keep` | `main` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `tools/cleanup_project.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 17 | class | `ProjectCleaner` | `keep` | `ProjectCleaner` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 20 | method | `ProjectCleaner.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 26 | method | `ProjectCleaner.clean_pycache` | `keep` | `clean_pycache` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 42 | method | `ProjectCleaner.clean_pyc_files` | `keep` | `clean_pyc_files` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 57 | method | `ProjectCleaner.clean_temp_files` | `keep` | `clean_temp_files` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 74 | method | `ProjectCleaner.clean_test_results` | `keep` | `clean_test_results` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 102 | method | `ProjectCleaner.clean_all` | `keep` | `clean_all` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 120 | method | `ProjectCleaner._print_summary` | `keep` | `_print_summary` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 139 | method | `ProjectCleaner._estimate_size` | `keep` | `_estimate_size` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 155 | function | `clean_gitkeep_files` | `keep` | `clean_gitkeep_files` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `tools/fix_catalog_bilingual.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 11 | function | `_fix_registry` | `keep` | `_fix_registry` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 261 | function | `_fix_entries` | `keep` | `_fix_entries` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 372 | function | `main` | `keep` | `main` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `tools/generate_api_docs.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 10 | function | `main` | `keep` | `main` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `tools/generate_api_rename_audit.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 97 | class | `SymbolRecord` | `keep` | `SymbolRecord` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 109 | class | `Advice` | `keep` | `Advice` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 117 | function | `iter_python_files` | `keep` | `iter_python_files` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 124 | function | `classify_bucket` | `keep` | `classify_bucket` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 149 | class | `SymbolCollector` | `keep` | `SymbolCollector` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 150 | method | `SymbolCollector.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 157 | method | `SymbolCollector._qualified_name` | `keep` | `_qualified_name` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 161 | method | `SymbolCollector._params` | `keep` | `_params` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 174 | method | `SymbolCollector.visit_ClassDef` | `keep` | `visit_ClassDef` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 192 | method | `SymbolCollector.visit_FunctionDef` | `keep` | `visit_FunctionDef` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 211 | method | `SymbolCollector.visit_AsyncFunctionDef` | `keep` | `visit_AsyncFunctionDef` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 231 | function | `read_symbols` | `keep` | `read_symbols` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 242 | function | `is_dunder` | `keep` | `is_dunder` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 246 | function | `param_suggestions` | `keep` | `param_suggestions` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 258 | function | `suggest_resolve_name` | `keep` | `suggest_resolve_name` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 294 | function | `advise` | `keep` | `advise` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 459 | function | `build_markdown` | `keep` | `build_markdown` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 530 | function | `write_csv` | `keep` | `write_csv` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 563 | function | `main` | `keep` | `main` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `tools/import_scan_utils.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 11 | class | `Failure` | `keep` | `Failure` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 16 | function | `scan` | `keep` | `scan` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 28 | function | `main` | `keep` | `main` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `tools/min_repro_5min.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 23 | class | `_MinProblem` | `keep` | `_MinProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 24 | method | `_MinProblem.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 33 | method | `_MinProblem.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 37 | method | `_MinProblem.evaluate_constraints` | `keep` | `evaluate_constraints` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 42 | function | `main` | `keep` | `main` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `tools/optional_dependency_guard.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 60 | function | `_iter_python_files` | `keep` | `_iter_python_files` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 72 | function | `_imported_top_name` | `keep` | `_imported_top_name` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 84 | function | `_collect_violations_in_block` | `keep` | `_collect_violations_in_block` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 119 | function | `check_file` | `keep` | `check_file` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 131 | function | `main` | `keep` | `main` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `tools/plugin_order_semantics_scenarios.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 19 | class | `DemoProblem` | `keep` | `DemoProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 20 | method | `DemoProblem.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 23 | method | `DemoProblem.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 28 | class | `NamedPlugin` | `keep` | `NamedPlugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 29 | method | `NamedPlugin.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 33 | class | `RequestOrderPlugin` | `keep` | `RequestOrderPlugin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 34 | method | `RequestOrderPlugin.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 37 | method | `RequestOrderPlugin.on_generation_end` | `keep` | `on_generation_end` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 42 | function | `plugin_names` | `keep` | `plugin_names` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 46 | function | `print_case` | `keep` | `print_case` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 52 | function | `case_1_priority_smaller_first` | `keep` | `case_1_priority_smaller_first` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 61 | function | `case_2_unknown_reference_fails` | `keep` | `case_2_unknown_reference_fails` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 72 | function | `case_3_priority_conflict_fails` | `keep` | `case_3_priority_conflict_fails` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 84 | function | `case_4_runtime_freeze` | `keep` | `case_4_runtime_freeze` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 99 | function | `case_5_request_order_boundary_apply` | `keep` | `case_5_request_order_boundary_apply` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 110 | function | `case_6_nested_solver_scope_isolation` | `keep` | `case_6_nested_solver_scope_isolation` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 132 | function | `run_demo` | `keep` | `run_demo` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `tools/release/make_v010_repro_package.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 29 | function | `_ensure_repo_parent_on_sys_path` | `keep` | `_ensure_repo_parent_on_sys_path` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 37 | function | `_copy_paths` | `keep` | `_copy_paths` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 58 | function | `_find_latest_file` | `keep` | `_find_latest_file` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 69 | function | `_write_manifest` | `keep` | `_write_manifest` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 94 | function | `build_package` | `keep` | `build_package` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 144 | function | `main` | `keep` | `main` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `tools/schema_tool.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 12 | class | `SchemaIssue` | `keep` | `SchemaIssue` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 18 | function | `_ensure_repo_parent_on_sys_path` | `keep` | `_ensure_repo_parent_on_sys_path` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 24 | function | `_infer_schema_name` | `keep` | `_infer_schema_name` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 41 | function | `_is_historical_root` | `keep` | `_is_historical_root` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 51 | function | `_iter_json_files` | `keep` | `_iter_json_files` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 68 | function | `check_files` | `keep` | `check_files` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 92 | function | `main` | `keep` | `main` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/__init__.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 34 | function | `__getattr__` | `keep` | `__getattr__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |

### `utils/analysis/metrics.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 9 | function | `pareto_filter` | `keep` | `pareto_filter` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 31 | function | `hypervolume_2d` | `keep` | `hypervolume_2d` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 59 | function | `igd` | `keep` | `igd` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 76 | function | `reference_front_zdt1` | `keep` | `reference_front_zdt1` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 83 | function | `reference_front_zdt3` | `keep` | `reference_front_zdt3` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 102 | function | `reference_front_dtlz2` | `keep` | `reference_front_dtlz2` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/constraints/constraint_utils.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 14 | function | `evaluate_constraints_safe` | `keep` | `evaluate_constraints_safe` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 34 | function | `evaluate_constraints_batch_safe` | `keep` | `evaluate_constraints_batch_safe` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `core/state/context_contracts.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 21 | function | `_normalize_fields` | `keep` | `_normalize_fields` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 34 | function | `_normalize_notes` | `keep` | `_normalize_notes` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 60 | function | `_collect_attrs` | `keep` | `_collect_attrs` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 70 | function | `_merge_notes` | `keep` | `_merge_notes` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 90 | function | `_flatten_values` | `keep` | `_flatten_values` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 103 | class | `ContextContract` | `keep` | `ContextContract` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 110 | method | `ContextContract.normalized` | `keep` | `normalized` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 119 | method | `ContextContract.to_dict` | `keep` | `to_dict` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 129 | method | `ContextContract.merge` | `keep` | `merge` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 141 | function | `get_component_contract` | `keep` | `get_component_contract` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 198 | function | `collect_solver_contracts` | `keep` | `collect_solver_contracts` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 202 | function | `collect_solver_contracts._add` | `keep` | `_add` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 241 | function | `validate_context_contracts` | `keep` | `validate_context_contracts` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 254 | function | `detect_context_conflicts` | `keep` | `detect_context_conflicts` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `core/state/context_events.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 9 | class | `ContextEvent` | `keep` | `ContextEvent` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 18 | method | `ContextEvent.to_dict` | `keep` | `to_dict` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 30 | function | `record_context_event` | `keep` | `record_context_event` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 54 | function | `apply_context_event` | `keep` | `apply_context_event` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 83 | function | `replay_context` | `keep` | `replay_context` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `core/state/context_keys.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 296 | function | `normalize_context_key` | `keep` | `normalize_context_key` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `core/state/context_schema.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 8 | class | `MinimalEvaluationContext` | `keep` | `MinimalEvaluationContext` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 25 | method | `MinimalEvaluationContext.to_dict` | `keep` | `to_dict` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 39 | function | `build_minimal_context` | `keep` | `build_minimal_context` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 69 | function | `validate_minimal_context` | `keep` | `validate_minimal_context` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 101 | class | `ContextField` | `keep` | `ContextField` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 111 | class | `ContextSchema` | `keep` | `ContextSchema` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 116 | method | `ContextSchema.required_keys` | `keep` | `required_keys` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 119 | method | `ContextSchema.field_map` | `keep` | `field_map` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 202 | function | `validate_context` | `keep` | `validate_context` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 238 | function | `get_context_lifecycle` | `keep` | `get_context_lifecycle` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 251 | function | `is_replayable_context` | `keep` | `is_replayable_context` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 264 | function | `strip_context_for_replay` | `keep` | `strip_context_for_replay` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `core/state/context_store.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 16 | class | `ContextStore` | `keep` | `ContextStore` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 20 | method | `ContextStore.get` | `keep` | `get` | `high` | `-` | 通用存取方法，参数别名规则不适用。 |
| 24 | method | `ContextStore.set` | `keep` | `set` | `high` | `-` | 通用存取方法，参数别名规则不适用。 |
| 28 | method | `ContextStore.delete` | `keep` | `delete` | `high` | `-` | 通用存取方法，参数别名规则不适用。 |
| 32 | method | `ContextStore.clear` | `keep` | `clear` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 36 | method | `ContextStore.snapshot` | `keep` | `snapshot` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 39 | method | `ContextStore.update` | `keep` | `update` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 44 | class | `InMemoryContextStore` | `keep` | `InMemoryContextStore` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 47 | method | `InMemoryContextStore.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 52 | method | `InMemoryContextStore._effective_ttl` | `keep` | `_effective_ttl` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 59 | method | `InMemoryContextStore._sweep_expired` | `keep` | `_sweep_expired` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 68 | method | `InMemoryContextStore.get` | `keep` | `get` | `high` | `-` | 通用存取方法，参数别名规则不适用。 |
| 72 | method | `InMemoryContextStore.set` | `keep` | `set` | `high` | `-` | 通用存取方法，参数别名规则不适用。 |
| 82 | method | `InMemoryContextStore.delete` | `keep` | `delete` | `high` | `-` | 通用存取方法，参数别名规则不适用。 |
| 87 | method | `InMemoryContextStore.clear` | `keep` | `clear` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 91 | method | `InMemoryContextStore.snapshot` | `keep` | `snapshot` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 96 | class | `RedisContextStore` | `keep` | `RedisContextStore` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 99 | method | `RedisContextStore.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 114 | method | `RedisContextStore._k` | `keep` | `_k` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 117 | method | `RedisContextStore._effective_ttl` | `keep` | `_effective_ttl` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 126 | method | `RedisContextStore.get` | `keep` | `get` | `high` | `-` | 通用存取方法，参数别名规则不适用。 |
| 135 | method | `RedisContextStore.set` | `keep` | `set` | `high` | `-` | 通用存取方法，参数别名规则不适用。 |
| 147 | method | `RedisContextStore.delete` | `keep` | `delete` | `high` | `-` | 通用存取方法，参数别名规则不适用。 |
| 150 | method | `RedisContextStore.clear` | `keep` | `clear` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 161 | method | `RedisContextStore.snapshot` | `keep` | `snapshot` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 177 | function | `create_context_store` | `keep` | `create_context_store` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/dynamic/cli_provider.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 20 | class | `CLISignalProvider` | `keep` | `CLISignalProvider` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 29 | method | `CLISignalProvider.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 35 | method | `CLISignalProvider.read` | `keep` | `read` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 39 | method | `CLISignalProvider._loop` | `keep` | `_loop` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 53 | method | `CLISignalProvider._parse_line` | `keep` | `_parse_line` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/dynamic/switch.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 21 | class | `DynamicSwitchConfig` | `keep` | `DynamicSwitchConfig` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 38 | class | `SignalProviderBase` | `keep` | `SignalProviderBase` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 42 | method | `SignalProviderBase.read` | `keep` | `read` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 46 | method | `SignalProviderBase.close` | `keep` | `close` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 51 | class | `DynamicSwitchBase` | `keep` | `DynamicSwitchBase` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 67 | method | `DynamicSwitchBase.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 87 | method | `DynamicSwitchBase.on_solver_init` | `keep` | `on_solver_init` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 90 | method | `DynamicSwitchBase.on_generation_start` | `keep` | `on_generation_start` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 111 | method | `DynamicSwitchBase.should_switch` | `keep` | `should_switch` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 115 | method | `DynamicSwitchBase.select_switch_mode` | `keep` | `select_switch_mode` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 119 | method | `DynamicSwitchBase.soft_switch` | `keep` | `soft_switch` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 123 | method | `DynamicSwitchBase.hard_switch` | `keep` | `hard_switch` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 130 | method | `DynamicSwitchBase._update_signals` | `keep` | `_update_signals` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 141 | method | `DynamicSwitchBase._build_context` | `keep` | `_build_context` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 153 | method | `DynamicSwitchBase._decide_mode` | `keep` | `_decide_mode` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 159 | method | `DynamicSwitchBase._apply_switch` | `keep` | `_apply_switch` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 185 | method | `DynamicSwitchBase._sync_solver_state` | `keep` | `_sync_solver_state` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 191 | method | `DynamicSwitchBase._capture_strategy_weights` | `keep` | `_capture_strategy_weights` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/engineering/config_loader.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 19 | class | `ConfigError` | `keep` | `ConfigError` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 23 | function | `load_config` | `keep` | `load_config` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 58 | function | `merge_dicts` | `keep` | `merge_dicts` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 69 | function | `select_section` | `keep` | `select_section` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 76 | function | `apply_config` | `keep` | `apply_config` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 101 | function | `build_dataclass_config` | `keep` | `build_dataclass_config` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/engineering/error_policy.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 20 | function | `_safe_context_store_update` | `keep` | `_safe_context_store_update` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 55 | function | `report_soft_error` | `keep` | `report_soft_error` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/engineering/experiment.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 9 | class | `ExperimentResult` | `keep` | `ExperimentResult` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 12 | method | `ExperimentResult.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 22 | method | `ExperimentResult.set_results` | `keep` | `set_results` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 37 | method | `ExperimentResult.save` | `keep` | `save` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 60 | method | `ExperimentResult.save._to_serializable` | `keep` | `_to_serializable` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 90 | class | `ExperimentTracker` | `keep` | `ExperimentTracker` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 93 | method | `ExperimentTracker.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 97 | method | `ExperimentTracker.log_run` | `keep` | `log_run` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/engineering/file_io.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 9 | function | `atomic_write_text` | `keep` | `atomic_write_text` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 17 | function | `atomic_write_json` | `keep` | `atomic_write_json` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/engineering/logging_config.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 12 | class | `JsonFormatter` | `keep` | `JsonFormatter` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 15 | method | `JsonFormatter.format` | `keep` | `format` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 27 | function | `_ensure_utf8_stream` | `keep` | `_ensure_utf8_stream` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 37 | function | `configure_logging` | `keep` | `configure_logging` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/engineering/schema_version.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 18 | class | `SchemaVersionError` | `keep` | `SchemaVersionError` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 22 | function | `expected_schema_version` | `keep` | `expected_schema_version` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 29 | function | `stamp_schema` | `keep` | `stamp_schema` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 36 | function | `schema_check` | `keep` | `schema_check` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 47 | function | `require_schema` | `keep` | `require_schema` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/evaluation/shape_validation.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 19 | class | `EvaluationShapeError` | `keep` | `EvaluationShapeError` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 24 | function | `validate_individual_evaluation_shape` | `keep` | `validate_individual_evaluation_shape` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 135 | function | `validate_population_evaluation_shape` | `keep` | `validate_population_evaluation_shape` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 274 | function | `validate_plugin_short_circuit_return` | `keep` | `validate_plugin_short_circuit_return` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/extension_contracts.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 20 | class | `ContractError` | `keep` | `ContractError` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 24 | function | `_as_1d_array` | `keep` | `_as_1d_array` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 36 | function | `normalize_candidate` | `keep` | `normalize_candidate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 44 | function | `normalize_candidates` | `keep` | `normalize_candidates` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 58 | function | `stack_population` | `keep` | `stack_population` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 73 | function | `normalize_objectives` | `keep` | `normalize_objectives` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 83 | function | `normalize_violation` | `keep` | `normalize_violation` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 93 | function | `normalize_bias_output` | `keep` | `normalize_bias_output` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 106 | function | `verify_component_contract` | `keep` | `verify_component_contract` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 143 | function | `verify_solver_contracts` | `keep` | `verify_solver_contracts` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 158 | function | `verify_solver_contracts._check` | `keep` | `_check` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/parallel/__init__.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 25 | function | `__getattr__` | `keep` | `__getattr__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |

### `utils/parallel/batch.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 21 | class | `BatchEvaluator` | `keep` | `BatchEvaluator` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 24 | method | `BatchEvaluator.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 43 | method | `BatchEvaluator.evaluate_population` | `keep` | `evaluate_population` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 131 | method | `BatchEvaluator._evaluate_batch_chunk` | `keep` | `_evaluate_batch_chunk` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 151 | method | `BatchEvaluator._parse_batch_result` | `keep` | `_parse_batch_result` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 185 | method | `BatchEvaluator._normalize_objectives` | `keep` | `_normalize_objectives` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 208 | method | `BatchEvaluator._normalize_constraints` | `keep` | `_normalize_constraints` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 223 | method | `BatchEvaluator._evaluate_constraints_batch` | `keep` | `_evaluate_constraints_batch` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 233 | method | `BatchEvaluator._compute_violations` | `keep` | `_compute_violations` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 240 | method | `BatchEvaluator._apply_bias_batch` | `keep` | `_apply_bias_batch` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 281 | method | `BatchEvaluator._evaluate_serial` | `keep` | `_evaluate_serial` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 323 | method | `BatchEvaluator.get_stats` | `keep` | `get_stats` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 327 | method | `BatchEvaluator.reset_stats` | `keep` | `reset_stats` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 337 | function | `create_batch_evaluator` | `keep` | `create_batch_evaluator` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/parallel/evaluator.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 45 | function | `_is_picklable` | `keep` | `_is_picklable` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 53 | function | `_default_context_builder` | `keep` | `_default_context_builder` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 79 | function | `_evaluate_individual_task_static` | `keep` | `_evaluate_individual_task_static` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 138 | function | `_ray_evaluate_individual_task` | `keep` | `_ray_evaluate_individual_task` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 144 | class | `ParallelEvaluator` | `keep` | `ParallelEvaluator` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 147 | method | `ParallelEvaluator.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 191 | method | `ParallelEvaluator._get_default_workers` | `keep` | `_get_default_workers` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 198 | method | `ParallelEvaluator._create_executor` | `keep` | `_create_executor` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 223 | method | `ParallelEvaluator._evaluate_individual_task` | `keep` | `_evaluate_individual_task` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 228 | method | `ParallelEvaluator._precheck_or_fallback` | `keep` | `_precheck_or_fallback` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 262 | method | `ParallelEvaluator.evaluate_population` | `keep` | `evaluate_population` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 403 | method | `ParallelEvaluator._evaluate_with_executor` | `keep` | `_evaluate_with_executor` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 427 | method | `ParallelEvaluator._evaluate_with_ray` | `keep` | `_evaluate_with_ray` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 464 | method | `ParallelEvaluator._evaluate_with_joblib` | `keep` | `_evaluate_with_joblib` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 480 | method | `ParallelEvaluator._retry_evaluation` | `keep` | `_retry_evaluation` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 495 | method | `ParallelEvaluator._evaluate_serial` | `keep` | `_evaluate_serial` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 539 | method | `ParallelEvaluator.get_stats` | `keep` | `get_stats` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 542 | method | `ParallelEvaluator.reset_stats` | `keep` | `reset_stats` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 551 | method | `ParallelEvaluator.estimate_speedup` | `keep` | `estimate_speedup` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 562 | method | `ParallelEvaluator.__enter__` | `keep` | `__enter__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 565 | method | `ParallelEvaluator.__exit__` | `keep` | `__exit__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 571 | function | `create_parallel_evaluator` | `keep` | `create_parallel_evaluator` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 575 | class | `SmartEvaluatorSelector` | `keep` | `SmartEvaluatorSelector` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 579 | method | `SmartEvaluatorSelector.select_evaluator` | `keep` | `select_evaluator` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 616 | method | `SmartEvaluatorSelector._analyze_problem_type` | `keep` | `_analyze_problem_type` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/parallel/integration.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 24 | function | `with_parallel_evaluation` | `keep` | `with_parallel_evaluation` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 31 | class | `with_parallel_evaluation.ParallelizedSolver` | `keep` | `ParallelizedSolver` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 32 | method | `ParallelizedSolver.with_parallel_evaluation.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 79 | method | `ParallelizedSolver.with_parallel_evaluation._ensure_parallel_evaluator` | `keep` | `_ensure_parallel_evaluator` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 126 | method | `ParallelizedSolver.with_parallel_evaluation.evaluate_population` | `keep` | `evaluate_population` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/performance/__init__.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 20 | function | `fast_non_dominated_sort_optimized` | `keep` | `fast_non_dominated_sort_optimized` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/performance/array_utils.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 9 | function | `safe_array_index` | `keep` | `safe_array_index` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 62 | function | `safe_slice_bounds` | `keep` | `safe_slice_bounds` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 92 | function | `safe_array_concat` | `keep` | `safe_array_concat` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 118 | function | `safe_array_reshape` | `keep` | `safe_array_reshape` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 155 | function | `validate_array_bounds` | `keep` | `validate_array_bounds` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 184 | class | `SafeArrayAccess` | `keep` | `SafeArrayAccess` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 190 | method | `SafeArrayAccess.safe_get` | `keep` | `safe_get` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 229 | method | `SafeArrayAccess.safe_slice_1d` | `keep` | `safe_slice_1d` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 253 | method | `SafeArrayAccess.safe_slice_2d` | `keep` | `safe_slice_2d` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 282 | function | `safe_get_element` | `keep` | `safe_get_element` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 287 | function | `safe_get_row` | `keep` | `safe_get_row` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 294 | function | `safe_get_2d_element` | `keep` | `safe_get_2d_element` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/performance/fast_non_dominated_sort.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 17 | class | `FastNonDominatedSort` | `keep` | `FastNonDominatedSort` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 25 | method | `FastNonDominatedSort.sort` | `keep` | `sort` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 90 | method | `FastNonDominatedSort._sort_feasible` | `keep` | `_sort_feasible` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 133 | method | `FastNonDominatedSort._dominates` | `keep` | `_dominates` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 144 | method | `FastNonDominatedSort.calculate_crowding_distance` | `keep` | `calculate_crowding_distance` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 199 | function | `dominates_numba` | `keep` | `dominates_numba` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 211 | function | `fast_non_dominated_sort_numba` | `keep` | `fast_non_dominated_sort_numba` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 258 | function | `fast_non_dominated_sort_optimized` | `keep` | `fast_non_dominated_sort_optimized` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 292 | function | `get_pareto_front_indices` | `keep` | `get_pareto_front_indices` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 298 | function | `count_non_dominated_solutions` | `keep` | `count_non_dominated_solutions` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 304 | function | `is_pareto_optimal` | `keep` | `is_pareto_optimal` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/performance/memory_manager.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 15 | class | `MemoryManager` | `keep` | `MemoryManager` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 21 | method | `MemoryManager.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 41 | method | `MemoryManager.get_memory_usage` | `keep` | `get_memory_usage` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 58 | method | `MemoryManager.check_memory_pressure` | `keep` | `check_memory_pressure` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 73 | method | `MemoryManager.register_cleanup_strategy` | `keep` | `register_cleanup_strategy` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 82 | method | `MemoryManager.cleanup_memory` | `keep` | `cleanup_memory` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 114 | method | `MemoryManager._gc_collect` | `keep` | `_gc_collect` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 118 | method | `MemoryManager._clear_arrays` | `keep` | `_clear_arrays` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 123 | method | `MemoryManager.start_monitoring` | `keep` | `start_monitoring` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 138 | method | `MemoryManager.stop_monitoring` | `keep` | `stop_monitoring` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 144 | method | `MemoryManager._monitor_loop` | `keep` | `_monitor_loop` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 154 | method | `MemoryManager.get_memory_trend` | `keep` | `get_memory_trend` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 183 | class | `SmartArrayCache` | `keep` | `SmartArrayCache` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 188 | method | `SmartArrayCache.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 204 | method | `SmartArrayCache.get` | `keep` | `get` | `high` | `-` | 通用存取方法，参数别名规则不适用。 |
| 221 | method | `SmartArrayCache.put` | `keep` | `put` | `high` | `-` | 通用存取方法，参数别名规则不适用。 |
| 251 | method | `SmartArrayCache._evict_one` | `keep` | `_evict_one` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 276 | method | `SmartArrayCache.clear` | `keep` | `clear` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 284 | method | `SmartArrayCache.get_stats` | `keep` | `get_stats` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 295 | class | `OptimizationMemoryOptimizer` | `keep` | `OptimizationMemoryOptimizer` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 300 | method | `OptimizationMemoryOptimizer.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 312 | method | `OptimizationMemoryOptimizer.optimize_history_storage` | `keep` | `optimize_history_storage` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 339 | method | `OptimizationMemoryOptimizer.optimize_population_storage` | `keep` | `optimize_population_storage` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 371 | method | `OptimizationMemoryOptimizer.clear_temporary_data` | `keep` | `clear_temporary_data` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 380 | method | `OptimizationMemoryOptimizer.auto_optimize` | `keep` | `auto_optimize` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 406 | method | `OptimizationMemoryOptimizer.get_optimization_report` | `keep` | `get_optimization_report` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 419 | method | `OptimizationMemoryOptimizer._get_recommendations` | `keep` | `_get_recommendations` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 441 | function | `get_global_memory_manager` | `keep` | `get_global_memory_manager` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 449 | function | `monitor_and_optimize_memory` | `keep` | `monitor_and_optimize_memory` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 466 | function | `memory_monitoring` | `keep` | `memory_monitoring` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 473 | function | `memory_monitoring.decorator` | `keep` | `decorator` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 474 | function | `memory_monitoring.decorator.wrapper` | `keep` | `wrapper` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/performance/numba_helpers.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 16 | function | `njit` | `keep` | `njit` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 19 | function | `njit.wrapper` | `keep` | `wrapper` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 26 | function | `fast_is_dominated` | `keep` | `fast_is_dominated` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/performance/thread_safety.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 9 | class | `ThreadLocalRNG` | `keep` | `ThreadLocalRNG` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 21 | method | `ThreadLocalRNG.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 25 | method | `ThreadLocalRNG._get_rng` | `keep` | `_get_rng` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 32 | method | `ThreadLocalRNG.__getattr__` | `keep` | `__getattr__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |

### `utils/runs/headless.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 7 | class | `CallableSingleObjectiveProblem` | `keep` | `CallableSingleObjectiveProblem` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 10 | method | `CallableSingleObjectiveProblem.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 16 | method | `CallableSingleObjectiveProblem.evaluate` | `keep` | `evaluate` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 21 | method | `CallableSingleObjectiveProblem.get_num_objectives` | `keep` | `get_num_objectives` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 25 | function | `run_headless_single_objective` | `keep` | `run_headless_single_objective` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 67 | function | `run_headless_single_objective._wrapped` | `keep` | `_wrapped` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/runtime/decision_trace.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 12 | function | `_json_safe` | `keep` | `_json_safe` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 31 | function | `build_decision_event` | `keep` | `build_decision_event` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 64 | function | `append_decision_jsonl` | `keep` | `append_decision_jsonl` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 70 | function | `load_decision_jsonl` | `keep` | `load_decision_jsonl` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 89 | class | `DecisionReplayEngine` | `keep` | `DecisionReplayEngine` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 93 | method | `DecisionReplayEngine.from_jsonl` | `keep` | `from_jsonl` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 96 | method | `DecisionReplayEngine.iter` | `keep` | `iter` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 113 | method | `DecisionReplayEngine.summary` | `keep` | `summary` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 130 | function | `record_decision_event` | `keep` | `record_decision_event` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/runtime/dependencies.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 14 | function | `_get_version` | `keep` | `_get_version` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 23 | function | `check_dependency` | `keep` | `check_dependency` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 45 | function | `dependency_report` | `keep` | `dependency_report` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 55 | function | `ensure_dependencies` | `keep` | `ensure_dependencies` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 80 | function | `summarize_report` | `keep` | `summarize_report` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/runtime/imports.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 12 | class | `ImportManager` | `keep` | `ImportManager` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 18 | method | `ImportManager.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 29 | method | `ImportManager.safe_import` | `keep` | `safe_import` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 72 | method | `ImportManager.check_optional_dependency` | `keep` | `check_optional_dependency` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 90 | method | `ImportManager.get_import_status` | `keep` | `get_import_status` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 121 | function | `safe_import` | `keep` | `safe_import` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 127 | function | `check_optional_dependency` | `keep` | `check_optional_dependency` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 132 | function | `get_import_status` | `keep` | `get_import_status` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 138 | function | `import_numpy` | `keep` | `import_numpy` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 143 | function | `import_matplotlib` | `keep` | `import_matplotlib` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 148 | function | `import_sklearn` | `keep` | `import_sklearn` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 153 | function | `import_numba` | `keep` | `import_numba` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 158 | function | `import_joblib` | `keep` | `import_joblib` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 163 | function | `import_plotly` | `keep` | `import_plotly` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 169 | function | `import_core` | `keep` | `import_core` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 183 | function | `import_bias` | `keep` | `import_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 218 | function | `import_utils` | `keep` | `import_utils` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 230 | class | `ImportWarning` | `keep` | `ImportWarning` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 235 | class | `MissingDependencyError` | `keep` | `MissingDependencyError` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 238 | method | `MissingDependencyError.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 248 | function | `is_jupyter_notebook` | `keep` | `is_jupyter_notebook` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 259 | function | `is_headless` | `keep` | `is_headless` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 270 | function | `get_package_root` | `keep` | `get_package_root` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 275 | function | `add_to_path` | `keep` | `add_to_path` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/runtime/repro_bundle.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 21 | function | `_json_safe` | `keep` | `_json_safe` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 40 | function | `_canonical_json_bytes` | `keep` | `_canonical_json_bytes` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 50 | function | `_sha256_payload` | `keep` | `_sha256_payload` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 54 | function | `_sha256_file` | `keep` | `_sha256_file` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 70 | function | `_now_iso` | `keep` | `_now_iso` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 75 | function | `_run_cmd` | `keep` | `_run_cmd` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 76 | function | `_run_cmd._decode` | `keep` | `_decode` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 115 | function | `_detect_git` | `keep` | `_detect_git` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 137 | function | `_normalize_entry` | `keep` | `_normalize_entry` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 153 | function | `_path_ref` | `keep` | `_path_ref` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 169 | function | `_sanitize_artifacts` | `keep` | `_sanitize_artifacts` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 185 | function | `_load_json_dict` | `keep` | `_load_json_dict` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 195 | function | `_load_jsonl` | `keep` | `_load_jsonl` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 214 | function | `_hash_signature_set` | `keep` | `_hash_signature_set` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 227 | function | `_hash_trie_fingerprint` | `keep` | `_hash_trie_fingerprint` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 251 | function | `_hash_trace_groups` | `keep` | `_hash_trace_groups` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 304 | function | `_digest_decision_trace` | `keep` | `_digest_decision_trace` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 336 | function | `_build_structure_proof` | `keep` | `_build_structure_proof` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 378 | function | `_solver_section` | `keep` | `_solver_section` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 387 | function | `_runtime_view` | `keep` | `_runtime_view` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 410 | function | `_wiring_view` | `keep` | `_wiring_view` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 426 | function | `_environment_view` | `keep` | `_environment_view` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 440 | function | `build_repro_bundle` | `keep` | `build_repro_bundle` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 490 | function | `write_repro_bundle` | `keep` | `write_repro_bundle` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 505 | function | `load_repro_bundle` | `keep` | `load_repro_bundle` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 513 | function | `compare_repro_bundle` | `keep` | `compare_repro_bundle` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 528 | function | `compare_repro_bundle._add` | `keep` | `_add` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 621 | function | `apply_bundle_to_solver` | `keep` | `apply_bundle_to_solver` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 658 | function | `replay_spec` | `keep` | `replay_spec` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/runtime/sequence_graph.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 16 | function | `_clean_token_part` | `keep` | `_clean_token_part` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 23 | function | `build_sequence_token` | `keep` | `build_sequence_token` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 34 | function | `_runtime_ids` | `keep` | `_runtime_ids` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 51 | function | `record_sequence_event` | `keep` | `record_sequence_event` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 69 | class | `SequenceRecord` | `keep` | `SequenceRecord` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 82 | method | `SequenceRecord.to_dict` | `keep` | `to_dict` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 98 | class | `SequenceGraphRecorder` | `keep` | `SequenceGraphRecorder` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 101 | method | `SequenceGraphRecorder.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 160 | method | `SequenceGraphRecorder._matches_any` | `keep` | `_matches_any` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 163 | method | `SequenceGraphRecorder._should_ignore` | `keep` | `_should_ignore` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 168 | method | `SequenceGraphRecorder._is_boundary` | `keep` | `_is_boundary` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 178 | method | `SequenceGraphRecorder._reset_current` | `keep` | `_reset_current` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 190 | method | `SequenceGraphRecorder._ensure_trace_cycle_decision` | `keep` | `_ensure_trace_cycle_decision` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 208 | method | `SequenceGraphRecorder._new_span_id` | `keep` | `_new_span_id` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 213 | method | `SequenceGraphRecorder._append_trace_event` | `keep` | `_append_trace_event` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 219 | method | `SequenceGraphRecorder._trace_event_payload` | `keep` | `_trace_event_payload` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 257 | method | `SequenceGraphRecorder.record_instant_trace` | `keep` | `record_instant_trace` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 291 | method | `SequenceGraphRecorder.start_trace_span` | `keep` | `start_trace_span` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 317 | method | `SequenceGraphRecorder.end_trace_span` | `keep` | `end_trace_span` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 354 | method | `SequenceGraphRecorder._current_signature` | `keep` | `_current_signature` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 358 | method | `SequenceGraphRecorder.record_event` | `keep` | `record_event` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 406 | method | `SequenceGraphRecorder.finalize_cycle` | `keep` | `finalize_cycle` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 441 | method | `SequenceGraphRecorder.snapshot` | `keep` | `snapshot` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/surrogate/manager.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 12 | class | `SurrogateManager` | `keep` | `SurrogateManager` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 15 | method | `SurrogateManager.add_model` | `keep` | `add_model` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 20 | method | `SurrogateManager.train_model` | `keep` | `train_model` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 25 | method | `SurrogateManager.predict_model` | `keep` | `predict_model` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 30 | method | `SurrogateManager.uncertainty` | `keep` | `uncertainty` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/surrogate/strategies.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 9 | class | `UncertaintySampling` | `keep` | `UncertaintySampling` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 12 | method | `UncertaintySampling.select` | `keep` | `select` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 23 | class | `AdaptiveStrategy` | `keep` | `AdaptiveStrategy` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 29 | method | `AdaptiveStrategy.__post_init__` | `keep` | `__post_init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 32 | method | `AdaptiveStrategy.update_strategy` | `keep` | `update_strategy` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/surrogate/trainer.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 13 | class | `SurrogateTrainer` | `keep` | `SurrogateTrainer` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 17 | method | `SurrogateTrainer.__post_init__` | `keep` | `__post_init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 20 | method | `SurrogateTrainer._create_model` | `keep` | `_create_model` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 31 | method | `SurrogateTrainer.train` | `keep` | `train` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 38 | method | `SurrogateTrainer.predict` | `keep` | `predict` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 45 | method | `SurrogateTrainer.predict_uncertainty` | `keep` | `predict_uncertainty` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/surrogate/vector_surrogate.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 12 | class | `VectorSurrogate` | `keep` | `VectorSurrogate` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 24 | method | `VectorSurrogate.__post_init__` | `keep` | `__post_init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 33 | method | `VectorSurrogate.fit` | `keep` | `fit` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 43 | method | `VectorSurrogate.predict` | `keep` | `predict` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 48 | method | `VectorSurrogate.uncertainty` | `keep` | `uncertainty` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/viz/matplotlib.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 14 | function | `_lazy_import_matplotlib` | `keep` | `_lazy_import_matplotlib` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 39 | class | `SolverVisualizationMixin` | `keep` | `SolverVisualizationMixin` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 42 | method | `SolverVisualizationMixin._init_visualization` | `keep` | `_init_visualization` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 66 | method | `SolverVisualizationMixin.setup_ui` | `keep` | `setup_ui` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 126 | method | `SolverVisualizationMixin.toggle_elite_retention` | `keep` | `toggle_elite_retention` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 136 | method | `SolverVisualizationMixin.update_elite_prob` | `keep` | `update_elite_prob` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 140 | method | `SolverVisualizationMixin.toggle_diversity_init` | `keep` | `toggle_diversity_init` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 152 | method | `SolverVisualizationMixin.toggle_history` | `keep` | `toggle_history` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 164 | method | `SolverVisualizationMixin.toggle_plot` | `keep` | `toggle_plot` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 176 | method | `SolverVisualizationMixin.clear_all_plots` | `keep` | `clear_all_plots` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 195 | method | `SolverVisualizationMixin.init_plot_static_elements` | `keep` | `init_plot_static_elements` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 214 | method | `SolverVisualizationMixin.redraw_static_elements` | `keep` | `redraw_static_elements` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 222 | method | `SolverVisualizationMixin.update_plot_dynamic` | `keep` | `update_plot_dynamic` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 230 | method | `SolverVisualizationMixin.update_population_and_pareto_plot` | `keep` | `update_population_and_pareto_plot` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 269 | method | `SolverVisualizationMixin.update_fitness_plot` | `keep` | `update_fitness_plot` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 298 | method | `SolverVisualizationMixin.update_info_text` | `keep` | `update_info_text` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 346 | method | `SolverVisualizationMixin.start_animation` | `keep` | `start_animation` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 359 | method | `SolverVisualizationMixin.stop_animation` | `keep` | `stop_animation` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/viz/ui/catalog_view.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 9 | function | `scope_from_key` | `keep` | `scope_from_key` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 13 | function | `context_role_match` | `keep` | `context_role_match` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 37 | class | `CatalogView` | `keep` | `CatalogView` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 38 | method | `CatalogView.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 44 | method | `CatalogView._build` | `keep` | `_build` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 142 | method | `CatalogView._set_detail_text` | `keep` | `_set_detail_text` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 151 | method | `CatalogView._clear_cards` | `keep` | `_clear_cards` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 165 | method | `CatalogView._select_detail_tab` | `keep` | `_select_detail_tab` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 173 | method | `CatalogView.load_catalog` | `keep` | `load_catalog` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 274 | method | `CatalogView.search` | `keep` | `search` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 368 | method | `CatalogView._default_catalog_file` | `keep` | `_default_catalog_file` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 380 | method | `CatalogView._catalog_file_for_kind` | `keep` | `_catalog_file_for_kind` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 391 | method | `CatalogView._project_catalog_file_for_kind` | `keep` | `_project_catalog_file_for_kind` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 397 | method | `CatalogView._collect_project_catalog_key_map` | `keep` | `_collect_project_catalog_key_map` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 424 | method | `CatalogView.open_register_dialog` | `keep` | `open_register_dialog` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 478 | method | `CatalogView.open_register_dialog._add_row` | `keep` | `_add_row` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 489 | method | `CatalogView.open_register_dialog._refresh_target_mode_hint` | `keep` | `_refresh_target_mode_hint` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 504 | method | `CatalogView.open_register_dialog._set_auto_target` | `keep` | `_set_auto_target` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 515 | method | `CatalogView.open_register_dialog._browse_file` | `keep` | `_browse_file` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 534 | method | `CatalogView.open_register_dialog._browse_source_file` | `keep` | `_browse_source_file` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 565 | method | `CatalogView.open_register_dialog._scan_symbols` | `keep` | `_scan_symbols` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 594 | method | `CatalogView.open_register_dialog._to_values` | `keep` | `_to_values` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 602 | method | `CatalogView.open_register_dialog._infer_key` | `keep` | `_infer_key` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 623 | method | `CatalogView.open_register_dialog._infer_import_path` | `keep` | `_infer_import_path` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 644 | method | `CatalogView.open_register_dialog._load_from_code` | `keep` | `_load_from_code` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 673 | method | `CatalogView.open_register_dialog._refresh_from_code` | `keep` | `_refresh_from_code` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 685 | method | `CatalogView.open_register_dialog._apply_to_code` | `keep` | `_apply_to_code` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 718 | method | `CatalogView.open_register_dialog._retarget_file_for_kind` | `keep` | `_retarget_file_for_kind` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 760 | method | `CatalogView.open_register_dialog._save` | `keep` | `_save` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 938 | method | `CatalogView._lookup_info` | `keep` | `_lookup_info` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 977 | method | `CatalogView.search_context_key` | `keep` | `search_context_key` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1002 | method | `CatalogView.on_select` | `keep` | `on_select` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1035 | method | `CatalogView._project_catalog_file` | `keep` | `_project_catalog_file` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1041 | method | `CatalogView._is_scaffold_project_root` | `keep` | `_is_scaffold_project_root` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1047 | method | `CatalogView._delete_selected_project_entry` | `keep` | `_delete_selected_project_entry` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1113 | method | `CatalogView.key_for_plugin` | `keep` | `key_for_plugin` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1125 | method | `CatalogView.key_for_bias` | `keep` | `key_for_bias` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1137 | method | `CatalogView._format_contracts` | `keep` | `_format_contracts` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1154 | method | `CatalogView._format_usage` | `keep` | `_format_usage` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 1166 | method | `CatalogView._detect_project_root` | `keep` | `_detect_project_root` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/viz/ui/context_view.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 54 | class | `ContextView` | `keep` | `ContextView` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 55 | method | `ContextView.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 80 | method | `ContextView._build` | `keep` | `_build` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 133 | method | `ContextView.request_refresh` | `keep` | `request_refresh` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 136 | method | `ContextView.refresh` | `keep` | `refresh` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 202 | method | `ContextView._reconcile_key_rows` | `keep` | `_reconcile_key_rows` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 216 | method | `ContextView.show_replay_keys` | `keep` | `show_replay_keys` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 227 | method | `ContextView._on_select` | `keep` | `_on_select` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 235 | method | `ContextView._set_selected_key` | `keep` | `_set_selected_key` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 255 | method | `ContextView._open_field_window` | `keep` | `_open_field_window` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 268 | method | `ContextView._build_field_window` | `keep` | `_build_field_window` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 302 | method | `ContextView._make_role_tree` | `keep` | `_make_role_tree` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 315 | method | `ContextView._close_field_window` | `keep` | `_close_field_window` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 326 | method | `ContextView._refresh_field_window` | `keep` | `_refresh_field_window` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 340 | method | `ContextView._focus_field_window_section` | `keep` | `_focus_field_window_section` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 349 | method | `ContextView._field_relation_rows` | `keep` | `_field_relation_rows` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 372 | method | `ContextView._populate_role_tree` | `keep` | `_populate_role_tree` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 380 | method | `ContextView._on_field_component_select` | `keep` | `_on_field_component_select` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 413 | method | `ContextView._catalog_intro_for_component` | `keep` | `_catalog_intro_for_component` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 477 | method | `ContextView._open_selected_component_detail` | `keep` | `_open_selected_component_detail` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 485 | method | `ContextView._collect_declared_io` | `keep` | `_collect_declared_io` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 519 | method | `ContextView._collect_component_contracts` | `keep` | `_collect_component_contracts` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 537 | method | `ContextView._iter_values` | `keep` | `_iter_values` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 544 | method | `ContextView._collect_missing_requires` | `keep` | `_collect_missing_requires` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 555 | method | `ContextView._build_component_name_map` | `keep` | `_build_component_name_map` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 586 | method | `ContextView._collect_runtime_writers` | `keep` | `_collect_runtime_writers` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 623 | method | `ContextView._clone_declared_cache` | `keep` | `_clone_declared_cache` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 631 | method | `ContextView._on_scheduled_refresh` | `keep` | `_on_scheduled_refresh` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 635 | method | `ContextView._cancel_scheduled_refresh` | `keep` | `_cancel_scheduled_refresh` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 643 | method | `ContextView._clear_table` | `keep` | `_clear_table` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 651 | method | `ContextView._set_error` | `keep` | `_set_error` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 660 | method | `ContextView._set_text` | `keep` | `_set_text` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 668 | method | `ContextView._fmt_list` | `keep` | `_fmt_list` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/viz/ui/contrib_view.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 16 | class | `ContributionView` | `keep` | `ContributionView` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 17 | method | `ContributionView.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 24 | method | `ContributionView._build_contrib` | `keep` | `_build_contrib` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 98 | method | `ContributionView._build_traj` | `keep` | `_build_traj` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 117 | method | `ContributionView.add_run_choice` | `keep` | `add_run_choice` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 129 | method | `ContributionView.reload_run_choices` | `keep` | `reload_run_choices` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 147 | method | `ContributionView.refresh_contribution` | `keep` | `refresh_contribution` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 166 | method | `ContributionView._set_contribution_text` | `keep` | `_set_contribution_text` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 172 | method | `ContributionView._set_hash_text` | `keep` | `_set_hash_text` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 178 | method | `ContributionView._set_bias_rows` | `keep` | `_set_bias_rows` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 192 | method | `ContributionView._load_modules_json` | `keep` | `_load_modules_json` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 202 | method | `ContributionView._load_switch_events` | `keep` | `_load_switch_events` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 206 | method | `ContributionView._schema_warning` | `keep` | `_schema_warning` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 212 | method | `ContributionView._load_contribution_report` | `keep` | `_load_contribution_report` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 325 | method | `ContributionView._load_all_contributions` | `keep` | `_load_all_contributions` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 368 | method | `ContributionView._diff_snapshots` | `keep` | `_diff_snapshots` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 389 | method | `ContributionView._diff_snapshots.key_fmt` | `keep` | `key_fmt` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 392 | method | `ContributionView._diff_snapshots.index_by_name` | `keep` | `index_by_name` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 436 | method | `ContributionView._load_snapshot` | `keep` | `_load_snapshot` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 445 | method | `ContributionView._refresh_hash_map` | `keep` | `_refresh_hash_map` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 471 | method | `ContributionView._compute_structure_hash_short` | `keep` | `_compute_structure_hash_short` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 472 | method | `ContributionView._compute_structure_hash_short.sort_items` | `keep` | `sort_items` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 492 | method | `ContributionView._normalize_snapshot` | `keep` | `_normalize_snapshot` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 505 | method | `ContributionView._compute_delta_keys` | `keep` | `_compute_delta_keys` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 508 | method | `ContributionView._compute_delta_keys.index_by_name` | `keep` | `index_by_name` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 552 | method | `ContributionView.compare_runs` | `keep` | `compare_runs` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 580 | method | `ContributionView._set_compare_text` | `keep` | `_set_compare_text` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 586 | method | `ContributionView._on_bias_select` | `keep` | `_on_bias_select` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 603 | method | `ContributionView._set_bias_detail_text` | `keep` | `_set_bias_detail_text` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 609 | method | `ContributionView._format_bias_detail` | `keep` | `_format_bias_detail` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 635 | method | `ContributionView._sparkline` | `keep` | `_sparkline` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 656 | method | `ContributionView._auto_color` | `keep` | `_auto_color` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 663 | method | `ContributionView._hsv_to_rgb` | `keep` | `_hsv_to_rgb` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 687 | method | `ContributionView._draw_switch_trajectory` | `keep` | `_draw_switch_trajectory` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 722 | method | `ContributionView._draw_switch_trajectory.y_for` | `keep` | `y_for` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/viz/ui/decision_view.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 13 | class | `DecisionView` | `keep` | `DecisionView` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 14 | method | `DecisionView.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 21 | method | `DecisionView._build` | `keep` | `_build` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 85 | method | `DecisionView.load_last_run` | `keep` | `load_last_run` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 93 | method | `DecisionView.load_from_history_index` | `keep` | `load_from_history_index` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 103 | method | `DecisionView._trace_path_for_run` | `keep` | `_trace_path_for_run` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 109 | method | `DecisionView.load_from_run` | `keep` | `load_from_run` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 122 | method | `DecisionView.refresh` | `keep` | `refresh` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 128 | method | `DecisionView._rebuild_filters` | `keep` | `_rebuild_filters` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 138 | method | `DecisionView._apply_filter` | `keep` | `_apply_filter` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 159 | method | `DecisionView._render` | `keep` | `_render` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 164 | method | `DecisionView._render._upsert_node` | `keep` | `_upsert_node` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 212 | method | `DecisionView._iter_tree_nodes` | `keep` | `_iter_tree_nodes` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 219 | method | `DecisionView._reconcile_tree` | `keep` | `_reconcile_tree` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 237 | method | `DecisionView._on_select_row` | `keep` | `_on_select_row` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 249 | method | `DecisionView._set_detail` | `keep` | `_set_detail` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/viz/ui/repro_view.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 19 | class | `ReproView` | `keep` | `ReproView` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 20 | method | `ReproView.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 27 | method | `ReproView._build` | `keep` | `_build` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 56 | method | `ReproView._set_detail` | `keep` | `_set_detail` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 62 | method | `ReproView._bundle_path_for_run` | `keep` | `_bundle_path_for_run` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 68 | method | `ReproView.load_last_run` | `keep` | `load_last_run` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 76 | method | `ReproView.load_from_history_index` | `keep` | `load_from_history_index` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 86 | method | `ReproView.load_from_run` | `keep` | `load_from_run` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 107 | method | `ReproView.load_file` | `keep` | `load_file` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 130 | method | `ReproView._render_bundle_summary` | `keep` | `_render_bundle_summary` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 153 | method | `ReproView.compare_current` | `keep` | `compare_current` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 190 | method | `ReproView._load_entry_if_needed` | `keep` | `_load_entry_if_needed` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 205 | method | `ReproView.run_by_bundle` | `keep` | `run_by_bundle` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 241 | method | `ReproView.export_last` | `keep` | `export_last` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/viz/ui/run_view.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 22 | class | `RunView` | `keep` | `RunView` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 23 | method | `RunView.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 28 | method | `RunView._build` | `keep` | `_build` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 60 | method | `RunView.update_sensitivity_button` | `keep` | `update_sensitivity_button` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 66 | method | `RunView.get_plugin` | `keep` | `get_plugin` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 77 | method | `RunView.sync_run_id_plugins` | `keep` | `sync_run_id_plugins` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 93 | method | `RunView._read_best_from_context` | `keep` | `_read_best_from_context` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 108 | method | `RunView._format_best_x` | `keep` | `_format_best_x` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 127 | method | `RunView.snapshot` | `keep` | `snapshot` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 227 | method | `RunView._structure_hash` | `keep` | `_structure_hash` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 228 | method | `RunView._structure_hash.sort_items` | `keep` | `sort_items` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 246 | method | `RunView._mask_redis_url` | `keep` | `_mask_redis_url` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 264 | method | `RunView._context_store_snapshot` | `keep` | `_context_store_snapshot` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 285 | method | `RunView._snapshot_store_snapshot` | `keep` | `_snapshot_store_snapshot` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 301 | method | `RunView._refresh_hash_index` | `keep` | `_refresh_hash_index` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 317 | method | `RunView._parse_seed_override` | `keep` | `_parse_seed_override` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 323 | method | `RunView.on_run` | `keep` | `on_run` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 343 | method | `RunView.on_run._worker` | `keep` | `_worker` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 436 | method | `RunView.on_run._worker._finish` | `keep` | `_finish` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 485 | method | `RunView.on_refresh_ui` | `keep` | `on_refresh_ui` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 498 | method | `RunView.on_sensitivity` | `keep` | `on_sensitivity` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 505 | method | `RunView.on_sensitivity._worker` | `keep` | `_worker` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/viz/ui/sequence_view.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 11 | class | `SequenceView` | `keep` | `SequenceView` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 12 | method | `SequenceView.__init__` | `keep` | `__init__` | `high` | `-` | Python 特殊方法，按语言协议保留。 |
| 24 | method | `SequenceView._build` | `keep` | `_build` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 181 | method | `SequenceView.load_last_run` | `keep` | `load_last_run` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 189 | method | `SequenceView.load_from_history_index` | `keep` | `load_from_history_index` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 199 | method | `SequenceView._sequence_path_for_run` | `keep` | `_sequence_path_for_run` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 205 | method | `SequenceView.load_from_run` | `keep` | `load_from_run` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 228 | method | `SequenceView.refresh` | `keep` | `refresh` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 234 | method | `SequenceView._apply_filter` | `keep` | `_apply_filter` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 256 | method | `SequenceView._filter_trace_rows` | `keep` | `_filter_trace_rows` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 269 | method | `SequenceView._render` | `keep` | `_render` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 295 | method | `SequenceView._build_trie` | `keep` | `_build_trie` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 311 | method | `SequenceView._render_trie` | `keep` | `_render_trie` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 317 | method | `SequenceView._render_trie._insert` | `keep` | `_insert` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 334 | method | `SequenceView._render_trace` | `keep` | `_render_trace` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 360 | method | `SequenceView._build_trace_groups` | `keep` | `_build_trace_groups` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 459 | method | `SequenceView._render_trace_groups` | `keep` | `_render_trace_groups` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 481 | method | `SequenceView._on_select_row` | `keep` | `_on_select_row` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 492 | method | `SequenceView._on_select_trie_node` | `keep` | `_on_select_trie_node` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 512 | method | `SequenceView._on_select_trace_row` | `keep` | `_on_select_trace_row` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 523 | method | `SequenceView._on_select_trace_group` | `keep` | `_on_select_trace_group` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 534 | method | `SequenceView._format_record` | `keep` | `_format_record` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 552 | method | `SequenceView._format_trace_event` | `keep` | `_format_trace_event` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 593 | method | `SequenceView._format_trace_group` | `keep` | `_format_trace_group` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 609 | method | `SequenceView._set_detail` | `keep` | `_set_detail` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 615 | method | `SequenceView._set_trie_detail` | `keep` | `_set_trie_detail` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 621 | method | `SequenceView._set_trace_detail` | `keep` | `_set_trace_detail` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 627 | method | `SequenceView._set_trace_group_detail` | `keep` | `_set_trace_group_detail` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/wiring/__init__.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 16 | function | `set_plugin_strict` | `keep` | `set_plugin_strict` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 27 | function | `set_parallel_thread_bias_isolation` | `keep` | `set_parallel_thread_bias_isolation` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/wiring/benchmark_harness.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 14 | function | `attach_benchmark_harness` | `keep` | `attach_benchmark_harness` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/wiring/checkpoint_resume.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 14 | function | `attach_checkpoint_resume` | `keep` | `attach_checkpoint_resume` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/wiring/default_plugins.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 32 | class | `ObservabilityPreset` | `keep` | `ObservabilityPreset` | `high` | `-` | 类名未命中当前归一化冲突规则。 |
| 88 | function | `resolve_observability_preset` | `keep` | `resolve_observability_preset` | `high` | `-` | 该 resolve_* 属于推断/合并/派生语义，符合规范保留。 |
| 97 | function | `_plugin_exists` | `keep` | `_plugin_exists` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 107 | function | `attach_default_observability_plugins` | `keep` | `attach_default_observability_plugins` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |
| 201 | function | `attach_observability_profile` | `keep` | `attach_observability_profile` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/wiring/dynamic_switch.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 13 | function | `attach_dynamic_switch` | `keep` | `attach_dynamic_switch` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/wiring/module_report.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 14 | function | `attach_module_report` | `keep` | `attach_module_report` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

### `utils/wiring/ray_parallel.py`

| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |
|---:|---|---|---|---|---|---|---|
| 14 | function | `attach_ray_parallel` | `keep` | `attach_ray_parallel` | `high` | `-` | 未命中当前批量改名规则，可暂时保留。 |

