# 数据源接进正式 Case：读取、验证、切分、装配分开

本书没有连接Hive/JDBC/S3，没有读外部数据、安装依赖或运行训练。代码主例默认本地内存行；远程分支必须由使用者显式选择并授权连接。三种Source的两组Catalog key是同类入口别名，不需要各装两份。

## source.case

**什么时候用：** 将确定的数值特征/目标表读成NumericDataView，再走现有ML Problem/Codec/Trainer。Source负责读取，不拥有算法Unit、Project租约或训练循环。RowDatasetStream用于已物化行的有限分批，不是无限网络流或可恢复数据游标。

**先准备什么：** 完整复制 `mlblack/examples/cases/catalog_codec_demo/`，保留default组、linear_point Case与CPU L0。默认依赖三仓/NumPy。需要Hive时另有本地pyhive及认证依赖；JDBC需本地JayDeBeApi、JVM与匹配driver jar；S3需pyarrow/s3fs与可访问对象。远程数据必须有唯一数值列x1/x2/target，SQL由自己维护的只读表提供；SQL字符串不会被组件自动校验或改写。

**放在哪：** 替换 Case config.py、pipeline/main.py、build_solver.py。pipeline包仍导出build_pipeline。保存《ML_CLASSICAL_ESTIMATOR_APPLICATIONS_CN.md》classical.estimator.run完整报告入口。Source实际读取在build_pipeline，因此**build-check也会调用数据读取**；默认local没有外部连接。

**接入步骤：** 以下先保存完整数据工厂，下一节保存薄builder和远程变体。凭据只从运行环境读取，不写Catalog/TOML、共享context或报告。

```python
# cases/linear_point/config.py
SOURCE = "local"  # local / hive / jdbc / s3
```

```python
# cases/linear_point/pipeline/main.py
import os
from pathlib import Path
import numpy as np
from mlblack.pipeline.data_views import NumericDataView
from mlblack.pipeline.datasets import RowDatasetStream, DatasetStreamConfig
from mlblack.pipeline.sources import HiveQuerySource, JDBCQuerySource, S3ParquetSource
from ..config import SOURCE

def required(name):
    value = os.environ.get(name, "")
    if not value:
        raise ValueError("required source configuration: "+name)
    return value

def local_rows():
    rows = [{"x1": float(i)/10., "x2": (-1.)**i,
             "target": 1.+float(i)/5.-.5*((-1.)**i)} for i in range(20)]
    stream = RowDatasetStream(rows, DatasetStreamConfig(batch_size=6, shuffle=False,
                                                       drop_last=False, repeat=1))
    seen, flattened = [], []
    for batch in stream.iter_batches():
        seen.extend(batch.indices)
        flattened.extend(batch.rows)
    if seen != list(range(20)):
        raise ValueError("stream coverage/order changed")
    return NumericDataView(X_train=np.array([[r["x1"], r["x2"]] for r in flattened]),
        y_train=np.array([r["target"] for r in flattened]),
        feature_names=("x1", "x2"), target_name="target",
        metadata={"source": "local_rows", "stream": stream.describe()})

def read_source():
    if SOURCE == "local":
        return local_rows()
    if os.environ.get("CATALOG_CONNECT_SOURCE") != "1":
        raise RuntimeError("remote source disabled; explicitly authorize this run first")
    query = "SELECT x1, x2, target FROM catalog_training_view"
    if SOURCE == "hive":
        source = HiveQuerySource(host=required("HIVE_HOST"),
            port=int(os.environ.get("HIVE_PORT", "10000")),
            database=required("HIVE_DATABASE"), query=query,
            auth=required("HIVE_AUTH"), username=required("HIVE_USERNAME"),
            password=os.environ.get("HIVE_PASSWORD", ""), target_column="target")
    elif SOURCE == "jdbc":
        jar = Path(required("JDBC_DRIVER_JAR")).expanduser().resolve()
        if not jar.is_file():
            raise FileNotFoundError(jar)
        source = JDBCQuerySource(jdbc_url=required("JDBC_URL"),
            driver_class=required("JDBC_DRIVER_CLASS"), driver_jar=str(jar),
            query=query, username=required("JDBC_USERNAME"),
            password=required("JDBC_PASSWORD"), target_column="target")
    elif SOURCE == "s3":
        source = S3ParquetSource(bucket=required("S3_BUCKET"), prefix=required("S3_PREFIX"),
            endpoint_url=os.environ.get("S3_ENDPOINT_URL", ""),
            access_key=required("S3_ACCESS_KEY_ID"), secret_key=required("S3_SECRET_ACCESS_KEY"),
            region=os.environ.get("S3_REGION", ""), target_column="target")
    else:
        raise ValueError("unknown source")
    return source.transform(None)

def build_pipeline():
    raw = read_source()
    names = tuple(raw.effective_feature_names)
    if len(names) != 2 or set(names) != {"x1", "x2"} or raw.target_name != "target":
        raise ValueError("expected exactly x1/x2 features and a separate target column")
    order = [names.index("x1"), names.index("x2")]
    X, y = np.asarray(raw.X_train)[:, order], np.asarray(raw.y_train)
    if len(X) < 10 or not np.all(np.isfinite(X)) or not np.all(np.isfinite(y)):
        raise ValueError("at least ten finite numeric rows required")
    split = int(.8*len(X))
    return NumericDataView(X_train=X[:split], y_train=y[:split],
        X_valid=X[split:], y_valid=y[split:], feature_names=("x1", "x2"),
        target_name="target", metadata={"source_kind": SOURCE, "ordered_tail_split": True})
```

Source的fit返回空摘要；这里直接transform读取一次，不再把Source放进预测时DataPipeline.transform而重新查库。Source不会替调用者切分、规范化、检查泄漏或管理事务隔离。Hive/JDBC fetchall、S3合并整个Parquet表，RowDatasetStream也先把所有行转tuple；batch_size6只影响本地迭代，不限制远程读取内存。默认local批次为6/6/6/2，之后只取一次全集再切16训练/4验证；没有偷偷把数据重复训练repeat次。

Hive/JDBC默认target为空会取最后列；目标名写错时可能退取最后列却保留原特征，导致目标泄漏，因此本例显式target并核对字段集合。S3按bucket/prefix下`*.parquet`列举排序，并非递归遍历所有深层子目录；列出文件顺序不保证行的业务时间序。三种Source的timeout字段当前没有传到底层客户端，不提供超时保证；Project L0也不会自动变成数据库查询配额或远程凭据授权。

## source.case.wiring

继续同一主例。完整build_solver.py：

```python
from mlblack.presets import build_orthogonal_linear_point_trainer
from .pipeline.main import build_pipeline

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config or component_overrides:
        raise ValueError("this recipe uses explicit source configuration")
    solver = build_orthogonal_linear_point_trainer(build_pipeline(),
        learning_rate=.03, l2=0., complexity_weight=0., max_components=3,
        energy_threshold=.999, run_name="catalog_source_regression")
    if resource_context is not None:
        solver.set_resource_context(resource_context)
    solver.set_bias_module(None, enable=False)
    solver.set_random_seed(17)
    solver.set_max_steps(4)
    return solver
```

原preset真实装配训练X正交映射、LinearPoint Codec、回归Problem和梯度Adapter。Artifact是可原生as_dict的正交线性模型，含训练特征基与参数，正式CaseRuntime发布ModelRef；不返回活连接、数据客户端或一串SQL充当模型交付。验证只用同一训练特征映射，不对valid再fit基。

**怎样判断接对：** classical.json目标 `[valid.mse,0]`、训练loss、train/valid指标与真实ModelRef。本地默认的16/4行可由pipeline检查，但不声称模型四步收敛。远程结果必须先核对schema、顺序与快照时间；SQL没有ORDER BY时的80/20只是返回顺序切分，不是时间验证。这里不保留原metadata中的JDBC URL等可能带认证参数的内容；不要print(source)或把dataclass带secret的repr存到报告。

**运行入口：** 默认local可用副本根 `python run_project.py --check --build-check` 后 `python run_classical_and_report.py`，正式Project只运行一次。远程模式必须先完成自己的服务授权/字段契约，再显式设置CATALOG_CONNECT_SOURCE=1及所需环境变量；此后两条命令都会执行真实读取。本文没有尝试连接，也没有用本地成功替代远程客户端兼容性/连接收据。

### 变体一：Hive的同一数值表，模型不变

**目的：** 更换数据来源，沿用相同schema与Trainer。**改在哪里：** config.py完整替换：

```python
SOURCE = "hive"
```

**行为变化：** 明确授权并配置HIVE_*后，读取catalog_training_view的x1/x2/target，conn在finally关闭。**限制：** 没有SQL只读分析器、绑定参数或服务端分页；请使用专门的只读表/账号。认证配置是否受底层版本支持须真实环境验证，构造对象不算已连接。

### 变体二：JDBC驱动表

**目的/改在哪里：** config.py完整替换：

```python
SOURCE = "jdbc"
```

**行为变化：** 经JayDeBeApi+指定本地jar读取相同字段；原连接关闭后模型不依赖活JVM连接。**限制：** JDBC_URL不得内嵌凭据，资源context不会管理JVM线程/远程事务；SQL一次全部取回，Driver依赖与关闭语义须另验收。

### 变体三：S3兼容Parquet目录

**目的/改在哪里：** config.py完整替换：

```python
SOURCE = "s3"
```

**行为变化：** pyarrow/s3fs读取前缀文件后进行同一字段校验/切分。**限制：** 对象列必须全数值，本例不隐式编码类别；Parquet文件在读取期间变化时没有冻结数据快照或内容摘要，生产需要可复现的数据版本。该Source没有明确暴露文件系统关闭与连接池授权协议，不能因Case结束就假定所有远端资源已审计清理。

来源：mlblack `pipeline/sources.py`、`pipeline/datasets.py`、`pipeline/data_views/numeric.py`、`presets/linear.py`。Source与DataPipeline属于数据准备；Provider、Problem、Adapter和Project仍保留各自责任。
