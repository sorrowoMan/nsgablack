# Adapter 决策与 Unit 成员维护

最后按代码核对：2026-10-12。实现属于 nsgablack 优化结构层；共享事务、生命周期和 Project/L0 编排继续使用 BlackBase。

## 一个用户真正需要写多少

已有算法使用默认 Unit，无需自定义。增加成员字段时，继承基础 Unit、声明字段、实现一个维护钩子，再用已有 builder/codec 绑定。Adapter 保留提出候选、选择算子、接受/拒绝、选择成员和推进阶段等搜索决策。

例如成员年龄 `age`：初始为 0；一次环境选择中旧成员被保留则加 1；新提案加入则为 0。旧种群 `[A, B, C]` 的年龄 `[10, 4, 7]`，加入 D 后 Adapter 选择 `[C, D, A]`，Unit 得到 `[8, 0, 11]`。

以下实现已进入标准 Case 模板的 `pipeline/population_example.py`，可以复制到自己的 Case。它不自动替换默认组件；由 `build_solver.py` 显式选择。

```python
from dataclasses import dataclass, field
import numpy as np
from nsgablack.units import PopulationUnit, UnitSchema, UnitBinding
from nsgablack.representation import PopulationUnitBuilder
from nsgablack.adapters import NSGA2Adapter

@dataclass
class AgePopulationUnit(PopulationUnit):
    age: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=int))
    member_fields = ("age",)
    schema = UnitSchema("case.age_population", required_fields=(
        *PopulationUnit.schema.required_fields, "age"), candidate_projection=False)

    def on_members_changed(self, change):
        increment = int(change.operation == "selection")
        return {"age": np.asarray([
            0 if i is None else self.age[i] + increment
            for i in change.previous_member_indices
        ], dtype=int)}

class AgePopulationBuilder(PopulationUnitBuilder):
    unit_type = AgePopulationUnit
    compatible_schemas = (PopulationUnit.schema,)

# 在标准 Case 的 build_solver 中选择；其余 Project/L0 装配保持原入口。
adapter = NSGA2Adapter(unit_binding=UnitBinding(AgePopulationBuilder()))
```

该例的 age 是“连续存活的环境选择次数”，不声称是所有算法的逻辑代计数。DE/MOEA/D 一轮可做多次局部替换；替换仅使新成员年龄归零，不增加其他成员年龄。若需要运行级代龄，应另行定义提交语义。步骤失败通过现有参与者事务恢复 age，不留下失败尝试的增长。

## 基础结构操作

- `initialize_population(X, F=None, V=None, candidate_tokens=...)`：初始化或显式安装一份新种群，所有行均为新成员。允许候选准备态没有反馈，F/V 必须成对。
- `apply_selection(indices, incoming_X, incoming_F, incoming_V, candidate_tokens=...)`：Adapter 的索引指向 `[旧成员, 新提案]`；Unit 统一合并和筛选 X/F/V/token。
- `replace_evaluated_rows(indices, X, F, V, candidate_tokens=...)`：Adapter 已决定替换的槽位。重复槽位按输入顺序覆盖，最终来源映射指向最后写入的行。MOEA/D 可将一个提案放入多个槽位。
- `clear_population()`：显式清空基础成员与扩展成员字段。
- `attach_feedback(F, V)`：为当前候选附加完整反馈，不构成成员选择，不调用成员维护钩子。

NSGA-II 的选择路径已经改为：

```python
merged_f = np.vstack([unit.objectives, incoming_f])
merged_v = np.concatenate([unit.violations, incoming_v])
keep = adapter._environmental_select(merged_f, merged_v, population_size)
unit.apply_selection(keep, incoming_x, incoming_f, incoming_v,
                     candidate_tokens=incoming_tokens)
```

NSGA-III 和 SPEA2 继承此路径，保留各自选择策略。DE/MOEA/D 的局部替换复用同一维护入口；初始化和人口 Snapshot 写入也接入结构操作。Unit 不评价 Problem，不应用 Bias，不重做接纳决策。

## 来源映射与维护钩子

`PopulationChange` 是不可变的调用局部值，包含 operation、previous_count、incoming_count，以及两个等长的最终行映射。每一行恰有一个来源：

```text
最终成员：                    C     D     A
previous_member_indices：     2     None  0
incoming_member_indices：     None  0     None
```

来源由 Adapter 的明确索引与结构操作产生，不按候选数值或 token 相等推断。token 仍是 CandidateBatch 的身份协议；来源索引表达成员操作，二者不互相替代。该值不是 ProposalRepair 或 BatchDisposition，也不进入 ContextStore/checkpoint。

`member_fields` 声明自定义的行对齐数据字段。`on_members_changed(change)` 只读原 Unit，返回额外 dataclass 字段的值更新；每个声明的 member field 都必须返回。基类字段与 Unit ID 不能由这个回调改写。Unit 使用封闭数据 codec 脱离返回值，合并到草稿后调用完整 `validate()`；成员字段须与新行数一致，领域可进一步扩展 validator。全部通过才发布字段并清理派生缓存。

钩子不得直接写 self、执行求值、访问 Provider/session、决定保留成员或引入全局授权。声明检查不是 Python 副作用沙箱。原 Unit 的任意直接写入、自定义 validator 的副作用和未声明字段之间的数学依赖仍由组件作者负责。无效输入、合法只读钩子抛错、非法字段、错误形状或活对象返回均不会发布局部更新。

## 构建、恢复、组合与范围

初始化通过 builder 创建空 Unit，成员操作填入行与扩展值；声明字段复用已有 dataclass codec。checkpoint 和步骤回滚恢复实际 Unit 数据，不重放成员维护钩子。schema/binding 仍精确匹配，不因“都继承 PopulationUnit”自动转换持久状态。本次基础 population schema 未增加持久字段；自定义 age schema 单独声明。

Snapshot setter 对已声明为当前行投影的未变矩阵仅刷新反馈，不重复增长年龄；安装另一份矩阵作为新种群初始化。这个旧式 X/F/V setter 本身没有完整身份输入，不能用它表达“同数值的新身份”。需要此语义时使用明确 token/source 的结构操作；不按数值相等恢复新成员身份。

同类型多个 Adapter 各有自己的 Unit。组合器继续按原 owner 路径路由 ProposalRepair、BatchDisposition 和事务；本次没有增加共享可写 context 状态、组合调度者或资源授权者。嵌套事务测试验证自定义成员字段随原所有者回滚。

轨迹、图节点和区域没有被强制套用种群成员接口：它们的变动不一定是行选择。已有候选反馈版本和 UnitRepair 对账继续生效。此次闭合的是种群家族的成员维护边界，不能据此宣称所有 Adapter 内部更新都已迁移到结构操作。

## 验证入口

组合职责与坐标清单见 [Unit 契约职责与组合验收](UNIT_CONTRACT_MAP_CN.md)。成员维护沿用 Adapter 的步骤事务，不单独登记 Unit 或成员钩子为参与者。正常零接纳恢复成员及修复效果，并由 disposition 清空本次 pending；异常回滚才恢复整个步骤前的 Adapter 状态。

部分接纳后，`PopulationChange.incoming_member_indices` 是本次成员操作输入的局部索引，不能直接索引原 ProposalRepair 或 BatchDisposition。环境选择与 repair 草稿是不同操作；不得为了修复而借用一次环境选择、无意增长 age 等历史字段。

`tests/test_population_member_operations.py` 覆盖实际 NSGA-II/III/SPEA2 选择、五种种群 Adapter 的完整运行和恢复、相同数值不同身份、重复槽位来源、空选择、钩子失败、嵌套回滚和 Snapshot 刷新。

`tests/test_unit_member_composition.py` 在真实控制路径验证共同修复、非连续部分接纳、成员字段和权威发布，并覆盖更新后失败、零接纳、正式 checkpoint 恢复、同类型多实例与 Provider slot 提交/释放。具体范围和测试替身限制见上面的职责清单。

Doctor 的现有 `adapter-unit-binding-invalid` 检查同时检查 member_fields 和钩子签名，不执行钩子，不能证明字段维护的算法正确性。运行证据见 `artifacts/audit/unit-member-operations-20261012/`。
