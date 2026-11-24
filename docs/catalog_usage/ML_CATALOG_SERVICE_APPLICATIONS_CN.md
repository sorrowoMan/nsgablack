# MLBlack 目录维护与查看：事实数据库、网页和静态导出

这些是目录工具，不执行求解。Catalog 数据库保存组件事实；Experiment 数据库保存观察记录；Artifact viewer 只查看已给出的 JSON。三者不能因为都能导出网页就混用。本页仅按源码核对，未写入目录数据库、启动网页服务或调用模型接口。

## mlblack.catalog.query · 从源目录同步到本地 SQLite，再查询

**什么时候用：** 想为 MLBlack 单独生成一个可重复查询的组件事实快照，或在脚本中按 kind/关键词筛选；不是让模型重新生成组件说明。当前部署看板中的 nsgablack 联邦目录是另一套服务入口，本工具不会自动替换它的库。

**先准备什么：** 当前三仓及 NumPy。可在完整 `mlblack/examples/cases/catalog_codec_demo/` Project 副本根保存这个目录维护工具；不改任何 Case。示例显式使用副本中的 `.mlblack/tutorial.sqlite`，不会写默认线上库。同步需要本地目录写权限，读取方只用已有库。

**放在哪：** 新建 Project 根 `inspect_catalog.py`，完整内容如下。这里没有新建 Trainer 或搜索循环，因此不额外申请求解 L0 授权。

**接入步骤：**

```python
from pathlib import Path
import json
from mlblack.catalog.registry import get_catalog
from mlblack.catalog.query import CatalogQuery, query_catalog, query_catalog_db
from mlblack.catalog.store import (
    SQLiteCatalogStore, resolve_catalog_store, materialize_catalog_db,
)


def main():
    root = Path(__file__).resolve().parent
    path = root / ".mlblack" / "tutorial.sqlite"
    source = get_catalog(refresh=True)
    written = materialize_catalog_db(path, catalog=source, profile="default")
    reader = resolve_catalog_store(path, readonly=True)
    if not isinstance(reader, SQLiteCatalogStore):
        raise TypeError("this example requires its explicit SQLite path")
    summary = reader.catalog_summary(profile="default")
    query = CatalogQuery(query="linear", limit=10, profile="default", db_path=str(path))
    first = query_catalog(query)
    second = query_catalog_db(query, db_path=str(path), profile="default")
    payload = {"source_count": len(source.list()), "written_count": written["entries"],
        "db_count": summary.total, "kind_counts": dict(summary.by_kind),
        "keys": [entry.key for entry in first.entries],
        "same_queries": [e.key for e in first.entries] == [e.key for e in second.entries]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

`get_catalog` 读取 MLBlack 自己的源注册表，不是 nsgablack 的联邦前缀空间，因此本地结果 key 没有 `mlblack.` 前缀。materialize_catalog_db 将当前 Catalog 交给实际 SQLiteCatalogStore.sync_catalog，事务中替换该 profile 的组件、关系和索引，保留其它 profile；它不是逐条追加，也不填 AI 用法。

profile 在这个原生存储面是快照命名空间；传一个名字不会自动执行 nsgablack 的 framework-core 过滤。需要专门范围时，先构造那个范围的真实 Catalog，再同步。query_catalog 未提供 catalog 对象时固定走数据库；source="registry" 不会把它变成源读取器，库/所选 profile 不存在就报错，不静默换来源。

kind/标签/fields 会影响结果。原生对象查询分支先 search(limit) 再做额外过滤，不能据“只有三行”保证源中仅三条匹配；本例固定数据库分支、limit=10。facets 是这次返回行的分面，不是整库统计。整库数量读 store.catalog_summary，而非结果行数。

**怎样判断接对：** 当前三个数量 source_count/written_count/db_count 应一致，same_queries 为 true，keys 最多10条且属于实际库；数量随本机源码版本变化，不硬编码。这里没有判断算法正确性、示例运行次数或 AI 说明完成度。SQLite 的 readonly 读取不等于对象级安全沙箱，sync_catalog 自身仍打开写连接，不把写方法暴露给只读调用者。

**运行入口：** 在该完整 Project 副本根执行 `python inspect_catalog.py`；会实际创建/替换本地目录快照，不会运行原 Project。重新运行是同步新事实，不能把旧 DB 的 built_at 当成最新源码。本轮未执行这条命令。

### 变体一：用已有 PostgreSQL 存储同一份事实

**目的：** 多人需要查询同一组件快照时，显式更换数据库连接，保留查询协议。

**改在哪里：** 新建完整 `inspect_catalog_postgres.py`。先安装 MLBlack 声明的 postgres 可选依赖，并在运行环境设置 `EXAMPLE_CATALOG_DB_URL`；代码不打印连接串。

```python
import json
import os
from mlblack.catalog.registry import get_catalog
from mlblack.catalog.query import CatalogQuery, query_catalog_db
from mlblack.catalog.store import PostgresCatalogStore, resolve_catalog_store


def main():
    target = os.environ["EXAMPLE_CATALOG_DB_URL"]
    if not target.startswith(("postgres://", "postgresql://")):
        raise ValueError("an explicit PostgreSQL target is required")
    writer = resolve_catalog_store(target, readonly=False)
    if not isinstance(writer, PostgresCatalogStore):
        raise TypeError("expected PostgreSQL store")
    source = get_catalog(refresh=True)
    report = writer.sync_catalog(source, profile="default")
    result = query_catalog_db(CatalogQuery(query="linear", limit=10),
        db_path=target, profile="default")
    print(json.dumps({"written_count": report["entries"],
        "keys": [entry.key for entry in result.entries]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
```

**行为变化：** 创建/同步目标 PostgreSQL 的目录表，需要实际数据库和建表/写入权限；之后 query_catalog_db 通过同一公开面只读查询。依赖不可用或连接失败会报错，不回退 SQLite。

**限制：** 这不是给用户当前看板自动部署一个新库。查询的 as_dict/deep_link 可能包含 db_path，因此连接串含凭据时不要直接打印整个结果或分享其链接；本例只打印非敏感数量和 key。不把任何账户写进源码或目录 JSON。

来源：`mlblack/catalog/query.py`、`catalog/store/surface.py`；没有本轮数据库执行证明。

## mlblack.dashboard.catalog_web · 用已经同步好的库打开本地查询页

**什么时候用：** 已有上节实际生成的 tutorial.sqlite，希望本地浏览，不希望每次打开网页都重新扫描并写库。HTTP 页面与 Streamlit launcher 都只使用明确库路径。

**先准备什么：** 保留上节 Project 副本和已同步的 SQLite。轻量 HTTP 只用标准库；Streamlit 分支需要 web 可选依赖。下面仅展示回环地址，不包含登录系统；用户当前 simon 看板的访问控制不会自动附着到这个独立服务。

**放在哪：** 新建根目录完整 `serve_catalog.py`：

**接入步骤：**

```python
from pathlib import Path
from mlblack.catalog.web_app import serve_catalog_web


def main():
    path = Path(__file__).resolve().parent / ".mlblack" / "tutorial.sqlite"
    if not path.is_file():
        raise FileNotFoundError("materialize the tutorial catalog first")
    server = serve_catalog_web(host="127.0.0.1", port=8651,
        profile="default", db_path=path)
    print("Open http://127.0.0.1:8651/")
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
```

当前源码的摘要路由已校正为调用真正的 DB facade，避免把 db_path/profile 传给只接受 Catalog 对象的静态 HTML helper。这只修正调用链，没有验证用户目标数据库或部署服务；本轮针对性 mock 测试通过。

**怎样判断接对：** 打开打印地址，搜索 linear；`/api/catalog?kind=model&q=linear&limit=5` 应返回最多5个本地 model key，`/api/summary` 应返回整库 total/by_kind。空结果先核对 profile、kind、关键词和实际同步时间，不将其解释为模型库缺组件。网页查询不运行组件，不会训练模型或补 AI 笔记。

**运行入口：** `python serve_catalog.py`。进程一直服务，结束时关闭它；本轮没有启动这项服务。

### 变体一：给 launcher 提供明确的 Streamlit 页面

**目的：** 用现有 launch_catalog_dashboard 启动一个只读页面，脚本的真实参数协议也一并给出，不假设任意文件都能当页面运行。

**改在哪里：** 新建 `catalog_page.py` 和 `launch_catalog_page.py`，两文件完整如下。

```python
# catalog_page.py
import argparse
import streamlit as st
from mlblack.catalog.query import CatalogQuery, query_catalog_db

parser = argparse.ArgumentParser()
parser.add_argument("--db-path", required=True)
parser.add_argument("--profile", default="default")
parser.add_argument("--no-refresh", action="store_true")
args = parser.parse_args()
st.title("MLBlack 组件事实")
query = st.text_input("关键词", "linear")
result = query_catalog_db(CatalogQuery(query=query, limit=50),
    db_path=args.db_path, profile=args.profile)
st.dataframe([{"key": e.key, "kind": e.kind, "title": e.title,
               "summary": e.summary} for e in result.entries], hide_index=True)
st.caption("这次查询返回的行数：" + str(len(result.entries)))
```

```python
# launch_catalog_page.py
from pathlib import Path
from mlblack.catalog.dashboard import launch_catalog_dashboard


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    raise SystemExit(launch_catalog_dashboard(script_path=root / "catalog_page.py",
        db_path=root / ".mlblack" / "tutorial.sqlite", profile="default",
        host="127.0.0.1", port=8652, headless=True))
```

**行为变化：** 执行 `python launch_catalog_page.py` 后在8652浏览；launcher 调用当前 Python 的 Streamlit 子进程，并传入 profile/db-path/no-refresh。页面使用绝对包导入，实际实现了这些参数，不依赖相对导入的隐含 package 上下文。

**限制：** launcher 不包含页面业务、不自动物化数据库，也不证明目标端口空闲；它返回子进程退出码并等待服务结束。这里没有新增公开部署、权限管理或远程执行能力。

## mlblack.dashboard.catalog_html · 导出可离线打开的事实与能力说明

**什么时候用：** 想把现有目录快照和后端声明发给同事查看，不依赖持续运行的服务器。HTML 是导出时的值，不会实时查询或运行算法。

**先准备什么：** 上节同一个 Project 副本与已有 tutorial.sqlite。只读取目录 DB；后端矩阵查询当前注册后端的契约，可以导入和缓存后端 facade，但不构造训练会话或检验设备授权。

**放在哪：** 根目录新建完整 `export_catalog_views.py`。

**接入步骤：**

```python
from pathlib import Path
from mlblack.catalog.store import load_catalog_db
from mlblack.catalog.dashboard import export_catalog_html
from mlblack.catalog.backend_dashboard import backend_capability_matrix, export_backend_matrix_html


def main():
    root = Path(__file__).resolve().parent
    catalog = load_catalog_db(root / ".mlblack" / "tutorial.sqlite", profile="default")
    output = root / "results" / "catalog_views"
    first = export_catalog_html(output / "components.html", catalog=catalog)
    matrix = backend_capability_matrix(
        requirements=("tensor.float_tensor", "autograd.functional.grad"),
        backend_names=("numpy", "torch"))
    second = export_backend_matrix_html(output / "backends.html", matrix=matrix)
    print(first)
    print(second)


if __name__ == "__main__":
    main()
```

显式传入 catalog，避免 HTML helper 省略参数时读取当前源注册表而误当成 DB 快照。matrix 也先显式构造再传给 exporter，输出 numpy/torch 在这两个能力字符串上的声明支持。

**怎样判断接对：** components.html 行数与源 Catalog.list 相符，包含 key/kind/title/tags/summary；它不自动加入本平台的详细教程或 AI 审核。backends.html 两行两项能力，yes/no 只表示 contract.supports，不证明库已安装、运算执行、GPU可用或 L0 授权。核对的是导出时快照，不以 HTML 修改时间代替目录 built_at。

**运行入口：** `python export_catalog_views.py`，再打开打印的两个本地文件；本轮没有执行该脚本。

### 变体一：给已有正式运行的 JSON 描述生成静态 Artifact 页

**目的：** 查看实际运行已经产生的描述，不为了展示再次训练或制造假的 Artifact。

**改在哪里：** 先按本目录 [正式 ArtifactBundle 用法](ARTIFACT_BUNDLE_APPLICATION_CN.md) 在另一份完整 catalog_codec_demo 副本配置 BundleObserver。它的唯一正式 Project 运行会生成 `cases/linear_point/results/bundle/summary.json`。有了这份本轮真实文件后，在该副本根新建完整 `export_artifact_view.py`：

```python
from pathlib import Path
from mlblack.catalog.artifacts import export_artifact_html


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    description = root / "cases" / "linear_point" / "results" / "bundle" / "summary.json"
    if not description.is_file():
        raise FileNotFoundError("run the formally assembled BundleObserver Case first")
    path = export_artifact_html(root / "results" / "artifact-description.html", description)
    print(path)
```

**行为变化：** 执行 `python export_artifact_view.py`，读取已有 JSON 并写 HTML，不再次调用 run_project。Bundle 这种通用描述主要可在 Raw Payload 查看，类型专用 Summary/Expression 区可能为空；空区不意味着原模型没训练。

**限制：** 此 viewer 读取 JSON 元数据，不加载 NPZ/ZIP 模型、不验证 PublicationReceipt/digest，也不把本地观察摘要升级为权威 Artifact。需恢复或推理时仍消费正式模型引用和对应 loader。本轮未生成上述运行文件或执行导出。

来源：`mlblack/catalog/dashboard.py`、`backend_dashboard.py`、`artifacts.py`、`web_app.py` 与 store/facade；源码与静态调用检查不替代服务运行证据。
