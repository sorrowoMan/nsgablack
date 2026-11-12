# 生产源文件发布 Case

先使用原 loader 核对 BOM／到料文件，再将原字节发布为 `bom` 和 `supply` Artifact。
不更改第 0 天库存，不移动到料，不执行模型评分。Project 在本 Case 成功 seal 后，
通过正式 `input_artifacts` 将两份发布收据交给外层供应 Case，再交给内层 Worker。

组件覆盖接受 `bom`、`supply`、`machines`、`materials`、`days`、`production_case_dir`；
省略文件路径时使用原生产 Case 的数据定位规则。跨机器的 Worker 不使用这些协调端路径，
只消费已发布 Artifact 的字节。代码由目标预部署，并以任务的 Python 源码清单复核。
