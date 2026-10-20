"""입력: CLI가 수집한 sidecar 범위·base·선언 YAML. 출력: 검증·채점한 부록 입력과 Markdown."""

from math import fsum
from pathlib import Path
import re

from shared.multimodal.publish.report import _display_cohorts
from shared.multimodal.publish.schema import canonical_model_id
from shared.multimodal.publish.select import cohort_key, select_representatives
from shared.multimodal.rescore.conditions_section import render_conditions
from shared.multimodal.rescore.report_section import render_section
from shared.stats.item_scores import METRICS, average_runs
from shared.stats.report_pairs import compare_pairs, render_pairs
from shared.stats.selection import BENCHMARKS, SelectionError, choose_cohort, read_collected_run


class ConfigError(ValueError):
    """원문이나 비밀 값을 포함하지 않는 선언 검증 오류."""


def read_yaml(path, optional=False):
    """YAML을 읽되 누락 가능한 서빙 선언만 빈 목록으로 처리한다."""
    import yaml

    try:
        return yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        if optional:
            return []
        raise ConfigError("paired YAML missing") from exc
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ConfigError("invalid report YAML") from exc


def valid_name(value):
    """결과 폴더·세션을 가리키는 단일 경로 성분인지 반환한다."""
    return isinstance(value, str) and ".." not in value and bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value))


def validate_pairs(value):
    """쌍 목록의 구조·벤치·경로·중복(역방향 포함)을 검증한다."""
    if not isinstance(value, list):
        raise ConfigError("paired YAML must be a list")
    seen = set()
    for row in value:
        if not isinstance(row, dict) or set(row) != {"a", "b", "bench"}:
            raise ConfigError("pair requires exactly a, b, bench")
        if not all(valid_name(row[k]) for k in ("a", "b")) or row["a"] == row["b"]:
            raise ConfigError("pair model paths must be distinct directory names")
        if not isinstance(row["bench"], str) or row["bench"] not in METRICS:
            raise ConfigError("unsupported paired benchmark")
        key = (*sorted((row["a"], row["b"])), row["bench"])
        if key in seen:
            raise ConfigError("duplicate pair")
        seen.add(key)
    return value


def validate_conditions(value):
    """모델·명시 세션·근거가 있는 서빙 선언만 허용한다."""
    if not isinstance(value, list):
        raise ConfigError("serving YAML must be a list")
    seen = set()
    for row in value:
        if not isinstance(row, dict) or set(row) != {"model", "sessions", "generation_config", "evidence"}:
            raise ConfigError("serving declaration requires model, sessions, generation_config, evidence")
        if any(not isinstance(row[k], str) or not row[k].strip() for k in ("model", "evidence")):
            raise ConfigError("serving model and evidence required")
        if row["generation_config"] not in ("vllm", "auto"):
            raise ConfigError("generation_config must be vllm or auto")
        if not isinstance(row["sessions"], list) or not row["sessions"] or not all(map(valid_name, row["sessions"])):
            raise ConfigError("explicit serving sessions required")
        for session in row["sessions"]:
            key = row["model"], session
            if key in seen:
                raise ConfigError("duplicate serving model/session")
            seen.add(key)
    return value


def scope_sidecars(sidecars, comparison_sidecars=None):
    """render_markdown과 같은 strict 코호트 범위를 반환하며 추가 수집하지 않는다."""
    if comparison_sidecars is None:
        return sidecars
    keys = {cohort_key(v) for v in sidecars if v.get("publishable")}
    return [v for v in comparison_sidecars if v.get("publishable") and cohort_key(v) in keys]


def score_cohort(base, representative, cache):
    """선택기의 반복 전체를 읽어 두 지표 평균과 SHA·대표 출처를 반환한다."""
    bench = next(k for k, v in BENCHMARKS.items() if v == representative["benchmark_id"])
    runs = representative["_selection"]["cohort_runs"]
    scores, proofs, old = [], [], []
    for run in runs:
        key = run["source"]["unit"]
        if key not in cache:
            cache[key] = read_collected_run(base, run, bench)
        score, proof = cache[key]
        scores.append(score)
        proofs.append(proof)
        axis = next(v for v in run["metrics"]["axes"] if v["name"] == "overall")
        old.append(axis["numerator"] / axis["denominator"])
    averaged = average_runs(scores)
    return {**averaged, "cohort": list(cohort_key(representative)[:3]),
            "model": canonical_model_id(representative), "runs": proofs,
            "representative": representative["source"]["unit"],
            "folded_duplicates": representative["_selection"]["folded_duplicates"],
            "old_mean": fsum(old) / len(old),
            "new_mean": fsum(v["score"] for v in averaged["items"]) / len(averaged["items"])}


def folder_matches(base, run, folder, bench):
    """sidecar의 source가 지정 모델 폴더·벤치에 속하는지 판정한다."""
    path = Path(run["source"]["unit"])
    if path.is_absolute():
        try:
            path = path.relative_to(Path(base).resolve())
        except ValueError:
            return False
    return len(path.parts) >= 3 and path.parts[:2] == ("results", folder) and path.name == bench


def build_inputs(base, sidecars, comparison_sidecars=None, pairs_path=None):
    """같은 수집 범위에서 전체 표시·비교를 구성하고 검증 거부만 진단으로 남긴다."""
    pair_file = pairs_path or Path(__file__).resolve().parents[3] / "reports/paired_pairs.yaml"
    pairs = validate_pairs(read_yaml(pair_file))
    declarations = validate_conditions(read_yaml(Path(base) / "configs/serving_conditions.yaml", optional=True))
    scoped = scope_sidecars(sidecars, comparison_sidecars)
    selected, ambiguous = select_representatives(scoped)
    official, rejected, cache = [], [], {}
    for _, group in _display_cohorts(selected):
        for representative in sorted(group, key=canonical_model_id):
            if representative["benchmark_id"] not in ("K-MMBench", "MTVQA-KR"):
                continue
            try:
                official.append(score_cohort(base, representative, cache))
            except SelectionError as exc:
                rejected.append({"model": canonical_model_id(representative),
                                 "cohort": list(cohort_key(representative)[:3]), "reason": str(exc)})
    for entry in ambiguous:
        if entry["key"][0] in ("K-MMBench", "MTVQA-KR"):
            rejected.append({"model": entry["key"][3], "cohort": list(entry["key"][:3]),
                             "reason": "대표 선택 모호"})
    paired_cohorts = {}
    for folder, bench in sorted({(p[s], p["bench"]) for p in pairs for s in ("a", "b")}):
        candidates = [v for v in scoped if folder_matches(base, v, folder, bench)]
        try:
            if candidates and not any(v.get("publishable") for v in candidates):
                raise SelectionError("범위 내 발행 가능 코호트 없음 (REJECTED/비발행)")
            paired_cohorts[folder, bench] = score_cohort(base, choose_cohort(candidates), cache)
        except SelectionError as exc:
            paired_cohorts[folder, bench] = exc
    return {"official": official, "rejected": rejected, "selected": selected,
            "pairs": compare_pairs(pairs, paired_cohorts), "declarations": declarations}


def build_appendix(base, sidecars, comparison_sidecars=None):
    """보고서 CLI용 IO 조정자: 모든 검증·계산을 완료한 뒤 부록 문자열을 반환한다."""
    value = build_inputs(base, sidecars, comparison_sidecars)
    return "\n".join((render_section(value["official"], value["rejected"]),
                      render_pairs(value["pairs"]),
                      render_conditions(value["selected"], value["declarations"])))
