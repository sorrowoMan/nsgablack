# phi_bundle_image_search（图像 Phi Bundle 搜索）

`phi_bundle_image_search` 验证 nsgablack 对图像 objectification formula bundles 的搜索能力，并由 mlblack 图像特征代理进行评估。

## 这个 case 验证什么

- nsgablack 搜索 typed bundle genome，而不是每个特征一个连续标量。
- Outer individual 是 `PhiBundle = {phi_lane_1, phi_lane_2, ...}`，用于生成 feature/object matrix。
- mlblack 通过 image-classification proxy 和 orthogonal source governance 评估解码后的 bundle。
- 搜索目标是在提升分类质量的同时，惩罚 redundant、complex、unstable 或 expensive 的 feature bundles。

## 是否使用 mlblack

使用。Inner evaluation path 通过 `evaluate_phi_bundle` 和 `PhiBundleEvaluationConfig` 调用 mlblack-side image objectification surface。

## nsgablack 侧能力

- 对 typed lane-family toggles 和 lane fields 做 outer solver 搜索。
- 质量、冗余、复杂度、不稳定性、成本的 multi-objective objective vector。
- 使用 `build_solver.py` / `run_solver.py` 标准 case scaffold 入口。

## mlblack 侧能力

- Image-feature/objectification evaluation proxy。
- 由选中 phi lanes 生成 representation objects。
- Orthogonal source governance。
- Logistic-head classification metrics。

## Outer genome

`family toggles -> typed lane fields -> representation/source budget fields`

Lane families 包括：

| Family | 含义 |
|---|---|
| `edge` | 方向、local/global scope 和 edge operator。 |
| `patch_pool` | Patch size、stride、pooling operator 和 spatial region。 |
| `patch_texture` | Patch size、stride、texture operator 和 spatial region。 |
| `orthogonal_frequency` | DCT frequency band 和 orientation。 |
| `moment` | Row/column axis 与 center/variance statistic。 |
| `region` | Center、outer ring 或 full-image region。 |
| `symmetry` | Left-right、top-bottom 或 all symmetry signal。 |
| `row_projection` / `col_projection` | Spatial band projection。 |
| `mass` | Mass/intensity summary lane。 |

## 目标和指标（Objectives / Metrics）

| 目标 | 含义 |
|---|---|
| `classification_error` | 解码 bundle 的主要图像分类误差。 |
| `redundancy` | 重复或高度重叠 feature lanes 的惩罚。 |
| `complexity` | 选中 formula bundle 的结构成本。 |
| `instability` | Bundle 在不同评估条件下的敏感性/方差。 |
| `cost` | Runtime 或 evaluation cost proxy。 |

## 结构（Structure）

| 路径 | 作用 |
|---|---|
| `build_solver.py` | 标准 assembly entry。 |
| `run_solver.py` | CLI entry。 |
| `problem/outer_problem.py` | 解码 typed bundle genomes，并调用 mlblack evaluation proxy。 |
| `pipeline/` | Outer bundle genome 的 representation pipeline。 |
| `adapter/` | Outer search configuration。 |
| `solver/` | Solver defaults 和 assembly helpers。 |

## 运行

```powershell
python examples\cases\phi_bundle_image_search\run_solver.py --check
python examples\cases\phi_bundle_image_search\run_solver.py --suite-id digits_phi_outer_v1
```

## 预期信号（Expected signal）

有效运行应该降低 `classification_error`，同时防止搜索通过堆叠 redundant、unstable 或过高成本的 feature lanes 来“作弊”。
