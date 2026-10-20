"""무엇: 역사 run 보고 조립 · 입력: 실행 ID·모델·명시 비교 · 출력: Markdown · 계약 §5-1b·7-6."""

from dataclasses import replace

from jeveval.io import audit_evidence as audit_io, history, report_inputs, report_markdown, run_files
from jeveval.io.paths import identifier, inside
from jeveval.run import auxiliary_report, history_check, history_stage, layout, question_report
from jeveval.score.kosgd_decompose import decompose
from jeveval.score.set_metrics import metric_spec
from jeveval.score.report_extras import comparison, supplementary
from jeveval.score.report_tables import common_errors, variant
from jeveval.types.report import Report, ReportComparison, ReportVariant


def _variant(root, directory):
    saved = history.read(root, directory)
    checked = history_check.check(saved)
    try:
        family, primary = report_inputs.metadata(root, directory.parts[-2], directory.name)
    except (ValueError, KeyError, OSError):
        family, primary = None, None
    result = variant(saved, checked, primary)
    if result.status == "damaged":
        return result
    decompositions, notes, registration = [], [], "exploratory"
    if metric_spec(family).kosgd_decompose and result.variant == "full":
        for stage in checked.stages:
            if stage.status != "verified_complete":
                continue
            try:
                data = history_stage.restore(root, saved, stage.name)
                valid = [f for f in data.finals if f.status == "ok"]
                decompositions.append(decompose(valid, data.items, stage.name))
            except (ValueError, KeyError, TypeError, OSError):
                notes.append("분해 불가: 역사 입력 또는 요청 바이트 검증 불가")
    if result.status == "verified_complete" and "question_risk.json" in saved.artifacts:
        try:
            value = saved.artifacts["question_risk.json"]
            registration = question_report.status(root, saved, value)
            if registration == "registration_damaged":
                notes.append("registration_damaged — 질문 위험 수치 비공개")
            else:
                notes += supplementary(value)
        except (ValueError, KeyError, TypeError):
            notes.append("질문 위험 표 검증 실패 — 수치 비공개")
    result = replace(result, decompositions=decompositions, supplementary=notes, supplementary_status=registration)
    return auxiliary_report.attach(root, saved, result)


def run(*, root, run_id, models, results="results", compare_id=None, out=None, note_unrun=None, audit_evidence=None):
    audits = audit_io.overrides(root, audit_evidence)
    run_id = identifier(run_id)
    models = [identifier(m) for m in models]
    if not models or len(models) != len(set(models)):
        raise ValueError("unique nonempty models required")
    comparisons = [identifier(c) for c in compare_id or []]
    unrun = [identifier(m) for m in note_unrun or []]
    target = report_inputs.output(root, out or layout.report_path(inside(root, results), run_id))
    if run_files.exists(target):
        raise ValueError("report output already exists; use a new filename")
    variants, audit_notes = [], []
    for model in models:
        directories = history.variants(root, results, model, run_id)
        variants.extend(_variant(root, directory) for directory in directories)
        for directory in directories:
            note = audit_io.summary(root, directory, audits.get(directory.parent.name))
            if note is not None and note not in audit_notes:
                audit_notes.append(note)
        if not directories:
            variants.append(ReportVariant(model, "unknown", "unknown", "incomplete", [], []))
    compared = []
    for cid in comparisons:
        for set_name, name in sorted({(v.set_name, v.variant) for v in variants if v.set_name != "unknown"}):
            value = report_inputs.compare(root, results, cid, set_name, name)
            if value is not None:
                participants = [v for v in variants if (v.set_name, v.variant) == (set_name, name)]
                if {v.model for v in participants if v.status == "verified_complete"} != set(models):
                    compared.append(ReportComparison(cid, set_name, name, ["비교 미표시: 참여 변형 검증 미완료"]))
                else:
                    compared.append(comparison(value, cid, models, set_name, name))
    report = Report(run_id, models, variants, compared, common_errors(variants), unrun, audit_notes)
    text = report_markdown.render(report)
    run_files.make_directory(target.parent)
    run_files.write_text(target, text)
    return dict(ok=True, variants=len(variants), damaged=sum(v.status == "damaged" for v in variants))
