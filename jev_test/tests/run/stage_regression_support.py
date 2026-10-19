"""무엇: 단계 회귀 관측 · 입력: 합성 완료 run · 출력: 경계별 판정/분모 · 계약 §6-1·§9 C6."""

from dataclasses import asdict
from types import SimpleNamespace

from jeveval.io import archive, history, run_files
from jeveval.run import cmd_compare, cmd_report, context, history_check, summary
from tests.run import cli_support
from tests.run.compare_support import pair


def isolated_external(monkeypatch):
    """변경 밖 evalcommon 경계만 합성한다. 인접 저장소 파일은 읽지 않는다."""
    def add_external(root):
        target = root.parent / "reranker_test/evalcommon/schema.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# synthetic external identity for stage regression\n")
        return target

    def make_score_summary(*, benchmark, model, metric, score, total, extra):
        return dict(benchmark=benchmark, model=model, metric=metric, score=score, total=total, **extra)

    monkeypatch.setattr(cli_support, "add_external", add_external)
    monkeypatch.setattr(summary, "_evalcommon_schema", lambda: SimpleNamespace(make_score_summary=make_score_summary))


def observed(root, monkeypatch, name):
    """실제 실행·채점 후 history/report/archive/compare가 보는 단계와 모집단을 추출한다."""
    isolated_external(monkeypatch)
    first, second = pair(root, monkeypatch, name)
    ctx, stages, threshold = context.completed(root, first.directory)
    scores = run_files.read_json(first.directory / "scores.json")
    risk = run_files.read_json(first.directory / "risk.json")
    checked = history_check.check(history.read(root, first.directory))
    report = cmd_report._variant(root, first.directory)
    cmd_compare.run(root=root, run_dirs=[first.directory, second.directory], compare_id="c1")
    comparison = run_files.read_json(root / "results/_compare/c1/A" / name / "default/compare.json")
    value = dict(context_stages=list(stages), history=asdict(checked),
                 score_populations=scores["populations"], cost_stages=list(scores["cost"]),
                 threshold={k: v.to_dict() for k, v in threshold.by_tau.items()}, risk=risk["cells"],
                 report=dict(status=report.status, stages=[asdict(s) for s in report.stages],
                             risks=[asdict(r) for r in report.risk]),
                 archive_members=sorted(archive.entries_for(root, [ctx])), compare=comparison)
    return first, value
