# 难题案例 B：TSP 路径问题（逐行版）

目标：
- 染色体是排列（每个城市出现一次）
- 优化目标是路径总长度最短
- 可行性靠 repair 保证

---

## 1) Problem（路径长度）
```python
class TSPProblem(BlackBoxProblem):  # TSP 问题
    def __init__(self, distance_matrix):  # 初始化
        self.distance_matrix = np.asarray(distance_matrix, dtype=float)  # 距离矩阵
        n = self.distance_matrix.shape[0]  # 城市个数
        bounds = {f"x{i}": [0, n - 1] for i in range(n)}  # 索引边界
        super().__init__(name="TSP", dimension=n, bounds=bounds, objectives=["distance"])  # 注册元信息

    def evaluate(self, x):  # 目标函数
        route = np.asarray(x, dtype=int).reshape(-1)  # 路径排列
        n = route.size  # 长度
        total = 0.0  # 总距离
        for i in range(n):  # 按边累加
            a = route[i]  # 当前城市
            b = route[(i + 1) % n]  # 下一城市（闭环）
            total += float(self.distance_matrix[a, b])  # 加边长
        return np.array([total], dtype=float)  # 单目标返回
```

## 2) Repair（排列合法化）
```python
class PermutationRepair(RepresentationComponentContract):  # 排列修复器
    def repair(self, x, context=None):  # 修复
        _ = context  # 当前不用 context
        arr = np.asarray(x, dtype=int).copy()  # 复制
        n = arr.size  # 城市数
        seen = set()  # 已出现城市
        missing = [i for i in range(n) if i not in arr]  # 缺失城市列表
        miss_idx = 0  # 缺失索引指针
        for i, v in enumerate(arr):  # 扫描每个位置
            if v in seen or v < 0 or v >= n:  # 重复或越界
                arr[i] = missing[miss_idx]  # 用缺失城市填充
                miss_idx += 1  # 指针后移
            else:  # 合法元素
                seen.add(int(v))  # 记录出现
        return arr  # 返回合法排列
```

## 3) Bias（结构偏好示例）
```python
class EdgeDiversityBias(Bias):  # 边多样性偏好
    name = "edge_diversity"  # 偏置名

    def compute(self, x, context=None):  # 偏置计算
        _ = context  # 当前不用 context
        route = np.asarray(x, dtype=int).reshape(-1)  # 路径
        edge_set = {(int(route[i]), int(route[(i + 1) % route.size])) for i in range(route.size)}  # 边集合
        return -float(len(edge_set))  # 示例：边越丰富越鼓励（负值）
```

结论：TSP 的“合法性”主要在 repair，bias 只是辅助偏好。
