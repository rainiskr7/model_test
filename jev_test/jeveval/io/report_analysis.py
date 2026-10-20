"""무엇: 보조 절 렌더 · 입력: 검증된 보고 타입 · 출력: Markdown 줄 · 계약 §7-6."""


def _number(value):
    return "—" if value is None else str(value) if type(value) is int else f"{value:.6g}"


def selective(value):
    """질문 단위 절과 분리하며 부분 적분의 최대 처리율을 함께 표시한다."""
    lines = ["", "선택적 예측(보조, 인증과 별개)", f"보조 상태: {value.status}"]
    if value.metrics is None:
        lines.append("보조 지표 없음" if value.status == "missing" else "보조 지표 검증 실패 — 수치 비공개")
    else:
        m = value.metrics
        lines += [f"부분 AURC: {_number(m['partial_aurc'])}; 최대 처리율: {_number(m['max_coverage'])}; AUROC: {_number(m['auroc'])}",
                  f"분모: {m['n_denom']}; 유효: {m['n_valid']}; 무효: {m['n_invalid']}",
                  "", "| 격자 | 실제 coverage | risk |", "|---|---|---|"]
        lines += [f"| {c['target']} | {_number(c['coverage'])} | {_number(c['risk'])} |" for c in m["grid"]]
    lines += ["", "관측 n에 조건부인 가정상 통과 확률", "", "| τ | 가정 위험 r | 통과 확률 |", "|---|---|---|"]
    lines += [f"| {tau} | {_number(c['r'])} | {_number(c['probability'])} |"
              for tau, cells in value.power.items() for c in cells]
    return lines


def score_variants(value):
    """후보별 선택 근거와 test 상태를 별도 등록 지위로 표시한다."""
    title = {"registered": "등록", "exploratory": "탐색적", "registration_damaged": "등록 손상",
             "missing": "미산출", "unsupported": "미지원"}[value.status]
    lines = ["", f"확신 변형({title}; 주 지표 인증과 별개)"]
    if value.note:
        lines.append(value.note)
    if value.cells:
        lines += ["", "| τ | 후보 | dev n/k | test 상태 | test n/k | U |", "|---|---|---|---|---|---|"]
        for tau, c in value.cells.items():
            d, t = c["dev"], c["test"]
            lines.append(f"| {tau} | {c['candidate']} | {_number(d['n_accepted'])}/{_number(d['k_errors'])} | "
                         f"{t['status']} | {_number(t['n_accepted'])}/{_number(t['k_errors'])} | {_number(t['U'])} |")
    return lines
