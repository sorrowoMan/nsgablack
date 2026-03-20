# START HERE

如果你第一次接触 NSGABlack，建议按这个顺序开始。

---

## 1) 先跑通最小闭环

```powershell
python -m nsgablack project init my_project
cd my_project
python -m nsgablack project doctor --path . --build --strict
python build_solver.py
```

目标是确认：  
能成功组装 solver、能完成一次运行、能产出输出。

---

## 2) 明确四层边界

- Solver：调度与控制平面  
- Adapter：搜索策略  
- Representation：可行解管线  
- Plugin：工程能力  

如果你要改主干逻辑，先确认不会破坏四层职责边界。

---

## 3) 推荐阅读顺序

1. `QUICKSTART.md`
2. `WORKFLOW_END_TO_END.md`
3. `docs/architecture/README.md`
4. `docs/user_guide/RUN_INSPECTOR.md`

