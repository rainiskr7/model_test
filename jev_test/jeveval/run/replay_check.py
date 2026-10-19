"""무엇: 순수 replay 선검사 · 입력: fingerprint·시도·경고 · 출력: 오류 목록 · 계약 §5-5c."""


def compatible(source, current):
    """코드·환경·run 식별자·시각만 달라질 수 있으며 나머지 필드는 닫혀 있다."""
    if not isinstance(source, dict) or source.keys() != current.keys():
        return ["fingerprint fields differ"]
    if source.get("schema") != "fingerprint/1":
        return ["invalid fingerprint schema"]
    old, new = source.get("inputs"), current["inputs"]
    if not isinstance(old, dict) or old.keys() != new.keys():
        return ["fingerprint input fields differ"]
    errors = []
    if old.get("run_id") != source.get("run_id"):
        errors.append("source run identity differs")
    allowed = {"code_sha256", "env", "run_id", "started_at", "inputs"}
    errors.extend(key + " differs" for key in current if key not in allowed and source[key] != current[key])
    errors.extend("inputs." + key + " differs" for key in new if key != "run_id" and old[key] != new[key])
    return errors


def complete_attempts(attempts, warnings):
    """파일은 비어 있거나 끝이 끊기면 안 된다. 논리 요청의 미완료는 허용한다."""
    return (["source attempts empty"] if not attempts else []) + (["source attempts pending"] if warnings else [])


def check_reason(reason):
    """공개 사유는 선택적인 200자 이하 한 줄이며 제어 문자를 허용하지 않는다."""
    return ([] if reason is None or isinstance(reason, str) and len(reason) <= 200
            and not any(ord(c) < 32 or ord(c) == 127 or c in "\u0085\u2028\u2029" for c in reason)
            else ["invalid replay reason"])
