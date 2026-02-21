# COMPONENT_REGISTRATION

本案例使用 `project_registry.py` 注册本地可发现组件。

目标：
- 让 Run Inspector/Catalog 能搜索到案例组件。
- 保持组件使用说明、context 契约、示例入口可读。

新增组件时请至少补齐：
- use_when / minimal_wiring / required_companions / config_keys / example_entry
- context_requires / context_provides / context_mutates / context_cache / context_notes
