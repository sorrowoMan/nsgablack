# Case B（TSP）- Pipeline 逐行批注

参考实现：`my_project/pipeline/tsp_pipeline.py`

```python
from nsgablack.representation import (  # 从框架导入排列表示组件
    RepresentationPipeline,  # 管线容器
    PermutationInitializer,  # 排列初始化器
    PermutationSwapMutation,  # 交换变异
    PermutationFixRepair,  # 排列修复器
)


def build_tsp_pipeline() -> RepresentationPipeline:  # TSP 管线装配函数
    return RepresentationPipeline(  # 返回标准管线对象
        initializer=PermutationInitializer(),  # 生成初始排列
        mutator=PermutationSwapMutation(),  # 交换两个位置做邻域搜索
        repair=PermutationFixRepair(),  # 修复重复/缺失元素，保证排列合法
        encoder=None,  # 当前不需要额外编码映射
    )
```

## 重点
- `PermutationFixRepair` 是 TSP 可行性的核心保障。
- 交换变异比高斯变异更符合排列空间语义。
