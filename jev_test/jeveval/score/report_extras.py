"""무엇: 비교·질문 위험 공개 투영 · 입력: 파일 schema · 출력: 안전한 통계 문자열 · 계약 §7-6."""

from jeveval.score.report_tables import safe_id
from jeveval.score.threshold import TAUS
from jeveval.types.report import ReportComparison


def number(value):
    if value is None:
        return "—"
    if type(value) not in (int, float):
        raise ValueError("expected public number")
    return str(value) if type(value) is int else f"{value:.4f}"


def _pairs(value, title):
    lines = []
    for pair in value["pairs"]:
        models = "/".join(safe_id(m) for m in pair["models"])
        ci = "—" if pair["ci95"] is None else "/".join(number(v) for v in pair["ci95"])
        lines.append(f"{title} {models}: 차이={number(pair['estimate'])}; CI95={ci}")
    return lines


def comparison(value, compare_id, models, set_name, variant):
    if value.get("schema") != "compare/1" or set(value["models"]) != set(models):
        raise ValueError("comparison models/schema mismatch")
    if value["set"] != set_name or value["variant"] != variant:
        raise ValueError("comparison identity mismatch")
    lines = _pairs(value["bootstrap"]["coverage"]["0.02"], "τ=0.02 처리율(전체 test 대표 분모)")
    for qid, stats in value["bootstrap"]["f1"]["test"].items():
        lines += _pairs(stats, f"공통 ok 코호트 F1 {safe_id(qid)}")
    return ReportComparison(safe_id(compare_id), safe_id(set_name), safe_id(variant), lines)


def supplementary(value):
    if value.get("schema") != "question_risk/1" or value["registration"]["status"] not in ("exploratory", "registered"):
        raise ValueError("unsupported supplementary registration")
    lines = [f"registration.status={value['registration']['status']}; 질문별 주변적 95% 상한, 동시 보장 아님"]
    for table in ("questions", "diagnostic"):
        for qid, stats in value[table].items():
            safe_id(qid)
            for tau in TAUS:
                cell = stats["by_tau"][tau]
                if cell["status"] not in ("MEETS", "FAILS", "UNDERPOWERED", "NO_THRESHOLD"):
                    raise ValueError("invalid supplementary status")
                values = "/".join(number(cell[k]) for k in ("t_star", "n_accepted", "k_errors", "U"))
                coverage = cell["coverage"]
                lines.append(f"{table} {qid} τ={tau}: {cell['status']}; t/n/k/U={values}; 처리={number(coverage['num'])}/{number(coverage['den'])}")
    return lines
