"""리랭커 평가 설정 — 계획안(../리랭커_모델_테스트_계획안.md)의 단일 진실 공급원(SSOT).

- 대상 리랭커: 2절(후보, 실행 전 확정)
- 1차 검색 임베딩(실행 인자): 1.3 개선안 — 임베딩×리랭커 궁합
- 태스크: 3-2절 한국어 4종 (native reranking vs retrieval 구분)
- 지표/설정: 4·6절

⚠️ 태스크 이름·성격(native reranking / retrieval)은 실행 전 `run.py verify` 로 확정한다(8절 게이트).
"""

from __future__ import annotations

from dataclasses import dataclass


# --------------------------------------------------------------------------- #
# 2절. 대상 리랭커 (후보 — 실행 전 사내 확정)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class RerankerSpec:
    key: str
    hf_name: str
    revision: str | None
    backend: str  # 스코어링 구현: "cross_encoder" | "causal_lm" (모델명 금지)
    uses_prompts: bool  # 권장 instruction/포맷 사용 여부
    notes: str = ""
    # causal_lm 백엔드용 — 전적으로 yaml 에서 온다(코드에 모델 특화 기본값 없음).
    #   prompt: {"prefix","suffix","instruct","body_template"}
    #   score_method: 예) "yes_no_softmax" (yes/no 토큰 로그릿 softmax)
    score_method: str = "yes_no_softmax"
    prompt: dict | None = None
    yes_token: str = "yes"
    no_token: str = "no"


SCORING_BACKENDS = ("cross_encoder", "causal_lm")


def _validate_backend(b: str, key: str) -> str:
    """스코어링 백엔드는 cross_encoder|causal_lm 만. 모델명을 backend 로 박는 것 금지."""
    if b not in SCORING_BACKENDS:
        raise ValueError(
            f"[config] '{key}' 의 local_backend='{b}' 는 허용되지 않음. "
            f"{SCORING_BACKENDS} 중 하나여야 함(모델별 차이는 yaml prompt/token 으로 표현).")
    return b


# 리랭커/임베더는 코드 하드코딩하지 않는다(모델 비종속). configs/models/*.yaml(리랭커) 와
# configs/embedders/*.yaml(1차 검색 임베더)가 SSOT 이며 아래 발견 로직이 import 시 스캔한다.
from pathlib import Path as _Path

_CONFIG_DIR = _Path(__file__).resolve().parents[1] / "configs" / "models"
_EMBEDDER_DIR = _Path(__file__).resolve().parents[1] / "configs" / "embedders"


def _yaml():
    try:
        import yaml
        return yaml
    except ImportError as e:
        raise RuntimeError("PyYAML 필요 — configs/*.yaml 로딩(requirements.txt).") from e


def _load_raw_rerankers() -> dict[str, dict]:
    """configs/models/*.yaml(class=reranker) 발견. 파싱오류/stem!=key/필수누락 → import 중단."""
    yaml = _yaml()
    if not _CONFIG_DIR.is_dir():
        raise RuntimeError(f"리랭커 config 디렉토리 없음: {_CONFIG_DIR}")
    out: dict[str, dict] = {}
    for path in sorted(_CONFIG_DIR.glob("*.yaml")):
        stem = path.stem
        try:
            cfg = yaml.safe_load(path.read_text())
        except Exception as e:
            raise RuntimeError(f"yaml 파싱 실패: {path}: {e}") from e
        if not isinstance(cfg, dict):
            raise RuntimeError(f"yaml 형식 오류(dict 아님): {path}")
        if cfg.get("class") != "reranker":
            raise RuntimeError(f"class 는 정확히 'reranker' 이어야 함({cfg.get('class')}): {path}")
        if cfg.get("key") != stem:
            raise RuntimeError(f"파일명 stem('{stem}') != yaml key('{cfg.get('key')}'): {path}")
        if not cfg.get("model"):
            raise RuntimeError(f"필수 'model' 없음: {path}")
        loc = cfg.get("local") or {}
        if not loc.get("hf_name"):
            raise RuntimeError(f"필수 'local.hf_name' 없음: {path}")
        if not cfg.get("local_backend"):
            raise RuntimeError(f"필수 'local_backend'(cross_encoder|causal_lm) 없음: {path}")
        b = _validate_backend(str(cfg["local_backend"]), stem)
        # causal_lm 의 모델 특화 동작은 yaml 이 전부 명시해야 한다(코드 기본 템플릿 없음).
        # 존재만이 아니라 '비어있지 않은 값'까지 검증(null/빈문자 통과 방지).
        if b == "causal_lm":
            def _nonempty_str(v) -> bool:
                return isinstance(v, str) and v.strip() != ""
            for f in ("yes_token", "no_token", "score_method"):
                if not _nonempty_str(loc.get(f)):
                    raise RuntimeError(f"causal_lm 'local.{f}' 는 비어있지 않은 문자열 필요: {path}")
            pr = loc.get("prompt")
            if not isinstance(pr, dict):
                raise RuntimeError(f"causal_lm 'local.prompt' 는 dict 필요: {path}")
            for k in ("prefix", "suffix", "instruct", "body_template"):
                if not _nonempty_str(pr.get(k)):
                    raise RuntimeError(f"causal_lm 'local.prompt.{k}' 는 비어있지 않은 문자열 필요: {path}")
            if "{query}" not in pr["body_template"] or "{document}" not in pr["body_template"]:
                raise RuntimeError(f"local.prompt.body_template 에 {{query}}/{{document}} 필요: {path}")
        out[stem] = cfg
    if not out:
        raise RuntimeError(f"리랭커 config 없음: {_CONFIG_DIR}/*.yaml")
    return out


_RAW_CONFIGS: dict[str, dict] = _load_raw_rerankers()


def _build_reranker_spec(cfg: dict) -> RerankerSpec:
    loc = cfg.get("local") or {}
    b = _validate_backend(str(cfg.get("local_backend", "cross_encoder")), cfg["key"])
    return RerankerSpec(
        key=cfg["key"], hf_name=loc["hf_name"], revision=loc.get("revision"),
        backend=b, uses_prompts=bool(loc.get("uses_prompts", b == "causal_lm")),
        notes=cfg.get("notes", ""), score_method=loc.get("score_method", "yes_no_softmax"),
        prompt=loc.get("prompt"), yes_token=loc.get("yes_token", "yes"),
        no_token=loc.get("no_token", "no"))


RERANKERS: dict[str, RerankerSpec] = {k: _build_reranker_spec(c) for k, c in _RAW_CONFIGS.items()}


# --------------------------------------------------------------------------- #
# 1차 검색 임베딩(실행 인자) — configs/embedders/*.yaml 발견. 정확히 하나가 default: true.
# --------------------------------------------------------------------------- #
def _load_embedders() -> tuple[dict[str, str], str]:
    yaml = _yaml()
    if not _EMBEDDER_DIR.is_dir():
        raise RuntimeError(f"1차 임베더 config 디렉토리 없음: {_EMBEDDER_DIR}")
    mapping: dict[str, str] = {}
    default: str | None = None
    for path in sorted(_EMBEDDER_DIR.glob("*.yaml")):
        cfg = yaml.safe_load(path.read_text())
        if not isinstance(cfg, dict) or cfg.get("key") != path.stem or not cfg.get("hf_name"):
            raise RuntimeError(f"임베더 yaml 오류(key==stem + hf_name 필요): {path}")
        mapping[path.stem] = str(cfg["hf_name"])
        if cfg.get("default"):
            if default is not None:
                raise RuntimeError(f"default: true 임베더가 둘 이상({default}, {path.stem})")
            default = path.stem
    if not mapping:
        raise RuntimeError(f"1차 임베더 config 없음: {_EMBEDDER_DIR}/*.yaml")
    if default is None:
        raise RuntimeError("default: true 임베더가 정확히 하나 필요")
    return mapping, default


FIRST_STAGE_EMBEDDERS, DEFAULT_EMBEDDER = _load_embedders()


# --------------------------------------------------------------------------- #
# 3절. 태스크 — kind 가 핵심:
#   "reranking" = MTEB native reranking 태스크(후보 내장) → 그대로 실행
#   "retrieval" = retrieval 태스크 → 1차 후보(top-N) 생성 후 rerank (2-stage)
# --------------------------------------------------------------------------- #
@dataclass
class TaskSpec:
    name: str
    kind: str            # "reranking" | "retrieval"
    primary_k: int       # 주 지표 k (계획안 표)
    primary_metric: str  # "ndcg" | "mrr" | "hit_rate@1" | "precision"
    domain: str = "general"
    subset: str | None = None  # 예: AutoRAG 금융 subset
    status: str = "unverified"
    note: str = ""


# 3-0. 스모크(영어 경량 reranking)
SMOKE_TASKS: list[TaskSpec] = [
    TaskSpec("AskUbuntuDupQuestions", "reranking", 10, "ndcg", note="경량 reranking 스모크."),
    TaskSpec("SciDocsRR", "reranking", 10, "ndcg", note="경량 reranking 스모크."),
]

# 3-2. 한국어 4종 (계획안 표)
KOREAN_TASKS: list[TaskSpec] = [
    TaskSpec("MIRACLReranking", "reranking", 10, "ndcg", domain="general",
             subset="ko", note="MTEB native reranking(Wikipedia 기반). 한국어 subset."),
    TaskSpec("Ko-StrategyQA", "retrieval", 1, "ndcg", domain="general",
             note="multi-hop. retrieval → 1차 후보 후 rerank. 주지표 nDCG@1, MRR."),
    TaskSpec("AutoRAGRetrieval", "retrieval", 1, "hit_rate@1", domain="finance",
             subset="finance", note="금융 subset만. retrieval → rerank. HitRate@1, P@k."),
    TaskSpec("MultiLongDocRetrieval", "retrieval", 5, "ndcg", domain="long_doc",
             note="장문 검색. retrieval → rerank. 주지표 nDCG@5."),
]


def all_task_specs() -> list[TaskSpec]:
    return [*SMOKE_TASKS, *KOREAN_TASKS]


# --------------------------------------------------------------------------- #
# 6절. 실행/재현성 설정 (전부 핀 고정)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class RunSettings:
    seed: int = 42
    precision: str = "bf16"
    # candidate 수 민감도(계획안 3·5절): 이 top-N 들로 곡선을 그린다.
    candidate_top_ns: tuple[int, ...] = (20, 50, 100)
    rerank_batch_size: int = 32       # 공정 비교용 고정 batch
    max_doc_len: int = 512            # (query+doc) truncation 상한(모든 모델 동일 고정)
    # 전 지표 공통 평가 k
    eval_ks: tuple[int, ...] = (1, 5, 10)
    # retrieval 1차 후보 생성 시 코퍼스 상한(시간 제어). None=전체.
    corpus_limit: int | None = None
    query_limit: int | None = None    # 쿼리 샘플링 상한(시간 제어)
    results_dir: str = "results"
    cache_dir: str = "cache"          # frozen 1차 후보 캐시(데이터셋별 재시작 핵심)


SETTINGS = RunSettings()

# 권장 설정 vs 통제 설정(계획안 2·6절): 모델 권장 포맷 vs 동일 통제.
PROMPT_MODES = ("recommended", "controlled")


# --------------------------------------------------------------------------- #
# 모델 메타 접근자 — 모두 _RAW_CONFIGS(발견된 yaml) 를 읽는다. 코드에 모델값 없음.
#   yaml top-level backend = local|endpoint(실행 위치),
#   yaml local_backend = cross_encoder|causal_lm(스코어링 구현, RerankerSpec.backend).
# --------------------------------------------------------------------------- #
def _raw(key: str) -> dict | None:
    return _RAW_CONFIGS.get(key)


def model_backend(key: str) -> tuple[str, dict]:
    """실행 위치 (local|endpoint, endpoint_cfg). 기본 ('local', {})."""
    cfg = _raw(key)
    if not cfg:
        return "local", {}
    return str(cfg.get("backend", "local")), (cfg.get("endpoint") or {})


def model_full_name(key: str) -> str:
    """결과 디렉토리/summary 용 모델 풀네임(yaml 'model')."""
    cfg = _raw(key)
    if cfg and cfg.get("model"):
        return str(cfg["model"])
    spec = RERANKERS.get(key)
    return spec.hf_name if spec else key


def resolve_spec(key: str) -> RerankerSpec:
    """RerankerSpec — yaml 발견으로 이미 RERANKERS 가 구성됐으므로 그대로 반환."""
    if key not in RERANKERS:
        raise KeyError(f"알 수 없는 리랭커 키: {key} (configs/models/*.yaml: {list(RERANKERS)})")
    return RERANKERS[key]
