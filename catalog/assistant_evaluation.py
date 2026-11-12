"""Evaluate assistant deliveries without confusing format with semantic quality.

Saved responses and human reviews are bound to the exact exported corpus and
response bytes. References/rubrics are never supplied to the model. No retries,
automatic training, production switch or new execution authority are created.
"""
from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from .lab_assistant import AssistantProviderError, validate_draft

SCHEMA = "nsgablack.assistant_evaluation/v1"
RESPONSES_SCHEMA = "nsgablack.assistant_responses/v1"
REVIEWS_SCHEMA = "nsgablack.assistant_reviews/v1"


def content_digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    allow_nan=False, separators=(",", ":")).encode()).hexdigest()


def model_configuration_metadata(config) -> dict:
    """Record actual selected settings, never credentials or a private URL."""
    from .curation_provider import DeepSeekConfig, ENDPOINT
    from .lab_model_provider import CompatibleAssistantConfig, _endpoint
    if isinstance(config, DeepSeekConfig):
        backend, endpoint, json_mode = "deepseek", ENDPOINT, True
    elif isinstance(config, CompatibleAssistantConfig):
        backend, endpoint, json_mode = "compatible", _endpoint(config.base_url)[0], config.json_mode
    else:
        raise ValueError("model_configuration_invalid")
    metadata = {"backend": backend, "model": config.model,
                "endpoint_sha256": hashlib.sha256(endpoint.encode("utf-8")).hexdigest(),
                "max_output_tokens": config.max_output_tokens, "timeout_seconds": config.timeout_seconds,
                "json_mode": json_mode, "temperature": 0.1}
    return {**metadata, "configuration_sha256": content_digest(metadata),
            "evidence_level": "selected_configuration_not_weight_attestation"}


def _delivery(answer: Mapping) -> str:
    return "draft" if answer["draft"] is not None else "clarify" if answer["questions"] else "discussion"


def evaluate_records(records: Sequence[Mapping], *, responses: Mapping | None = None,
                     generator=None, model_identity: str, reviews: Mapping | None = None,
                     reference_replay: bool = False) -> dict:
    """Protocol and delivery checks are automatic; prose semantics require review."""
    if not isinstance(model_identity, str) or not model_identity.strip() or len(model_identity) > 160:
        raise ValueError("model_identity_invalid")
    if sum((responses is not None, generator is not None, reference_replay)) != 1:
        raise ValueError("exactly_one_response_source_required")
    records = tuple(records)
    ids = [r["id"] for r in records]
    if not records or len(set(ids)) != len(ids):
        raise ValueError("evaluation_cases_invalid")
    if responses is not None and (not isinstance(responses, Mapping) or set(responses) - set(ids)):
        raise ValueError("unknown_response_case")
    reviews = {} if reviews is None else reviews
    if not isinstance(reviews, Mapping) or set(reviews) - set(ids):
        raise ValueError("unknown_review_case")
    rows = []
    for record in records:
        packet = deepcopy(record["packet"])
        row = {"id": record["id"], "family": record["family"], "split": record["split"],
               "protocol": "failed", "delivery_matches_reference": None,
               "draft_matches_reference": None, "semantic_review": "pending",
               "rubric": deepcopy(record["rubric"]), "response_sha256": None}
        try:
            if reference_replay:
                answer = deepcopy(record["reference_answer"])
            elif generator is not None:
                # Only the actual inference packet is visible, never reference/rubric.
                answer = generator.generate(packet)
            else:
                if record["id"] not in responses:
                    row["error"] = "response_missing"
                    rows.append(row)
                    continue
                answer = deepcopy(responses[record["id"]])
            checked = validate_draft(answer, base_digest=packet["base_digest"],
                                     catalog=packet["assembly_catalog"],
                                     framework_context=packet["framework_context"])
            reference = record["reference_answer"]
            row.update(protocol="passed", response_sha256=content_digest(answer),
                       delivery_matches_reference=_delivery(checked) == _delivery(reference),
                       draft_matches_reference=(content_digest(checked["draft"]) ==
                                                content_digest(reference["draft"])) if reference["draft"] is not None else None,
                       answer=deepcopy(answer))
        except AssistantProviderError:
            row["error"] = "response_or_provider_rejected"
        except Exception:
            # Provider exceptions can contain headers, private URLs or response text.
            row["error"] = "generation_or_validation_failed"
        review = reviews.get(record["id"])
        if review is not None:
            if (not isinstance(review, Mapping) or set(review) != {"response_sha256", "decision"}
                    or review["decision"] not in {"pass", "fail", "needs_more_evidence"}
                    or row["response_sha256"] is None
                    or review["response_sha256"] != row["response_sha256"]):
                raise ValueError("review_response_mismatch")
            row["semantic_review"] = review["decision"]
        rows.append(row)
    return {"schema": SCHEMA, "model_identity": model_identity,
            "model_identity_kind": "experiment_label", "model_configuration": None,
            "kind": "harness_reference_replay" if reference_replay else "model_evaluation",
            "cases": rows, "summary": {
                "total": len(rows), "protocol_passed": sum(r["protocol"] == "passed" for r in rows),
                "delivery_matches_reference": sum(r["delivery_matches_reference"] is True for r in rows),
                "draft_matches_reference": sum(r["draft_matches_reference"] is True for r in rows),
                "semantic_passed": sum(r["semantic_review"] == "pass" for r in rows),
                "semantic_failed": sum(r["semantic_review"] == "fail" for r in rows),
                "semantic_pending": sum(r["semantic_review"] in {"pending", "needs_more_evidence"} for r in rows)},
            "limitations": ["协议合法与交付形态相符不证明解释正确或算法正确。",
                            "参考答案回放只检验评测器，不计作模型能力。",
                            "本评测不执行装配；运行验收须另走正式 Project runner。",
                            "测试参考答案和评分要求不进入模型输入。"]}


def _read_json(path: Path):
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("evaluation_file_too_large")
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate_json_key")
            value[key] = item
        return value
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite_json")))


def main(argv=None):
    parser = argparse.ArgumentParser(description="框架助手评测：格式检查与语义人审分别报告")
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--split", choices=("train", "validation", "test"), default="test")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--responses", type=Path, help="读取已保存回答，不访问模型")
    source.add_argument("--model-config", type=Path, help="显式调用服务端配置的模型，每题一次")
    source.add_argument("--reference-replay", action="store_true", help="仅回放参考答案检验工具")
    parser.add_argument("--model-identity", default="reference-fixture")
    parser.add_argument("--reviews", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    from .assistant_dataset import load_exported_records
    records = load_exported_records(args.dataset, split=args.split)
    corpus = hashlib.sha256((args.dataset / "metadata.json").read_bytes()).hexdigest()
    responses = None
    if args.responses:
        saved = _read_json(args.responses)
        if (not isinstance(saved, dict) or set(saved) != {"schema", "corpus_sha256", "model_identity", "responses"}
                or saved["schema"] != RESPONSES_SCHEMA or saved["corpus_sha256"] != corpus
                or saved["model_identity"] != args.model_identity):
            raise ValueError("saved_responses_mismatch")
        responses = saved["responses"]
    reviews = None
    if args.reviews:
        saved = _read_json(args.reviews)
        if (not isinstance(saved, dict) or set(saved) != {"schema", "corpus_sha256", "reviews"}
                or saved["schema"] != REVIEWS_SCHEMA or saved["corpus_sha256"] != corpus):
            raise ValueError("saved_reviews_mismatch")
        reviews = saved["reviews"]
    generator = None
    configuration_metadata = None
    if args.model_config:
        if args.model_identity == "reference-fixture":
            parser.error("真实模型评测须显式填写 --model-identity")
        from .lab_model_provider import create_assistant_generator, load_assistant_model_config
        config = load_assistant_model_config(args.model_config)
        generator = create_assistant_generator(config)
        configuration_metadata = model_configuration_metadata(config)
    report = evaluate_records(records, responses=responses, generator=generator,
                              model_identity=args.model_identity, reviews=reviews,
                              reference_replay=args.reference_replay)
    report["corpus_sha256"] = corpus
    report["model_configuration"] = configuration_metadata
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"kind": report["kind"], **report["summary"]}, ensure_ascii=False))
    return 0 if report["summary"]["protocol_passed"] == report["summary"]["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
