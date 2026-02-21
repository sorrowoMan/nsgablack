# adapter

策略层（propose/update 搜索逻辑）。  
Strategy layer for propose/update search logic.

## 说明 / Notes
- 多数项目可先不写自定义 adapter。
- 当默认 solver 循环不足时再新增 adapter。
- Typical projects can start without custom adapters.
- Add adapter only when default solver loop is not enough.

## 推荐 context 声明 / Recommended context declaration
- `context_requires`: required fields
- `context_provides`: produced fields
- `context_mutates`: overwritten fields
- `context_cache`: non-replayable cache fields
