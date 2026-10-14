"""세션의 이미지 결과 JSON을 schema와 legacy 키로 검사한다."""

import json
import sys
from pathlib import Path


def iter_result_files(session):
    # 이 스크립트가 만든 이미지 결과(vision/)만 검사한다. 세션 전체를 훑으면 같은 세션의 언어 트랙
    # (예: Qwen 의 solo taubench 는 템플릿 거부로 늘 발행 불가)을 잡아 이미지 시험을 매번 실패로 끝낸다.
    for path in (session / 'vision').rglob('*.json'):
        if '_derived' in path.parts:
            continue
        if path.name in ('run_config.json', 'runs.json'):
            continue
        yield path


def check_file(path, rel, model_name, schema):
    failures = []
    warnings = []
    try:
        d = json.loads(path.read_text())
    except Exception:
        return failures, warnings

    if schema is not None and isinstance(d, dict):
        detect_and_validate, diagnostic_warnings, publish_status_error = schema
        warnings.extend(f"  [warning] {msg}" for msg in diagnostic_warnings(d, str(rel)))
        gate_error = publish_status_error(
            d, str(rel), allow_clean_unscored=(path.parent.name == "koffvqa"),
        )
        if gate_error:
            failures.append(f"  [publish] {gate_error}")
            return failures, warnings

        # 1차: schema 검증 (새 bench 표준)
        kind, msg = detect_and_validate(d, str(rel))
        if msg:
            failures.append(f"  [{kind}] {msg}")
            return failures, warnings
        if kind != "unknown":
            return failures, warnings  # schema 통과 → legacy 검사 skip

    # 2차: legacy fallback (키 기반 — KRETA 같은 비표준 구조 등)
    if isinstance(d, dict):
        for k in ("total", "count", "n_samples", "num_samples"):
            v = d.get(k)
            if isinstance(v, (int, float)) and v == 0:
                failures.append(f"  {rel}: {k}=0")
                break
        # KRETA results.json 의 모델별 키 구조에서 stale key 탐지
        if path.parent.name == "kreta" and path.name == "results.json":
            stale = [k for k in d.keys() if not k.startswith(model_name)]
            if stale:
                failures.append(f"  {rel}: stale model key {stale}")
    return failures, warnings


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    session = Path(argv[0])
    model_name = argv[1]
    benches_dir = Path(argv[2])

    # schema-aware validation (Pydantic 기반 — _schema.py 가 있으면 활용)
    # 예외: 지정 폴더에 _schema가 없으면 legacy 검사로 돌아가는 계약을 유지한다.
    sys.path.insert(0, str(benches_dir))
    try:
        from _schema import detect_and_validate, diagnostic_warnings, publish_status_error
        schema = detect_and_validate, diagnostic_warnings, publish_status_error
    except Exception as e:
        print(f"[sanity] schema module 로드 실패 ({e}) — legacy 키 검사만")
        schema = None

    failures = []
    warnings = []
    if not session.exists():
        print(f"[sanity] WARN: session dir 없음 {session}")
        return 0

    for path in iter_result_files(session):
        file_failures, file_warnings = check_file(
            path, path.relative_to(session), model_name, schema,
        )
        failures.extend(file_failures)
        warnings.extend(file_warnings)

    if warnings:
        print(f"[sanity] {len(warnings)} 건의 비치명 경고:")
        for w in warnings:
            print(w)
    if failures:
        print(f"[sanity] {len(failures)} 건의 실패 결과:")
        for failure in failures:
            print(failure)
        return 1
    else:
        print("[sanity] OK — 치명적 결과 없음")
        return 0


if __name__ == "__main__":
    # 기존 `python -`처럼 cwd를 검색한다. 잘못된 benches_dir를 이 파일의 경로로 보완하지 않는다.
    sys.path[0] = ""
    sys.exit(main())
