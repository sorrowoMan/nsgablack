# -*- coding: utf-8 -*-
"""Plugin template / 插件模板。"""

from __future__ import annotations

from nsgablack.catalog.markers import component
from nsgablack.plugins.base import Plugin


@component(kind="plugin")
class PluginTemplate(Plugin):
    # TODO(中/EN): 仅声明真实读写字段 / declare only real read-write fields.
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("TODO(中/EN): 一句话说明 context 契约 / one-line context contract.",)

    def __init__(self) -> None:
        # TODO(中/EN): 设置稳定插件名 / set a stable plugin name.
        super().__init__(name="plugin_template")
