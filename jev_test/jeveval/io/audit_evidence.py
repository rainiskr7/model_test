"""무엇: 명시 감사 증거 읽기 · 입력: root/run/선택 경로 · 출력: 출처 포함 감사 줄 · 계약 §7-6."""

from jeveval.io import derived_stage, run_files
from jeveval.contract.stages import stage_names
from jeveval.io.models import load_model_config
from jeveval.io.hashes import sha256_file
from jeveval.io.paths import inside, identifier
from jeveval.score.audit_selection import RULES, STATES, select_derived_audit_evidence
from jeveval.score.derived_provenance import check_derived_origin, source_calls_match


def overrides(root, values):
    """중복 set과 감사 출력 디렉터리 밖 경로는 보고 쓰기 전에 거부한다."""
    result = {}
    base = inside(root, "audits/audit_v4/out")
    for value in values or []:
        name, separator, path = value.partition("=")
        identifier(name)
        target = inside(root, path)
        if not separator or name in result or not target.is_relative_to(base) or target.suffix != ".json":
            raise ValueError("invalid explicit audit evidence")
        result[name] = target
    return result


def summary(root, directory, selected=None):
    """기본 파일 또는 명시된 한 파일만 읽으며 다른 판을 자동 탐색하지 않는다."""
    name = directory.parent.name
    if name not in ("kosgd", "kosgd2") and selected is None:
        return None
    path = inside(root, selected or f"audits/audit_v4/out/{name}.json")
    if not path.is_relative_to(inside(root, "audits/audit_v4/out")):
        raise ValueError("audit evidence outside output directory")
    if not run_files.exists(path):
        return None if selected is None else "미완·한계: 지정 감사 파일 없음 — 연결 미확인."
    try:
        fp = run_files.read_json(inside(root, directory / "fingerprint.json"))
        for key in ("model", "set", "variant", "run_id"):
            identifier(fp[key])
        value = run_files.read_json(path)
        # 옛 INCOMPLETE 감사에는 runs 자체가 없을 수 있다.
        if value.get("retrospective") is True and isinstance(value.get("historical_calls"), dict):
            value["historical_calls"].setdefault("runs", [])
        provenance = read_derived_provenance(root, directory, fp)
        selected = select_derived_audit_evidence(value, fp, provenance)
        return _summary(fp, value, selected, path.name, sha256_file(path))
    except (ValueError, OSError, KeyError, TypeError, AttributeError):
        return f"미완·한계: {directory.parent.name}/{directory.name} 감사 증거 연결 불가 — 연결 미확인."


def read_derived_provenance(root, directory, fp):
    """기존 stage 검사와 저장 호출 해시를 사용한다. 불완전 출처는 직접 연결 경로로 남긴다."""
    if fp["variant"] != "actions_only":
        return None
    try:
        model = inside(root, fp["inputs"]["model_cfg_path"])
        if sha256_file(model) != fp["files"][fp["inputs"]["model_cfg_path"]]:
            return None
        cfg = load_model_config(model)
        if cfg.question_scoring != "separate":
            return None
        source_dir = inside(root, directory.parent / "full")
        source_fp = run_files.read_json(source_dir / "fingerprint.json")
        for stage in stage_names(fp["set"]):
            rows = derived_stage.read_derived_stage(directory, stage)
            origin = check_derived_origin(rows.existing, rows.provenance, fp)
            if (origin is None or inside(root, origin) != source_dir or not rows.existing or
                    rows.warnings or rows.attempts or rows.pending):
                return None
            original = derived_stage.read_derived_stage(source_dir, stage)
            if original.warnings or original.pending or original.provenance is not None:
                return None
            if not source_calls_match(rows.existing, original.existing):
                return None
        return dict(fingerprint=source_fp, question_scoring=cfg.question_scoring)
    except (ValueError, OSError, KeyError, TypeError, AttributeError):
        return None


def _summary(fp, value, selected, filename, file_digest):
    """연결 실패는 규칙 수치를 숨기고 FAIL 규칙의 주장 범위도 분리한다."""
    label = "사후 감사" if value["retrospective"] else "감사"
    rules, digest, linked = (selected[k] for k in ("rules", "digest", "linked"))
    text = f"미완·한계: {fp['model']} {fp['set']}/{fp['variant']} {label} v4"
    text += f"; file={filename}; sha256={file_digest[:12]}; script={digest[:12]}."
    if value["retrospective"]:
        text += " 모델 실행 전 감사 증거로 소급하지 않는다."
    if not linked:
        return text + " 저장 호출과의 연결 미확인: 기존 실행 입력에 대한 뒷받침이 부족하다."
    if selected["kind"] == "derived":
        text += (" 파생 변형: 자체 전송 없음. 파생 출처 검증 PASS. 원천 full 저장 호출 연결 PASS."
                 " 이어지는 actions_only 규칙은 가상 직접 요청 감사이며 파생 판 자체 전송의 증거가 아님.")
    text += " " + ", ".join(f"{r}={rules[r]['status']}" for r in RULES) + ". 관측은 인증과 다르다."
    claims = dict(R2v3="8,192 이하 입력", R4="라벨·미래턴 비노출 및 원문 대응",
                  R5="정답 클래스 범위", R6="같은 턴 라벨 반영", R7="질문·정답 연결", v4_hash="실전 요청 일치")
    if selected["scope"] == "hypothetical_direct":
        claims["v4_hash"] = "가상 직접 요청 일치"
    failed = [claims[r] for r in RULES if rules[r]["status"] == "FAIL"]
    if failed:
        text += " 뒷받침이 부족한 결론: " + ", ".join(failed) + "."
    return text
