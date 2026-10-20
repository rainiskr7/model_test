"""입력: 결과 루트·모델 폴더·벤치. 출력: 검증한 코호트와 반복 평균 또는 안전한 후보 오류."""

import hashlib
import json
from pathlib import Path

from shared.multimodal.publish.schema import (
    apply_model_identity, canonical_model_id, load_model_identity_map,
    sidecar_path, validate_artifact_integrity, validate_sidecar,
)
from shared.multimodal.publish.select import cohort_key, select_representatives
from shared.multimodal.rescore.manifest import load_manifest
from shared.multimodal.rescore.sessions import read_session
from shared.stats.item_scores import METRICS, average_runs, score_items
from shared.stats.paired import validate_pair

BENCHMARKS = {"k_dtcbench": "K-DTCBench", "k_mmbench": "K-MMBench", "mtvqa_kr": "MTVQA-KR"}


class SelectionError(ValueError):
    """선택 실패 사유와 원문을 제외한 후보만 보관한다."""

    def __init__(self, reason, candidates=()):
        super().__init__(reason)
        self.candidates = list(candidates)


def candidates(sidecars):
    """sidecar에서 선택 설명에 필요한 식별자만 뽑는다."""
    return sorted([{"cohort": list(cohort_key(v)[:3]), "model": canonical_model_id(v),
                    "session": v.get("session"), "source": v["source"]["unit"],
                    "publishable": v["publishable"]} for v in sidecars],
                  key=lambda v: v["source"])


def choose_cohort(sidecars, fingerprint=None):
    """기존 선택기의 단일 코호트와 접힌 반복 전체를 반환한다."""
    eligible = [v for v in sidecars if fingerprint is None or cohort_key(v)[2] == fingerprint]
    selected, ambiguous = select_representatives(eligible)
    if ambiguous or len(selected) != 1:
        raise SelectionError("ambiguous or unavailable cohort", candidates(eligible or sidecars))
    return selected[0]


def read_sidecars(base, model_dir, bench):
    """모델 폴더 안 세션의 sidecar·원본 SHA·source 연결을 읽기만 하여 검증한다."""
    base = Path(base).resolve()
    model = Path(model_dir)
    model = (model if model.is_absolute() else base / (
        Path("results") / model if len(model.parts) == 1 else model)).resolve()
    if bench not in METRICS or model.parent != (base / "results").resolve() or not model.is_dir():
        raise SelectionError("expected model directory directly under base/results")
    mapping, values = load_model_identity_map(base), []
    for source in sorted(model.rglob(bench)):
        if not source.is_dir() or "_derived" in source.parts:
            continue
        try:
            if not source.resolve().is_relative_to(model):
                raise ValueError("source escapes model")
            raw = sidecar_path(source).read_bytes()
            value = json.loads(raw)
            validate_sidecar(value)
            if (base / value["source"]["unit"]).resolve() != source.resolve():
                raise ValueError("sidecar source mismatch")
            if value["benchmark_id"] != BENCHMARKS[bench]:
                raise ValueError("sidecar benchmark mismatch")
            validate_artifact_integrity(value, base)
            value, _ = apply_model_identity(value, mapping)
            value["_stats_sidecar_sha256"] = hashlib.sha256(raw).hexdigest()
            values.append(value)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            raise SelectionError("invalid sidecar/artifacts", [{"source": str(source.relative_to(base))}]) from exc
    return values


def read_run(base, run, bench, manifest_directory=None):
    """반복 원본을 읽고 sidecar가 인증한 바이트와 manifest를 확인해 채점한다."""
    base = Path(base).resolve()
    source = (base / run["source"]["unit"]).resolve()
    rows, dataset, hashes = read_session(source)
    artifacts = {(base / v["path"]).resolve(): v["sha256"] for v in run["source"]["artifacts"]}
    if any(artifacts.get(source / name) != "sha256:" + sha for name, sha in hashes.items()):
        raise SelectionError("session bytes not bound by sidecar", candidates([run]))
    manifest, manifest_sha = load_manifest(bench, dataset.get("revision"), manifest_directory)
    if dataset.get("huggingface_id") != manifest["dataset"]:
        raise SelectionError("session dataset mismatch", candidates([run]))
    scores = score_items(bench, rows, manifest)
    evidence = {"source": run["source"]["unit"], "session": run.get("session"),
                "input_sha256": hashes, "sidecar_sha256": run["_stats_sidecar_sha256"],
                "manifest_sha256": manifest_sha, "revision": manifest["revision"]}
    return scores, evidence


def load_cohort(base, model_dir, bench, fingerprint=None, manifest_directory=None):
    """선택한 모든 반복을 채점·평균하고 선택 및 파일 근거를 붙인다."""
    representative = choose_cohort(read_sidecars(base, model_dir, bench), fingerprint)
    selection = representative["_selection"]
    scores, evidence = [], []
    for run in selection["cohort_runs"]:
        try:
            result, proof = read_run(base, run, bench, manifest_directory)
            scores.append(result)
            evidence.append(proof)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            raise SelectionError("invalid cohort run", candidates([run])) from exc
    return {**average_runs(scores), "cohort": list(cohort_key(representative)[:3]),
            "model": canonical_model_id(representative), "runs": evidence,
            "folded_duplicates": selection["folded_duplicates"]}


def check_comparison(a, b):
    """비교 불가능하면 양쪽 후보 근거와 함께 거부한다."""
    try:
        validate_pair(a, b)
    except ValueError as exc:
        evidence = [{"model": v["model"], "cohort": v["cohort"], "metric": v["metric"],
                     "repetitions": v["repetitions"], "runs": [r["source"] for r in v["runs"]]}
                    for v in (a, b)]
        raise SelectionError(str(exc), evidence) from exc


def read_collected_run(base, run, bench, manifest_directory=None):
    """collect가 준 실행을 디스크 sidecar에 다시 바인딩하여 점수·SHA 근거를 읽는다."""
    # collect는 모델 정체성·경고만 갱신한다. 보고서의 전역 선택을 폴더별로 재수집하지 않는다.
    base = Path(base).resolve()
    source = (base / run["source"]["unit"]).resolve()
    if not source.is_relative_to(base / "results") or source.name != bench:
        raise SelectionError("invalid collected source")
    try:
        raw = sidecar_path(source).read_bytes()
        saved = json.loads(raw)
        validate_sidecar(saved)
        ignored = {"model_identity", "warnings", "_stats_sidecar_sha256"}
        if ({k: v for k, v in saved.items() if k not in ignored}
                != {k: v for k, v in run.items() if k not in ignored}):
            raise SelectionError("collected sidecar changed")
        bound = {**run, "_stats_sidecar_sha256": hashlib.sha256(raw).hexdigest()}
        return read_run(base, bound, bench, manifest_directory)
    except (OSError, ValueError) as exc:
        raise SelectionError("collected run failed validation", candidates([run])) from exc
