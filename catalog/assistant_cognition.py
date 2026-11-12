"""A short, explicitly separate profile for framework-concept SFT experiments.

It teaches explanations and design judgments, not the full online assembly
envelope. It cannot replace the workbench dataset or demonstrate that a model
can satisfy the online JSON protocol. No tokenizer truncation is performed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .assistant_dataset import load_exported_records

PROFILE = "framework_cognition_only/v1"
SYSTEM = ("你是 blackbase、nsgablack、mlblack 框架的中文协作助手。理解用户的算法想法，"
          "解释组件职责、复用位置与必要扩展；保留用户已确认的条件。"
          "框架接口以当前版本源码为准；没有执行证据时不宣称运行成功。"
          "这次只回答设计与概念，不生成可执行装配。")


def cognition_messages(record: dict) -> list[dict]:
    packet = record["packet"]
    context = packet["guide_context"]
    parts = [packet["instruction"]]
    if context["design_notes"]:
        parts.append("已记录的项目决定：\n" + context["design_notes"])
    if context["history"]:
        parts.append("相关讨论：\n" + "\n".join(row["role"] + ": " + row["content"]
                                             for row in context["history"]))
    nodes = packet["assembly"].get("nodes", [])
    if nodes:
        parts.append("当前算法实例：" + "，".join(node["id"] + "=" + node["component"] for node in nodes))
    # Retain the actual dynamic support facts independently of the reference.
    # Omitting these would teach unsupported BO as timeless model knowledge.
    catalog = packet["assembly_catalog"]
    support = {"online_adapters": [row["key"] for row in catalog["components"]["adapters"]],
               "unsupported": catalog.get("unsupported", [])}
    parts.append("本次页面的算法支持事实（不代表整个框架的能力）：\n" +
                 json.dumps(support, ensure_ascii=False, separators=(",", ":")))
    answer = record["reference_answer"]
    target = answer["explanation"]
    if answer["changes"]:
        target += "\n建议变更：" + "；".join(answer["changes"])
    if answer["questions"]:
        target += "\n需要澄清：" + "；".join(answer["questions"])
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": "\n\n".join(parts)},
            {"role": "assistant", "content": target}]


def export_cognition_dataset(parent: str | Path, output: str | Path) -> dict:
    parent, output = Path(parent), Path(output)
    # All splits are loaded/validated before output is created.
    splits = {name: load_exported_records(parent, split=name) for name in ("train", "validation", "test")}
    if output.exists():
        raise ValueError("cognition_output_already_exists")
    prepared, metadata = {}, []
    for split, records in splits.items():
        rows = []
        for record in records:
            messages = cognition_messages(record)
            rows.append(json.dumps({"messages": messages}, ensure_ascii=False, allow_nan=False))
            metadata.append({"id": record["id"], "family": record["family"], "split": split,
                             "review_status": "agent_source_checked", "semantic_quality": "not_model_evaluated",
                             "message_characters": [len(m["content"]) for m in messages],
                             "token_count": None, "rubric": record["rubric"]})
        prepared[split + ".jsonl"] = ("\n".join(rows) + "\n").encode("utf-8")
    prepared["metadata.json"] = json.dumps(metadata, ensure_ascii=False, indent=2).encode("utf-8")
    manifest = {"schema": "nsgablack.assistant_cognition_dataset/v1", "profile": PROFILE,
                "parent_manifest_sha256": hashlib.sha256((parent / "metadata.json").read_bytes()).hexdigest(),
                "counts": {key: len(value) for key, value in splits.items()},
                "files": {name: hashlib.sha256(data).hexdigest() for name, data in prepared.items()},
                "limitations": ["自然语言认知任务，不是实验台 JSON 装配协议训练。",
                                "样本有源码核对，不代表人工审核或模型效果已验证。",
                                "分词长度由训练 tokenizer 实测；导出不截断内容。",
                                "测试集独立保存，不是训练输入。"]}
    output.mkdir(parents=True)
    for name, data in prepared.items():
        (output / name).write_bytes(data)
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description="导出独立的短框架认知数据；不能替代线上装配协议训练")
    parser.add_argument("parent", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    value = export_cognition_dataset(args.parent, args.output)
    print(json.dumps({"profile": value["profile"], "counts": value["counts"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
