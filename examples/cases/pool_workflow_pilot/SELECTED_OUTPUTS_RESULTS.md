# 一次choose交付主Pool与命名副Pool：正式运行

Project run：`20261020T151028Z-0bc1637e3c`。

- 标准ga_partition Case、正式Project partition分组，L0为1 thread / 1 worker。
- 3次提交，预算260，实际求值100+80+80=260；具名输出不额外求值。
- selector一次返回members和elite/reserve映射；本Case没有pool_maintenance绑定。
- 首轮输入100→members100、elite20、空reserve；后两轮输入180→members100、elite20、reserve80。
- elite明确取自最终members；reserve只取未选位置。精确引用与原offered位置逐项一致。
- 第一轮只初始化；第二、三轮分别从上一提交的20个elite有放回抽父代，生成80个新身份的孩子。
- 已逐个核对160个孩子的change_source_refs/change_input_refs与已发布provenance，来源都是上一提交elite。
- MixedPoolParentSelector的pool_fraction=1.0，PoolTask声明change_sources=('elite',)；读父代额外求值为0。
- elite预先存在并精确替换；reserve首次缺失，即使为空也正式创建，后续保留同一池身份。
- 选择只声明结果，由既有PoolEdit/Authority事务发布；主成员由PopulationUnit应用。
- 本例明确按raw可行性、违反量、目标和挑20，不宣称等价于默认NSGA-II Pareto选择。
- 提交后只读观察重算确定性分区，不调用Problem、不消耗RNG、不写池或Unit。

完整证据：results/ga_partition_selection_outputs.json、results/selection_outputs_summary.json。
原PARTITION_RESULTS.md保留历史分区结果；默认三Case结果不覆盖。
