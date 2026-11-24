# 普通安装后的组件用法资料

当前 wheel 除组件代码、Catalog 条目与示例声明外，也包含本目录的公开中文用法书。
普通 `pip install` 安装不再丢失这些 Markdown；源码安装与 wheel 安装使用同一份内容。
它们安装在 `nsgablack/docs/catalog_usage/`，不是当前工作目录下的 `docs/`。

在已安装当前版本的环境中，可直接查看实际资源位置：

```python
from pathlib import Path
import nsgablack.catalog

package_root = Path(nsgablack.catalog.__file__).resolve().parent.parent
guide_root = package_root / "docs" / "catalog_usage"
for guide in sorted(guide_root.glob("*.md")):
    print(guide.name, guide)
```

用法书中的 `cases/search/...` 等代码应写入用户自己的标准 Project。
先执行 `python -m nsgablack project new my_project`，再进入该目录执行
`python -m nsgablack project add-case search --type solver --framework nsgablack`；
具体章节会说明要替换的文件、装配入口和结果读取方式。

这些资料只表示源码可读。普通 wheel 不附带全部示例 Project、业务数据、
数据库、预构建部署索引或运行收据，也不会因读取资料而调用 AI。
引用仓库内现有 Project 的章节需要另取得对应版本的公开示例源码；
跨框架章节仍须安装所需的 BlackBase、MLBlack 及其可选后端。
服务器 Catalog 的完整来源索引及真实运行记录仍由发布流程构建和核验。
