"""무엇: 주 지표 요약 · 입력: risk/1 · 출력: evalcommon summary · 계약 §8-3."""

from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


class _ReadOnlyLoader(SourceFileLoader):
    def set_data(self, path, data, **kwargs):
        """인접 저장소에는 bytecode 캐시도 쓰지 않는다."""


def summary_from_risk(*, risk: dict, model, set, variant, primary_variant: str, t0_status):
    if variant != primary_variant:
        return None
    cell = risk["cells"]["0.02"]
    if cell["tau"] != "0.02":
        raise ValueError("summary tau mismatch")
    coverage = cell["test"]["coverage"]
    score = (coverage["num"] / coverage["den"] if coverage["den"] and
             cell["status"] not in ("NO_THRESHOLD", "UNDERPOWERED") else 0.0)
    path = Path(__file__).resolve().parents[3] / "reranker_test/evalcommon/schema.py"
    spec = spec_from_file_location("_jev_evalcommon_schema", path,
                                  loader=_ReadOnlyLoader("_jev_evalcommon_schema", str(path)))
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.make_score_summary(benchmark=f"jev:{set}:{variant}", model=model,
        metric="coverage_at_risk_2pct", score=score, total=cell["test"]["n_denom"],
        extra={"status": cell["status"], "insufficient_by_design": cell["insufficient_by_design"],
               "t0_status": t0_status})
