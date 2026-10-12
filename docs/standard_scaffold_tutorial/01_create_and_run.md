# 01. 创建并运行第一个 Project

下面生成可直接运行的优化 Case：二维平方和问题、候选管线、NSGA2 和两次逻辑提交。

```powershell
python -m nsgablack project new my_project
cd my_project
python -m nsgablack project add-case search --type solver --framework nsgablack
python run_project.py --check --build-check
python -m nsgablack project doctor --path . --build --strict --format json
python run_project.py
```

add-case 自动登记 Project stage。检查输出展示实际组件和有效资源上下文。接着逐步替换：

1. cases/search/problem/__init__.py 的 build_problem()：自己的问题。
2. cases/search/pipeline/main.py：所需 init/mutate/repair 等操作。
3. cases/search/build_solver.py：选择 Adapter，挂载 Bias/Plugin，设置步数。
4. project_config.py：串行、并行、多 Case 编排和资源需求。

复用内置组件，直接在现有 build_solver 中导入装配：

```python
from nsgablack.adapters import NSGA2Adapter
# 放在 solver 创建之后、return 之前
solver.set_adapter(NSGA2Adapter(population_size=16, offspring_size=16))
```

add-component 创建的是**待实现的自定义组件骨架**，名字不会触发内置组件选择。要写新算法才执行：

```powershell
python -m nsgablack project add-component --case search --kind adapter --name my_search
```

然后按第 09 章实现接口并挂载。将骨架命名为 nsga2_adapter 不等于装配了 NSGA2。

ML Trainer 使用 `--type trainer --framework mlblack`，ML 语义属于 mlblack，目录与资源授权仍走相同 Project/Case 入口。Catalog 用 framework-core 查主干、default 查完整示例；模板片段须填写依赖，标为已验证的配方才代表完成执行验收。
