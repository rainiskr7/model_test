"""Protocol construction for multimodal publication adapters."""

from __future__ import annotations

from typing import Any, Mapping

from shared.multimodal.publish.schema import KRETA_ANSWER_PARSER_HASH, KRETA_ANSWER_PARSER_VERSION, make_protocol


def _add_decoding(config: Mapping[str, Any], recorded: dict[str, Any], unknown: list[str]) -> None:
    """기록된 디코딩 설정과 누락된 프로토콜 항목을 추가한다."""
    decoding = config.get("decoding") or {}
    serving = config.get("serving_constraints")
    removed = set(serving.get("removed_parameters") or []) if isinstance(serving, Mapping) else set()
    for key in ("temperature", "max_tokens", "seed"):
        value = decoding.get(key)
        if key in removed:
            recorded[f"{key}_removed"] = True
        elif value is None:
            unknown.append(key)
        else:
            recorded[key] = value
    if isinstance(serving, Mapping):
        # Carry every key the run recorded, not a fixed projection: dropping a
        # constraint this code does not know about would let a constrained run
        # share a cohort with an unconstrained one.
        snapshot = {
            key: serving.get(key)
            for key in (
                "unsupported_sampling_params",
                "max_output_tokens",
                "force_skip_special_tokens",
                "removed_parameters",
                "skip_special_tokens",
            )
        }
        snapshot.update({key: value for key, value in serving.items() if key not in snapshot})
        recorded["serving_constraints"] = snapshot
    unknown.extend(("prompt_template_hash", "answer_parser_hash", "image_preprocessing_version"))


def _dataset_revision(config: Mapping[str, Any]) -> Any:
    """기록된 데이터셋 revision 또는 commit을 반환한다."""
    dataset = config.get("dataset") or {}
    return dataset.get("revision") or dataset.get("git_commit")


def _add_dataset_provenance(config: Mapping[str, Any], recorded: dict[str, Any]) -> None:
    """명시된 데이터셋 출처 필드를 기록 순서대로 추가한다."""
    dataset = config.get("dataset")
    if not isinstance(dataset, Mapping):
        return
    recorded["dataset_provenance"] = {
        key: dataset.get(key)
        for key in ("huggingface_id", "revision", "revision_source", "git_repo", "git_commit")
        if key in dataset
    }


def _kreta_protocol(config: Mapping[str, Any], mode: str, item_digest: str | None, rows: list) -> dict:
    """KRETA 파서와 모드 및 데이터셋의 프로토콜을 구성한다."""
    recorded: dict[str, Any] = {"benchmark": "KRETA"}
    inferred: dict[str, Any] = {}
    unknown: list[str] = []
    if mode == "unknown":
        unknown.append("mode")
    else:
        recorded["mode"] = mode
        _add_decoding(config, recorded, unknown)
        # KRETA binds its own fixed response parser below; this is known even
        # though the generic helper treats answer parser metadata as absent.
        unknown = [item for item in unknown if item != "answer_parser_hash"]
        if "max_tokens" in unknown:
            unknown.remove("max_tokens")
            inferred["max_tokens"] = {
                "value": 32 if mode == "direct" else 4096,
                "basis": f"legacy run_kreta.sh: {mode} mode default KRETA_MAX_TOKENS",
            }
    recorded["answer_parser_version"] = KRETA_ANSWER_PARSER_VERSION
    recorded["answer_parser_hash"] = KRETA_ANSWER_PARSER_HASH
    _add_dataset_provenance(config, recorded)
    if item_digest:
        recorded["dataset_item_digest"] = item_digest
    else:
        unknown.append("dataset_item_digest")
    splits = {row.get("split") for row in rows if row.get("split") is not None}
    if len(splits) == 1:
        recorded["split"] = next(iter(splits))
    else:
        unknown.append("split")
    if mode == "unknown":
        unknown.extend(("temperature", "seed", "prompt_template_hash", "image_preprocessing_version"))
    protocol = make_protocol(recorded, inferred, unknown)
    return protocol


def _judge_protocol(summary: Mapping[str, Any], config: Mapping[str, Any], recorded_sha: Any, item_digest: str | None, rejudge: bool, generation_revision: Any) -> dict:
    """Judge 판정 규약과 고정 예측의 식별자를 구성한다."""
    recorded = {
        "benchmark": "KOFFVQA-judge",
        "judge_model": summary.get("judge_model"),
        "judge_prompt_version": summary.get("judge_prompt_version"),
        "prediction_sha256": recorded_sha,
        "dataset_item_digest": item_digest,
        "limit": (config.get("extra") or {}).get("limit"),
    }
    for key in ("judge_prompt_template_sha256", "judge_base_url", "judge_served_identity"):
        if summary.get(key):
            recorded[key] = summary[key]
    request = summary.get("judge_request") or {}
    for key in ("provider", "reasoning_effort"):
        if request.get(key):
            recorded["judge_" + key] = request[key]
    # The legacy default stays in decoding.max_tokens; do not fork its cohort.
    if request.get("max_tokens_effective") not in (None, 1024):
        recorded["judge_max_tokens"] = request["max_tokens_effective"]
    if rejudge:
        # Diagnostic variant: the predictions are held fixed, so they are part of
        # this protocol's identity rather than informational provenance.
        recorded["rejudged_prediction_sha256"] = recorded_sha
    unknown = [key for key in ("judge_model", "judge_prompt_version") if not recorded.get(key)]
    if not summary.get("judge_prompt_template_sha256"):
        unknown.append("judge_prompt_template_hash")
    _add_decoding(config, recorded, unknown)
    if generation_revision:
        recorded["dataset_provenance"] = {"revision": generation_revision}
    if not item_digest:
        unknown.append("dataset_item_digest")
    protocol = make_protocol(recorded, {}, unknown)
    return protocol
