"""Build source evidence and incrementally generate optional Catalog explanations.

This publisher runs independently from the read-only dashboard and search loop.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import threading

from .curation import prepare_packet, validate_note, CurationValidationError
from .curation_provider import DeepSeekGenerator, load_deepseek_config, PROMPT_VERSION, CurationProviderError
from .curation_store import resolve_knowledge_store


INDEX_SCHEMA = "nsgablack.catalog.knowledge_sources/v1"
PACKETS_SCHEMA = "nsgablack.catalog.knowledge_packets/v1"
DEFAULT_KEYS = (
    "adapter.nsga2", "adapter.vns", "adapter.moead", "adapter.search_plan", "adapter.bayesian_optimization",
    "tool.solution_pool", "tool.subpools", "tool.pool_task_spec", "tool.pool", "tool.unit_binding",
    "tool.population_unit", "tool.population_change", "bias.tabu", "tool.bo_acquisition",
    "mlblack.codec.linear_point", "mlblack.codec.neural_graph", "mlblack.data_view.numeric",
    "mlblack.head.binary_logistic", "mlblack.integration.learning_solver", "mlblack.trainer.learning_solver",
)


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def build_sources(source_roots: dict[str, Path], index_path: Path, packets_path: Path,
                  *, examples_index: dict | None = None) -> dict:
    """Capture once per image, so page reads never scan source or call a model."""
    from .registry import get_source_catalog
    from .usage_learning import select_documentation_guide
    entries = get_source_catalog(refresh=True, profile="default").list()
    def focused_examples(key):
        if examples_index is None:
            return ()
        records = tuple(examples_index["examples"][item] for item in examples_index["entries"].get(key, ())
                        if examples_index["examples"][item].get("origin") == "manifest")
        guide = select_documentation_guide(records)
        remaining = sorted((record for record in records if record is not guide),
                           key=lambda record: record.get("kind") not in {"project", "case"})
        return tuple(([guide] if guide is not None else []) + remaining)[:2]
    packets = {entry.key: prepare_packet(entry, entries, source_roots,
                                        usage_examples=focused_examples(entry.key)) for entry in entries}
    encoded = _json({"schema": PACKETS_SCHEMA, "packets": packets})
    if len(encoded.encode("utf-8")) > 32 * 1024 * 1024:
        raise ValueError("Knowledge source packets exceed their 32 MiB deployment limit")
    index = {"schema": INDEX_SCHEMA, "prompt_version": PROMPT_VERSION,
             "entries": {key: packet["source_digest"] for key, packet in packets.items()},
             "profiles": {profile: sorted(entry.key for entry in get_source_catalog(profile=profile).list())
                          for profile in ("default", "framework-core")},
             "packets_sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest()}
    packets_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    packets_path.write_text(encoded, encoding="utf-8")
    index_path.write_text(_json(index), encoding="utf-8")
    return {"ok": True, "entries": len(packets), "with_evidence": sum(bool(p["evidence"]) for p in packets.values()),
            "packet_bytes": len(encoded.encode("utf-8"))}


def load_packets(path: Path, *, index_path: Path | None = None) -> dict:
    if not path.is_file() or path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError("Knowledge packets are absent or oversized")
    content = path.read_text(encoding="utf-8")
    value = json.loads(content)
    if value.get("schema") != PACKETS_SCHEMA or not isinstance(value.get("packets"), dict):
        raise ValueError("Knowledge packets have an invalid schema")
    if index_path is not None:
        index = json.loads(index_path.read_text(encoding="utf-8"))
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if index.get("schema") != INDEX_SCHEMA or index.get("packets_sha256") != digest:
            raise ValueError("Knowledge source index does not match its evidence packets")
        if index.get("entries") != {key: p.get("source_digest") for key, p in value["packets"].items()}:
            raise ValueError("Knowledge source identities do not match their evidence packets")
    return value["packets"]


def curate_packets(packets: dict, store, generator, *, model: str, limit: int = 20,
                   workers: int = 3, keys: tuple[str, ...] | None = None,
                   source_roots: dict[str, Path] | None = None,
                   feedback_by_key: dict | None = None, include_failed_tutorial: bool = False,
                   examples_index: dict | None = None) -> dict:
    """Publish bounded independent drafts. Existing immutable identities are reused."""
    if not 1 <= limit <= 100 or not 1 <= workers <= 4:
        raise ValueError("Curation limit must be 1..100 and workers 1..4")
    if keys is not None and set(keys) - set(packets):
        raise ValueError("Requested knowledge entry does not exist in this release")
    ordered = list(keys) if keys is not None else list(dict.fromkeys((*DEFAULT_KEYS, *sorted(packets))))
    ordered = [key for key in ordered if key in packets]
    pending, cached, without_evidence = [], 0, []
    for key in ordered:
        packet = packets[key]
        if store.get(key, packet["source_digest"], model=model, prompt_version=PROMPT_VERSION) is not None:
            cached += 1
        elif packet.get("evidence"):
            pending.append(key)
        else:
            without_evidence.append(key)
    selected = pending[:limit]
    cancelled = threading.Event()

    def generate(key):
        if cancelled.is_set():
            return {"entry_key": key, "error": "batch_cancelled"}
        packet = packets[key]
        provider_phase = "generate"
        last_tutorial = None
        try:
            usage = {}
            reference = None
            if examples_index is not None:
                from .curation_seed import bounded_source_guide_reference
                examples = [examples_index['examples'][identifier]
                            for identifier in examples_index.get('entries', {}).get(key, ())]
                reference = bounded_source_guide_reference(packet, examples)
            # This editorial view only repeats text covered by original source
            # IDs. Validation and independent review still use the original
            # immutable packet; a guide never supplies a publication verdict.
            derived = {'source_guide_reference': reference} if reference else {}
            request = {**packet, **derived}
            previous = (feedback_by_key or {}).get(key)
            if isinstance(previous, dict) and previous.get("source_digest") == packet["source_digest"]:
                request = {**packet, **derived, "editor_feedback": {
                    name: previous[name] for name in ("issue", "validation_issue", "source_review", "previous_tutorial")
                    if name in previous}}
                request["editor_feedback"]["instruction"] = (
                    "修复上次真实验证与源码审阅指出的问题，继续使用本次冻结证据和原JSON契约。"
                    "叶组件可给完整独立输入/调用/输出，不声称未闭合的Case装配；正式Case入口必须符合真实注入契约。")
            last_review = None
            for attempt in range(2):
                provider_phase = "generate"
                # A review belongs to the candidate it inspected. Keep it in
                # that candidate's feedback, never attach it to a later draft.
                last_review = None
                result = generator.generate(request)
                last_tutorial = result.get("note", {}).get("tutorial")
                for name, count in result.get("usage", {}).items():
                    if type(count) is int and count >= 0:
                        usage[name] = usage.get(name, 0) + count
                try:
                    if getattr(generator, "requires_tutorial", False) and "tutorial" not in result["note"]:
                        raise CurationValidationError("Detailed component tutorial is missing")
                    note = validate_note(result["note"], packet)
                    if isinstance(note.get("tutorial"), dict):
                        from .usage_api_validation import inspect_usage_api
                        tutorial = note["tutorial"]
                        snippets = [(tutorial, tutorial["placement"]), *[
                            (extension, tutorial["placement"] + " " + extension["placement"])
                            for extension in tutorial.get("extensions", ())]]
                        # Python source binding cannot validate shell/text.
                        # Empty roots still permit the standalone Case-signature
                        # check; unresolved component calls remain unknown.
                        api_checks = [inspect_usage_api(snippet["code"], source_roots=source_roots or {},
                                                       placement=placement)
                                      for snippet, placement in snippets if snippet["language"] == "python"]
                        issues = [issue for check in api_checks for issue in check.get("issues", ())]
                        if issues:
                            raise CurationValidationError("Usage API contract mismatch: " + "; ".join(
                                str(issue.get("target", ""))[:100] + ": " + str(issue.get("message", ""))[:180]
                                for issue in issues[:6]))
                        usage["api_checked_calls"] = sum(len(check.get("checked_calls", ())) for check in api_checks)
                        usage["api_unknown_calls"] = sum(len(check.get("unknown_calls", ())) for check in api_checks)
                        usage["api_non_python_snippets"] = sum(snippet["language"] != "python"
                                                               for snippet, _ in snippets)
                    if getattr(generator, "requires_source_review", False):
                        from .tutorial_review import validate_review
                        provider_phase = "review"
                        reviewed = generator.review(packet, note)
                        for name, count in reviewed.get("usage", {}).items():
                            if type(count) is int and count >= 0:
                                usage[name] = usage.get(name, 0) + count
                        usage['review_actual_model'] = reviewed.get('actual_model', model)
                        last_review = validate_review(reviewed["note"], evidence_ids={item["id"] for item in packet["evidence"]})
                        if last_review["decision"] != "publish":
                            raise CurationValidationError("Tutorial source review did not approve publication")
                        note["tutorial_review"] = last_review
                    break
                except CurationValidationError as exc:
                    if attempt:
                        raise
                    # A single bounded format repair uses the same frozen
                    # evidence. It cannot add capabilities or relax validation.
                    request = {**packet, **derived, "editor_feedback": {
                        "issue": str(exc),
                        "validation_issue": str(exc),
                        "source_review": last_review,
                        "previous_tutorial": result.get("note", {}).get("tutorial"),
                        "instruction": "重新依据原证据整理；严格遵循当前生成器系统指定的输出格式，不添加额外顶层字段。使用已有key与出处ID，勿提内部事务调用。证据不足写明缺口，不复述成功验收短语；修复所指出的代码、证据或缺字段问题。"}}
            record = {"entry_key": key, "source_digest": packet["source_digest"], "model": model,
                      "prompt_version": PROMPT_VERSION,
                      "generated_at": datetime.now(timezone.utc).isoformat(), "note": note,
                      "evidence": packet["evidence"],
                      "usage": {**usage, "format_repairs": attempt, "actual_model": result.get("actual_model", model)}}
            saved = store.put(record)
            return {"entry_key": key, "generated_at": saved["generated_at"], "usage": saved["usage"]}
        except CurationProviderError as exc:
            category = str(exc)
            if category in {"ai_http_401", "ai_http_402", "ai_http_403"}:
                cancelled.set()
            failure = {"entry_key": key, "error": category, "provider_phase": provider_phase}
            if exc.diagnostics:
                failure["provider_diagnostics"] = exc.diagnostics
            if include_failed_tutorial and isinstance(last_tutorial, dict) and len(_json(last_tutorial)) <= 65536:
                failure["previous_tutorial"] = last_tutorial
            return failure
        except CurationValidationError as exc:
            # These validator diagnostics contain fixed categories/field names,
            # never model text, provider bodies, paths, or credentials.
            failure = {"entry_key": key, "error": "note_evidence_validation_failed", "validation_issue": str(exc)}
            if last_review is not None:
                failure["source_review"] = last_review
            if include_failed_tutorial and isinstance(last_tutorial, dict) and len(_json(last_tutorial)) <= 65536:
                failure["previous_tutorial"] = last_tutorial
            return failure
        except Exception as exc:
            return {"entry_key": key, "error": type(exc).__name__}

    results = []
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="catalog-curation") as executor:
        futures = [executor.submit(generate, key) for key in selected]
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda record: ordered.index(record["entry_key"]))
    failed = [r for r in results if "error" in r]
    return {"ok": not failed, "model": model, "prompt_version": PROMPT_VERSION,
            "generated": len(results) - len(failed), "cached": cached,
            "pending": len(pending) - len(results) + len(failed), "without_evidence": without_evidence,
            "results": results}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--root", action="append", required=True, help="trusted package=repository-path")
    build.add_argument("--index", type=Path, required=True)
    build.add_argument("--packets", type=Path, required=True)
    build.add_argument("--examples", type=Path, help="fixed, validated source example index")
    run = sub.add_parser("run")
    run.add_argument("--index", type=Path, required=True)
    run.add_argument("--packets", type=Path, required=True)
    run.add_argument("--config", type=Path, required=True)
    run.add_argument("--limit", type=int, default=20)
    run.add_argument("--workers", type=int, default=3)
    run.add_argument("--keys", required=True, help="explicit comma-separated existing Catalog keys")
    run.add_argument("--execute", action="store_true", help="explicitly authorize paid requests for these keys")
    run.add_argument("--root", action="append", default=[], help="trusted package=repository-path for source API checks")
    args = parser.parse_args(argv)
    if args.command == "run" and (not args.execute or not any(key.strip() for key in args.keys.split(","))):
        parser.error("run requires --execute and non-empty --keys; no paid work was started")
    try:
        if args.command == "build":
            roots = {}
            for item in args.root:
                name, separator, path = item.partition("=")
                if not separator or not path or name in roots:
                    raise ValueError("Invalid or duplicate source root")
                roots[name] = Path(path)
            examples_index = None
            if args.examples:
                from .examples import load_example_index
                examples_index = load_example_index(args.examples)
            result = build_sources(roots, args.index, args.packets, examples_index=examples_index)
        else:
            roots = {}
            for item in args.root:
                name, separator, path = item.partition("=")
                if not separator or not path or name in roots:
                    raise ValueError("Invalid or duplicate source root")
                roots[name] = Path(path)
            packets = load_packets(args.packets, index_path=args.index)
            keys = tuple(dict.fromkeys(key.strip() for key in args.keys.split(",") if key.strip()))
            if set(keys) - set(packets):
                raise ValueError("Requested knowledge entry does not exist in this release")
            config = load_deepseek_config(args.config)
            store = resolve_knowledge_store(readonly=False)
            store.ensure_schema()
            result = curate_packets(packets, store, DeepSeekGenerator(config, allow_paid_requests=True), model=config.model,
                                    limit=args.limit, workers=args.workers, keys=keys, source_roots=roots or None)
        print(_json(result))
        return 0 if result["ok"] else 1
    except Exception as exc:
        # Raw provider and driver errors can contain credentials; categories only.
        print(_json({"ok": False, "error_type": type(exc).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
