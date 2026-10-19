"""무엇: 보고 대상 감사 증거 읽기/연결 · 입력: root/역사 폴더 · 출력: 안전한 문구 · 계약 판 5 보정 2 WP1."""

import re

from jeveval.io import run_files
from jeveval.io.paths import inside, identifier

RULES = ("R2v3", "R4", "R5", "R6", "R7", "v4_hash")
STATES = {"PASS", "FAIL", "INCOMPLETE", "NOT_APPLICABLE"}


def summary(root, directory):
    """파일 존재만으로 PASS를 표시하지 않는다. task/split/lists 해시는 run에 결합한다."""
    if directory.parent.name not in ("kosgd", "kosgd2"):
        return None
    if not run_files.exists(inside(root, f"audits/audit_v4/out/{directory.parent.name}.json")):
        return None
    try:
        fp = run_files.read_json(inside(root, directory / "fingerprint.json"))
        name = fp["set"]
        identifier(fp["variant"])
        identifier(fp["model"])
        if name not in ("kosgd", "kosgd2"):
            return None
        path = inside(root, f"audits/audit_v4/out/{name}.json")
        if not run_files.exists(path):
            return None
        value = run_files.read_json(path)
        if value["schema"] != "audit_v4/1" or value["set"] != name or value["profile"] != name:
            raise ValueError("audit identity")
        required = {fp["inputs"]["task_path"], f"configs/splits/{name}.json", "configs/tasks/b1.yaml"}
        required.update(p for p in fp["files"] if p.startswith("configs/tasks/lists/"))
        if any(value["inputs"]["files"].get(p) != fp["files"].get(p) or not fp["files"].get(p) for p in required):
            raise ValueError("audit inputs differ")
        digest = value["code"]["audit_sha256"]
        if not isinstance(digest, str) or re.fullmatch("[0-9a-f]{64}", digest) is None:
            raise ValueError("audit digest")
        model = value["models"][fp["model"]]["variants"][fp["variant"]]
        if model["measurement_config"]:
            raise ValueError("measurement-only model")
        rules = value["per_variant"][fp["variant"]]
        if any(rules[r]["status"] not in STATES for r in RULES):
            raise ValueError("audit states")
        return _summary(fp, value, rules, digest)
    except (ValueError, OSError, KeyError, TypeError, AttributeError):
        return "미완·한계: 감사 증거 연결 불가. 관측은 인증과 다르다."



def _summary(fp, value, rules, digest):
    """사후 근거를 정확한 run에 연결하고 실패 규칙의 주장 범위를 명시한다."""
    label = "사후 감사" if value["retrospective"] is True else "감사"
    text = f"미완·한계: {fp['set']}/{fp['variant']} {label} v4 " + ", ".join(f"{r}={rules[r]['status']}" for r in RULES)
    text += f"; script={digest[:12]}. 관측은 인증과 다르다."
    if label == "사후 감사":
        text += " 모델 실행 전 감사 증거로 소급하지 않는다."
        linked = [r for r in value["historical_calls"].get("runs", []) if
                  all(r.get(k) == fp[k] for k in ("model", "variant", "run_id"))]
        if not linked or any(r["status"] != "PASS" for r in linked):
            text += " 저장 호출과의 연결 미확인: 기존 실행 입력에 대한 뒷받침이 부족하다."
    claims = dict(R2v3="8,192 이하 입력", R4="라벨·미래턴 비노출 및 원문 대응",
                  R5="정답 클래스 범위", R6="같은 턴 라벨 반영", R7="질문·정답 연결", v4_hash="실전 요청 일치")
    failed = [claims[r] for r in RULES if rules[r]["status"] == "FAIL"]
    if failed:
        text += " 뒷받침이 부족한 결론: " + ", ".join(failed) + "."
    return text
