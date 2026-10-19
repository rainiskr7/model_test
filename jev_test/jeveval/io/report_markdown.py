"""무엇: 공개 Markdown 렌더 · 입력: Report dataclass · 출력: 문자열 · 계약 §7-6; 파일 I/O 없음."""


def _number(value):
    if value is None:
        return "—"
    if type(value) not in (int, float):
        raise ValueError("numeric public statistic required")
    return str(value) if type(value) is int else f"{value:.4f}"


def _variant(v):
    lines = [f"### {v.model} / {v.set_name} / {v.variant}", "", f"상태: {v.status}; primary={v.primary}"]
    if v.status == "damaged":
        return lines + ["검증 실패: " + ", ".join(v.reasons), ""]
    lines += [f"code_sha256: {v.code_sha256}; started_at: {v.started_at}", f"T0: {v.t0_status}", ""]
    for origin in v.replay:
        lines.append(f"replay {origin.stage}: {origin.source_run_id}; {origin.source_code_sha256}; {origin.source_attempts_sha256}")
    for stage in v.stages:
        statuses = ", ".join(f"{s}={n}" for s, n in sorted(stage.by_status.items()))
        lines.append(f"{stage.name}: {stage.status}; expected={_number(stage.expected)}, finalized={stage.finalized}, pending={_number(stage.pending)}; {statuses}")
    lines += ["", "| τ | status | accepted/den | k | U | 관측 처리율 | insufficient_by_design |", "|---|---|---|---|---|---|---|"]
    for r in v.risk:
        coverage = (r.accepted or 0) / r.denominator if r.denominator else None
        lines.append(f"| {r.tau} | {r.status} | {_number(r.accepted)}/{r.denominator} | {_number(r.errors)} | {_number(r.upper)} | {_number(coverage)} | {r.insufficient} |")
    if not v.risk:
        lines.append(f"| 0.01 / 0.02 / 0.05 | {v.status} | — | — | — | — | — |")
    if v.questions:
        lines += ["", "질문별 통계 모집단: test의 ok·정답 있는 코호트(전체 test support와 구별).", f"입력 질문 종류/성공 질문 종류(가변 셋은 합집합): {len(v.questions)}/{sum(q.role == 'success' for q in v.questions)}",
                  "", "| 질문 | role | acc | macro-F1 | ECE(p[answer]) | positive support/predicted/tp | 주석 |", "|---|---|---|---|---|---|---|"]
    for q in v.questions:
        note = "희소 양성 — 클래스별 해석 제한" if q.sparse else ""
        lines.append(f"| {q.question_id} | {q.role} | {q.numerator}/{q.denominator} | {_number(q.macro_f1)} | {_number(q.ece)} | {_number(q.support)}/{_number(q.predicted)}/{_number(q.tp)} | {note} |")
    for d in v.decompositions:
        lines += ["", f"KoSGD {d.stage}: " + ("개발 표본 진단" if d.stage == "dev" else "시험 표본 진단"),
                  f"정답/칸만/행동만/둘 다: {d.correct}/{d.slots_only}/{d.actions_only}/{d.both}",
                  "; ".join(f"{key}={n}" for key, n in d.errors.items()),
                  f"중복 중 유일 정답 일치: {d.duplicate_unique_match}", f"정답 수 × 예측 비NONE 칸 수: {d.grid}"]
    if v.supplementary:
        lines += ["", "질문 단위(탐색적; 주 지표 인증과 별개)", *v.supplementary]
    return lines + [""]


def render(report):
    lines = [f"# 실행 보고서 {report.run_id}", "", "모델: " + ", ".join(report.models), "",
             "주 지표: 검증 완료 산출물의 MEETS만 인증. FAILS·UNDERPOWERED·NO_THRESHOLD는 관측이다.",
             "희소 양성 기준 support < 30은 보고 주석이며 점수·역할을 바꾸지 않는다.", ""]
    for variant in report.variants:
        lines.extend(_variant(variant))
    for c in report.common_errors:
        lines.append(f"공통 오류 {c.left}/{c.right} {c.set_name}/{c.variant} {c.stage}: 공통 유효={c.common}, 제외={c.excluded_left}/{c.excluded_right}, 함께 오류={c.both_wrong}")
    for c in report.comparisons:
        lines += ["", f"비교 {c.compare_id} {c.set_name}/{c.variant}",
                  "연결 근거: 모델·셋·변형 일치 및 사용자의 정확한 compare ID 지정. run 동일성은 파일로 검증할 수 없음.", *c.lines]
    lines += ["", "미완·한계: 감사 v4 수행 증거 미확인(판 5 Phase A). 관측은 인증과 다르다.",
              "사용자가 지정한 미실행 모델: " + (", ".join(report.unrun) or "없음"),
              "판 4: API confidence 수락과 p[answer] 보정을 분리. 판 5: 역사 읽기·탐색적 질문 위험·kosgd2 사전 등록.", ""]
    return "\n".join(lines)
