# Doctor 的范围、输出与门禁

`joint-repair-contract-invalid` 检查 JointRepairPolicy、ProblemRepair/UnitRepair 的 repair/validate 签名、可选 project_admission 签名，以及 UnitRepair 是否属于具有 algorithm_unit/UnitBinding 的实际叶所有者。还检查 admission_unit_fields 是否为该 Unit 中不重复的字段名。只声明检查，不执行回调；配置 UnitRepair 而未启用共同验收会报错。是否需要部分接纳投影由真实处置决定，缺方法时运行路径拒绝而非猜测。投影在 Adapter disposition 后执行；声明字段不能被二次裁剪，实际内容一致性由运行路径检查。数值/metadata 版本、暂存结构、有限轮协调、零接纳恢复和调度决策回滚须结合行为测试。详见 [共同修复](../architecture/JOINT_REPAIR_CN.md)。

算子声明检查 `unit-operator-contract-invalid` 验证 mutator.unit_inputs 类型、显式 unit 参数，以及声明使用管线变异且已经存在的 Unit 的字段/特征依赖。检查不会执行特征计算，尚未初始化的 Unit 仍在调用时校验。repair 调用次数、动态副作用及复合任务路由须结合行为测试，Doctor 通过不能证明这些性质。

多 Adapter 共享 Pipeline 时，还检查具名 mutation_operators 的声明及各消费者实际选择的算子。错误名称、没有默认项却未选择名称、依赖不匹配、非变异消费者配置选择均报告同一码；未选中的其他算子不会被强制与该消费者的 Unit 匹配。

Doctor 提供源码检查、入口导入检查和可选装配检查。报告中的 `completed` 表示某组检查已经执行完毕，不表示整个项目已经符合所有框架契约；应结合诊断、`coverage` 中的 scope、skipped 原因和启用选项解释结果。

## 日常检查与 CI

```powershell
# 框架仓库：检查主干源码和发现的正式 Project/Case，并显式审计主干 Catalog
python -m nsgablack project doctor --path . --strict --catalog-audit --profile framework-core --format json

# 具体项目：执行装配检查，收集实际组件/资源绑定契约，不执行 run()/fit()
python -m nsgablack project doctor --path examples/cases/algorithm_units --strict --build --format json

# 只提高失败阈值，不启用 strict 专属规则
python -m nsgablack project doctor --path . --fail-on warn --format text

# Catalog 完整口径：包含 example/doc，不能与 framework-core 的结果混用
python -m nsgablack project doctor --path . --strict --catalog-audit --profile default --format json
```

退出码：存在 error 返回 2；没有 error、但启用 `--strict` 或 `--fail-on warn` 且存在 warning 时返回 1；其余返回 0。非 strict 默认是提示模式，warning 不阻断。`--strict` 还会启用部分严格规则或提升规则严重性，不能仅看它是否改变退出码。

## 检查对象与能力边界

BlackBase 统一发现传入的 Project/Case，以及 `cases/`、`examples/cases/` 正式目录树中的 Project/Case。缺少入口的残缺脚手架只要仍有标记或源文件，也应收到诊断。生成输出、缓存、虚拟环境、tests/docs 不作为生产源码扫描目标。

共享的目录、入口签名、trainer 别名等结构规则由 BlackBase 执行一次；nsgablack 增加优化组件契约和管线文档建议。仓库根检查也逐个检查所发现 Case 的 registry、入口和相对组件目录，不再把根目录不是 Case 作为跳过所有子 Case 的理由。

`coverage` 按检查组与路径记录 completed/skipped 和原因。未开启 `--build` 时，装配与依赖实例的运行态检查明确 skipped；未开启 `--catalog-audit` 时，Catalog 审计明确 skipped。completed 不是规则完备率或测试覆盖率。部分静态规则只识别声明、可解析 AST 和局部别名，不进行任意 Python 程序的跨过程类型/控制流证明。

默认检查仍可能导入入口与注册组件；导入会执行模块顶层代码。`--build` 进一步调用 builder，传入 threads=1、workers=1 的资源上下文，完成后调用可用的 build-check 关闭钩子。它不是沙箱，也不保证 builder 自身没有副作用。资源绑定审计由共享 substrate 写入，第三方 Case 需要支持绑定协议，无须自行伪造 audit 字段。

## 诊断位置与呈现格式

`--format text/json/problem` 仅改变呈现，不筛选严重性。JSON 保留完整 diagnostics 和 coverage，适合 CI 保存证据。

诊断通过结构化 `line`、`column` 提供已知源码位置，不再从 message 中正则提取。未知位置在 JSON 中为 null；problem 输出不填造 `1:1`：

```text
C:\project\adapter.py:18:5: error runtime-bypass-write: ...
C:\project\adapter.py:18: error large-object-in-context: ...
C:\project\build_solver.py: error build-entry-instantiate-failed: ...
```

分别表示行列级、行级、文件级诊断。无源码位置的问题应作为文件/项目级注解展示。仓库 `.vscode/tasks.json` 分别匹配这些形式。`[doctor-coverage]` 行用于显示检查范围，不应被识别为源码错误。

大对象 Context 扫描覆盖直接赋值、注解赋值、局部别名及可静态识别的 update/setdefault 调用。Solver 状态检查支持局部别名与重新绑定；step 检查覆盖显式 None 和可识别的隐式返回路径。动态键、反射、自定义容器和跨函数别名仍需运行时契约及测试验证。

源码契约检查会解析静态继承与导入别名，并按 C3 顺序选择继承字段；可识别的重导出和静态 `__all__` 也参与解析。同名 package 优先于旧 module shim。动态工厂、含糊的重新绑定、动态导出与继承环不会被猜测为满足契约。异常规则区分静默回退与局部返回的失败证据，但不能证明调用者一定处理返回错误，也不能证明任意日志语句都覆盖了全部异常路径。

## 如何解释扩大覆盖后的失败

增加扫描对象可能发现过去未检查的违规。应保留原报告和新报告，区分既有代码匹配、误报与本次改动的回归。不要通过重新跳过目录、降级错误或修改无关业务实现，制造“全仓通过”。Doctor 通过也不能代替单点/批量评估、恢复、嵌套执行和资源后端的行为测试。

## Project/Case 扩展 Context 键

在 Project 根或 Case 根创建 context_keys.json，内容为字符串数组，例如 `["project.score", "metrics.project_score"]`。Doctor 与标准 builder/run_case 都读取它；Case 声明不会泄漏到另一 Case。metrics.* 也需要声明，不能用命名空间绕过检查。错误 JSON 产生 context-registry-invalid。

Catalog 静态审计未执行的 import/params 检查以 null 和 unchecked 计数报告；runtime 导入成功和构造签名匹配仍不代表完整组件行为正确。运行配方的行为证据见 tests/test_catalog_recipes_behavior.py。
