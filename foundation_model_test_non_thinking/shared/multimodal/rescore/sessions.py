"""입력: 결과 루트·벤치 경로·출력 경로. 출력: 읽은 세션·SHA 또는 외부 JSON."""

import hashlib
import json
from pathlib import Path
import subprocess

from shared.jsonwrite.atomic_json import write_json_atomic

BENCHES = ("k_mmbench", "mtvqa_kr")


def discover_sources(base, benches=BENCHES):
    """결과 트리를 읽어 대상 벤치의 원본 results.json 부모 경로를 반환한다."""
    return sorted({p.parent for p in (Path(base) / "results").rglob("results.json")
                   if p.parent.name in benches and "_derived" not in p.parts}, key=str)


def read_session(source):
    """벤치 경로의 원본 두 파일을 한 번씩 읽고 객체와 SHA를 반환한다."""
    source = Path(source)
    values, hashes = {}, {}
    for name in ("results.json", "summary.json"):
        raw = (source / name).read_bytes()
        values[name] = json.loads(raw)
        hashes[name] = hashlib.sha256(raw).hexdigest()
    rows, summary = values["results.json"], values["summary.json"]
    if not isinstance(rows, list) or not isinstance(summary, dict):
        raise ValueError("invalid session JSON shape")
    config = summary.get("run_config")
    if not isinstance(config, dict) or not isinstance(config.get("dataset"), dict):
        raise ValueError("invalid session dataset metadata")
    dataset = config["dataset"]
    return rows, dataset, hashes


def check_revisions(base, bench, revision):
    """git 추적 summary를 읽어 모든 저장 revision의 일치 여부와 건수를 반환한다."""
    result = subprocess.run(["git", "-C", str(base), "ls-files", "-z", "--", "results/"],
                            capture_output=True)
    if result.returncode:
        raise ValueError("cannot read tracked summary list")
    paths = [Path(base) / p for p in result.stdout.decode().split("\0")
             if p.endswith(f"/{bench}/summary.json")]
    if not paths:
        raise ValueError("no tracked dataset revisions")
    for path in paths:
        _, dataset, _ = read_session(path.parent)
        if dataset.get("revision") != revision:
            raise ValueError("tracked dataset revision mismatch")
    return len(paths)


def validate_output(path, base, sources=()):
    """출력 경로가 운영 디렉터리·입력 벤치 안이면 쓰기 전에 거부한다."""
    target = Path(path).absolute()
    resolved = target.resolve()
    if any(part in {"results", "data", "logs"} for p in (target, resolved) for part in p.parts):
        raise ValueError("output must be outside results/data/logs")
    roots = (Path(base), Path(__file__).resolve().parents[3])
    protected = [root / name for root in roots for name in ("results", "data", "logs")]
    protected.extend(Path(source) for source in sources)
    if any(resolved.is_relative_to(root.resolve()) for root in protected):
        raise ValueError("output must be outside operational inputs")
    return resolved


def write_output(path, value, base, sources=()):
    """검증된 외부 경로에 키 순서가 고정된 JSON을 원자적으로 쓴다."""
    target = validate_output(path, base, sources)
    ordered = json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False))
    write_json_atomic(target, ordered)


def rescore_source(source, manifest_directory=None):
    """세션과 고정 manifest를 읽어 순수 채점 결과에 입력 근거를 붙인다."""
    from shared.multimodal.rescore.kmmbench_circular import score as circular_score
    from shared.multimodal.rescore.manifest import load_manifest
    from shared.multimodal.rescore.mtvqa_lmms import score as mtvqa_score

    source = Path(source)
    rows, dataset, hashes = read_session(source)
    manifest, manifest_sha = load_manifest(source.name, dataset.get("revision"), manifest_directory)
    if dataset.get("huggingface_id") != manifest["dataset"]:
        raise ValueError("session dataset mismatch")
    scorer = circular_score if source.name == "k_mmbench" else mtvqa_score
    return {"source": source.as_posix(), "revision": manifest["revision"],
            "input_sha256": hashes, "manifest_sha256": manifest_sha, **scorer(rows, manifest)}
