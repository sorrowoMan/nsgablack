"""正式GA Case一次choose交付主成员与具名副Pool；只读整理证据。"""
import argparse
import json
from run_partition_and_report import ROOT, RESULTS, execute_project, summarize_partition, write_json
from nsgablack.utils.engineering.file_io import atomic_write_text


def summarize_outputs(project):
    summary = summarize_partition(project)
    trace = json.loads((RESULTS / "ga_partition.json").read_text(encoding="utf-8"))
    if trace.get("partition_schema") != "pool_workflow_pilot.partition_trace/v2":
        raise ValueError("named selection output observations are missing")
    if not trace["run_id"].startswith(summary["case_run_id"] + ":solver-run:"):
        raise ValueError("named outputs belong to another Case run")
    if trace["initial"]["selection_outputs_before"] != {"elite": True, "reserve": False}:
        raise ValueError("expected existing elite and absent reserve before first selection")
    rows = trace["partitions"]
    identities = {}
    splits = []
    previous_elite, seen_tokens = [], set()
    child_records = {ref["candidate_token"]: (ref, provenance)
        for ref, provenance in zip(trace["change_output"]["refs"],
                                   trace["change_output"]["provenance"], strict=True)}
    if len(child_records) != 160:
        raise ValueError("expected 160 independently identified admitted children")
    for index, (row, reserve_count) in enumerate(zip(rows, (0, 80, 80), strict=True)):
        outputs = row["selection_outputs"]
        if (row["maintenance_bound"] or not row["elite_from_final_members"]
                or set(outputs) != {"elite", "reserve"}):
            raise ValueError("expected one selector-owned output declaration")
        expected = {"elite": row["applied_refs"][:20],
                    "reserve": row["remaining_refs"][80:]}
        for name in ("elite", "reserve"):
            output = outputs[name]
            if (output["refs"] != expected[name]
                    or output["refs"] != [row["source_refs"][i] for i in output["positions"]]):
                raise ValueError("named output differs from its exact offered positions")
            descriptor = output["descriptor"]
            identity = descriptor["pool_id"], descriptor["view_id"]
            if identities.setdefault(name, identity) != identity:
                raise ValueError("existing named output was recreated rather than replaced")
        if len(outputs["reserve"]["refs"]) != reserve_count:
            raise ValueError("unexpected reserve capacity")
        if (row.get("previous_elite_refs") != previous_elite
                or row.get("parent_read_added_evaluations") != 0
                or not isinstance(row.get("offspring_sources"), list)):
            raise ValueError("previous committed elite parent observations are missing or inconsistent")
        children = row["offspring_sources"]
        if len(children) != (0 if index == 0 else 80):
            raise ValueError("initialization must not sample parents; later steps must produce 80 children")
        if index == 0:
            seen_tokens.update(ref["candidate_token"] for ref in row["source_refs"])
        else:
            if row["source_refs"][-80:] != [item["child"] for item in children]:
                raise ValueError("parent evidence must align with this step's admitted child versions")
            current_tokens = set()
            for item in children:
                ref, parents, inputs = item["child"], item["source_refs"], item["change_input_refs"]
                token = ref["candidate_token"]
                if (len(parents) != 2 or inputs != parents
                        or any(parent not in previous_elite for parent in parents)
                        or token in seen_tokens or token in current_tokens):
                    raise ValueError("children must have new identities and exact previous-elite parents")
                saved_ref, provenance = child_records[token]
                metadata = provenance["metadata"]
                if (saved_ref != ref or provenance["candidate_token"] != token
                        or metadata.get("change_source_refs") != parents
                        or metadata.get("change_input_refs") != inputs):
                    raise ValueError("parent observations differ from published child provenance")
                current_tokens.add(token)
            seen_tokens.update(current_tokens)
        splits.append({"step": row["step"], "input_count": row["input_count"],
            "members": len(row["applied_refs"]), "elite": len(outputs["elite"]["refs"]),
            "reserve": reserve_count, "elite_from_final_members": True,
            "source_unchanged": row["source_unchanged"],
            "previous_elite_count": len(previous_elite), "verified_children": len(children)})
        previous_elite = outputs["elite"]["refs"]
    return {**summary, "named_outputs": splits, "maintenance_bound": False,
        "empty_reserve_created": True, "existing_pool_identity_preserved": True,
        "named_outputs_added_evaluations": 0, "parent_pool": "elite", "parent_pool_fraction": 1.0,
        "parents_from_previous_committed_elite": True, "offspring_identity_new": True,
        "verified_children": len(child_records), "parent_read_added_evaluations": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    if not args.report_only:
        # Keep the earlier partition-only run reproducible as a historical
        # report; the default three-Case outputs are never touched here.
        old = RESULTS / "ga_partition.json"
        if old.exists():
            payload = json.loads(old.read_text(encoding="utf-8"))
            if payload.get("partition_schema") == "pool_workflow_pilot.partition_trace/v1":
                write_json(RESULTS / "ga_partition_baseline.json", payload)
        result = execute_project(ROOT, group="partition")
        write_json(RESULTS / "project_selection_outputs_result.json", result.as_dict())
        if not result.ok:
            return result.exit_code or 1
    project = json.loads((RESULTS / "project_selection_outputs_result.json").read_text(encoding="utf-8"))
    summary = summarize_outputs(project)
    trace = json.loads((RESULTS / "ga_partition.json").read_text(encoding="utf-8"))
    write_json(RESULTS / "ga_partition_selection_outputs.json", trace)
    write_json(RESULTS / "selection_outputs_summary.json", summary)
    lines = ["# 一次choose交付主Pool与命名副Pool：正式运行", "",
        f"Project run：`{summary['project_run_id']}`。", "",
        "- 标准ga_partition Case、正式Project partition分组，L0为1 thread / 1 worker。",
        "- 3次提交，预算260，实际求值100+80+80=260；具名输出不额外求值。",
        "- selector一次返回members和elite/reserve映射；本Case没有pool_maintenance绑定。",
        "- 首轮输入100→members100、elite20、空reserve；后两轮输入180→members100、elite20、reserve80。",
        "- elite明确取自最终members；reserve只取未选位置。精确引用与原offered位置逐项一致。",
        "- 第一轮只初始化；第二、三轮分别从上一提交的20个elite有放回抽父代，生成80个新身份的孩子。",
        "- 已逐个核对160个孩子的change_source_refs/change_input_refs与已发布provenance，来源都是上一提交elite。",
        "- MixedPoolParentSelector的pool_fraction=1.0，PoolTask声明change_sources=('elite',)；读父代额外求值为0。",
        "- elite预先存在并精确替换；reserve首次缺失，即使为空也正式创建，后续保留同一池身份。",
        "- 选择只声明结果，由既有PoolEdit/Authority事务发布；主成员由PopulationUnit应用。",
        "- 本例明确按raw可行性、违反量、目标和挑20，不宣称等价于默认NSGA-II Pareto选择。",
        "- 提交后只读观察重算确定性分区，不调用Problem、不消耗RNG、不写池或Unit。", "",
        "完整证据：results/ga_partition_selection_outputs.json、results/selection_outputs_summary.json。",
        "原PARTITION_RESULTS.md保留历史分区结果；默认三Case结果不覆盖。", ""]
    atomic_write_text(ROOT / "SELECTED_OUTPUTS_RESULTS.md", "\n".join(lines))
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
