# START_HERE

## 1) 这个 case 验证什么

`phi_bundle_image_search` 验证 nsgablack 对 typed image-feature formula bundles 的搜索能力。

- nsgablack 搜索 family toggles、typed lane fields 和 source-budget fields。
- mlblack 通过 image objectification/classification proxy 评估解码后的 bundles。
- Objectives 平衡 classification error、redundancy、complexity、instability 和 cost。

Lane families、结构、指标和预期信号见 `README.md`。

## 2) 验证 assembly

```powershell
python examples\cases\phi_bundle_image_search\run_solver.py --check
```

## 3) 运行

```powershell
python examples\cases\phi_bundle_image_search\run_solver.py --suite-id digits_phi_outer_v1
```

## 4) 关键指标

| 目标 | 含义 |
|---|---|
| `classification_error` | 主要图像分类误差。 |
| `redundancy` | 重复/重叠 feature-lane 惩罚。 |
| `complexity` | Bundle 结构成本。 |
| `instability` | 选中 bundle 的敏感性。 |
| `cost` | Runtime/evaluation cost proxy。 |

## 5) 预期信号

有效运行应该发现能提升分类表现的 feature bundles，同时避免 redundant、unstable 或过高成本。
