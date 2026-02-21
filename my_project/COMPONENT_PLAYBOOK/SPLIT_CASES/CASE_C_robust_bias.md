# Case C（稳健优化）- Bias 逐行批注

目标：在“平均效果”之外，引入风险偏好。

```python
class RobustnessPenaltyBias(Bias):  # 稳健惩罚偏置
    name = "robustness_penalty"  # 名称

    context_requires = ()  # 不强依赖主字段
    context_provides = ()  # 不提供字段
    context_mutates = ()  # 不修改字段
    context_cache = ()  # 不缓存
    context_notes = ("Penalize high uncertainty from MC/surrogate metrics.",)  # 说明

    requires_metrics = ("metrics.mc_std", "metrics.surrogate_std")  # 依赖两个不确定性指标
    metrics_fallback = "neutral"  # 缺指标时不惩罚

    def __init__(self, w_mc: float = 0.8, w_sur: float = 0.4):  # 参数
        super().__init__()  # 父类初始化
        self.w_mc = float(w_mc)  # MC 方差权重
        self.w_sur = float(w_sur)  # surrogate 方差权重

    def compute(self, x, context=None):  # 评分函数
        _ = x  # 该偏置不直接使用 x
        metrics = (context or {}).get("metrics", {})  # 读取 metrics 容器
        mc_std = float(metrics.get("mc_std", 0.0))  # 蒙卡标准差
        sur_std = float(metrics.get("surrogate_std", 0.0))  # 代理标准差
        return self.w_mc * mc_std + self.w_sur * sur_std  # 越不确定惩罚越大
```

## 重点
- 这类 bias 是“信号融合器”，把多个不确定性指标统一成一个可优化信号。
- 它不负责采样，不负责训练 surrogate，只负责“偏好表达”。
