# START_HERE

1) 运行：

```powershell
python working_nested_optimizer.py --parallel --parallel-backend thread --parallel-workers 8
```

2) 校验输入路径日志：
- `[data] bom=...`
- `[data] supply=...`

3) 查看导出：
- `adjusted_supply_<run_id>.xlsx`
- `adjusted_supply_moves_<run_id>.csv`

4) 在 Run Inspector 中使用入口：
- `build_solver.py:build_solver`
