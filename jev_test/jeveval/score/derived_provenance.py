"""무엇: 파생 출처 순수 검사 · 입력: marker/final/원천 지문 · 출력: 출처·연결 여부 · 계약 §7-6·9c."""

from pathlib import PurePosixPath


def check_derived_origin(finals, marker, fp):
    """역사 검사에서 공유하는 stage 출처 검사. 출처는 공개 문구에 그대로 내지 않는다."""
    origin = None if marker is None else marker["derived_from"]
    if any(f.derived_from != origin for f in finals):
        raise ValueError("derived provenance differs")
    if origin is not None:
        path = PurePosixPath(origin)
        if path.is_absolute() or ".." in path.parts or path.as_posix() != origin:
            raise ValueError("derived source path")
        if path.parts[-5:] != (fp["model"], fp["run_id"], "A", fp["set"], "full"):
            raise ValueError("derived source identity")
    return origin


def source_calls_match(finals, originals):
    """별도 전송 증거로 승격하지 않고 원천 호출 SHA의 부분집합만 확인한다."""
    source = {f.logical_id: f for f in originals}
    if len(source) != len(originals) or len(finals) != len(source) or set(source) != {f.logical_id for f in finals}:
        return False
    for final in finals:
        original = source[final.logical_id]
        calls = {c.call_id: c.request_sha256 for c in original.calls}
        if (len(calls) != len(original.calls) or len({c.call_id for c in final.calls}) != len(final.calls) or
                original.derived_from is not None or not final.calls or any(
                calls.get(c.call_id) != c.request_sha256 for c in final.calls)):
            return False
    return True


def source_identity_matches(fp, source):
    """파생 판과 같은 model/set/run의 full 원천인지 확인한다."""
    return source["variant"] == "full" and all(source[k] == fp[k] for k in ("model", "set", "run_id"))
