# Catalog 最小装配配方

五个独立标准 Case：CompositeAdapter、RoleAdapter、MultiRoleControllerAdapter、AStarAdapter、MOAStarAdapter。
每个 builder 给出所需子 Adapter 或 neighbors 函数；Problem 和 Pipeline 使用可运行起步组件。
图搜索的最小数值邻居只用于接口演示，实际路径规划需要领域 neighbors、目标判定与代价。

运行 `python run_project.py --check --build-check` 检查实际组件；`python run_project.py` 执行所有 Case。
这些配方也由 tests/test_catalog_recipes_behavior.py 验证，数值默认值不代表具体任务的推荐配置。
