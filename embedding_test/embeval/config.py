"""평가 대상 모델 / 태스크 / 실행 설정 정의.

계획안(임베딩_모델_테스트_계획안.md)을 코드로 옮긴 단일 진실 공급원(SSOT).
- 모델: 2절
- 태스크: 3절 (스모크 / 범용 한국어 / 금융)
- 설정: 5절 (재현성 핀 고정, prefix 정책)

⚠️ 여기 적힌 태스크 이름 중 다수는 "실재 여부 미확정"이다(계획안 8절).
   반드시 `python run.py verify` 를 먼저 돌려 registry 존재를 확정한 뒤 평가를 실행한다.
"""

from __future__ import annotations

from dataclasses import dataclass


# --------------------------------------------------------------------------- #
# 2절. 테스트 대상 모델
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ModelSpec:
    key: str  # 내부 식별자(파일/표 키)
    hf_name: str  # HuggingFace repo id
    revision: str | None  # 재현성: 커밋 해시로 고정 권장(계획안 5절). None=최신(비권장)
    # query/passage prefix 또는 instruction을 쓰는 모델인지.
    # True면 mteb의 모델 메타가 권장 프롬프트를 자동 주입한다(권장 설정).
    uses_prompts: bool
    notes: str = ""


# 모델은 코드에 하드코딩하지 않는다(모델 비종속). configs/models/*.yaml 이 단일 소스(SSOT)이며
# 아래 발견 로직이 import 시 그 디렉토리를 스캔해 MODELS 를 만든다.
from pathlib import Path as _Path

_CONFIG_DIR = _Path(__file__).resolve().parents[1] / "configs" / "models"


def _load_raw_configs() -> dict[str, dict]:
    """configs/models/*.yaml 발견. 엄격: PyYAML 필수, 빈 디렉토리/파싱오류/stem!=key/
    class!=embedding/필수필드 누락 → import 중단(SSOT 이므로 조용한 폴백 없음)."""
    try:
        import yaml
    except ImportError as e:
        raise RuntimeError("PyYAML 필요 — configs/models/*.yaml 로딩(requirements.txt).") from e
    if not _CONFIG_DIR.is_dir():
        raise RuntimeError(f"모델 config 디렉토리 없음: {_CONFIG_DIR}")
    out: dict[str, dict] = {}
    for path in sorted(_CONFIG_DIR.glob("*.yaml")):
        stem = path.stem
        try:
            cfg = yaml.safe_load(path.read_text())
        except Exception as e:
            raise RuntimeError(f"yaml 파싱 실패: {path}: {e}") from e
        if not isinstance(cfg, dict):
            raise RuntimeError(f"yaml 형식 오류(dict 아님): {path}")
        if cfg.get("key") != stem:
            raise RuntimeError(f"파일명 stem('{stem}') != yaml key('{cfg.get('key')}'): {path}")
        if cfg.get("class") != "embedding":
            raise RuntimeError(f"class 는 정확히 'embedding' 이어야 함({cfg.get('class')}): {path}")
        if not cfg.get("model"):
            raise RuntimeError(f"필수 'model' 없음: {path}")
        loc = cfg.get("local") or {}
        # 모델 특화값은 코드 기본값으로 둠 없이 yaml 이 명시해야 한다(SSOT, 무하드코딩).
        if not loc.get("hf_name"):
            raise RuntimeError(f"필수 'local.hf_name' 없음: {path}")
        if "uses_prompts" not in loc:
            raise RuntimeError(f"필수 'local.uses_prompts'(모델 특화) 없음: {path}")
        if not cfg.get("local_backend"):
            raise RuntimeError(f"필수 'local_backend'(sentence_transformers|flagembedding) 없음: {path}")
        out[stem] = cfg
    if not out:
        raise RuntimeError(f"모델 config 가 없음: {_CONFIG_DIR}/*.yaml")
    return out


_RAW_CONFIGS: dict[str, dict] = _load_raw_configs()


def _build_model_spec(cfg: dict) -> ModelSpec:
    loc = cfg.get("local") or {}
    return ModelSpec(
        key=cfg["key"], hf_name=loc["hf_name"], revision=loc.get("revision"),
        uses_prompts=bool(loc.get("uses_prompts", False)), notes=cfg.get("notes", ""))


MODELS: dict[str, ModelSpec] = {k: _build_model_spec(c) for k, c in _RAW_CONFIGS.items()}


# --------------------------------------------------------------------------- #
# 3절. 태스크 정의
#   status: "confirmed" = MTEB registry 실재 확인됨(검증 스크립트가 갱신)
#           "unverified" = 계획안 기준 후보. 실행 전 verify 필수
#           "fallback"   = 시간/메모리 초과 시 대체 후보
# --------------------------------------------------------------------------- #
@dataclass
class TaskSpec:
    name: str  # MTEB 태스크 클래스명
    kind: str  # STS | Classification | Retrieval | Clustering | PairClassification
    status: str = "unverified"
    note: str = ""
    fallback_for: str | None = None  # 어떤 태스크의 대체인지
    subset: str | None = None  # 예: AutoRAG 금융 subset (repr retrieval 로딩에서 사용)


# 3-0. 빠른 스모크(영어 기준, 파이프라인 검증용)
SMOKE_TASKS: list[TaskSpec] = [
    TaskSpec("Banking77Classification", "Classification", note="가벼움. 권장 스모크."),
    TaskSpec("STSBenchmark", "STS", note="가벼움. 권장 스모크."),
    TaskSpec("MSMARCO", "Retrieval", note="⚠️ 코퍼스 큼. 스모크엔 무거울 수 있음(계획안 3-0)."),
    TaskSpec("RedditClustering", "Clustering", note="⚠️ 코퍼스 큼(계획안 3-0)."),
    # 대체 후보(시간 초과 시)
    TaskSpec("TwentyNewsgroupsClustering", "Clustering", status="fallback",
             fallback_for="RedditClustering", note="가벼운 클러스터링 대체."),
    TaskSpec("SciFact", "Retrieval", status="fallback",
             fallback_for="MSMARCO", note="소규모 Retrieval 대체."),
]

# 3-A. 범용 한국어 (4개 태스크 유형)
KOREAN_TASKS: list[TaskSpec] = [
    # STS
    TaskSpec("KLUE-STS", "STS", note="국내 표준. MTEB 실재명 확인 필요(예: 'KLUE-STS' vs 'KlueSTS')."),
    TaskSpec("KorSTS", "STS", note="국제 비교 가능."),
    # Classification — 계획안 8.2: NSMC vs KLUE-TC(YNAT) 중 1개 확정 필요
    TaskSpec("KLUE-TC", "Classification",
             note="YNAT 주제 7분류. '분류' 목적에 적합(계획안 3-A 주석)."),
    TaskSpec("NSMC", "Classification", status="fallback", fallback_for="KLUE-TC",
             note="감성 이진분류. 도메인 다양성 제한적이나 안정적 대안."),
    # Retrieval
    TaskSpec("Ko-StrategyQA", "Retrieval", note="추론형 검색. nDCG@10."),
    # Clustering — 계획안 8: KlueMrcDomainClustering 은 미존재 추정 → verify 로 확정
    TaskSpec("KlueMrcDomainClustering", "Clustering",
             note="⚠️ 미존재 추정(계획안 8.1). verify 결과로 확정/제거."),
]

# 3-B. 금융 — 트랙 1 (가용 공개 데이터셋)
FINANCIAL_TASKS: list[TaskSpec] = [
    TaskSpec("FinancialPhrasebankClassification", "Classification", note="금융 감성(영어)."),
    TaskSpec("FiQA2018", "Retrieval", note="금융 QA 검색(영어). 보조지표."),
    TaskSpec("KorFin-ASC", "Classification",
             note="⚠️ 한국어 금융 감성. HF dataset/split/label 확인 후 사용(계획안 3-B). MTEB 실재 미확정."),
    # 계획안 3-B 주석: FinParaSTS 는 Finnish(핀란드어)라 제거함 — 추가하지 말 것.
]


def all_task_specs() -> list[TaskSpec]:
    return [*SMOKE_TASKS, *KOREAN_TASKS, *FINANCIAL_TASKS]


# --------------------------------------------------------------------------- #
# repr 트랙 — dense/sparse/hybrid 표현 비교(멀티기능 임베딩(BGEM3FlagModel 호환) 전용).
#   sparse 는 retrieval 에서만 의미 → retrieval 태스크만. 1차 구현은 한국어 중심 소수.
# --------------------------------------------------------------------------- #
REPR_TASKS: list[TaskSpec] = [
    TaskSpec("Ko-StrategyQA", "Retrieval", note="추론형 한국어 검색. dense/sparse/hybrid 비교."),
    TaskSpec("AutoRAGRetrieval", "Retrieval", subset="finance",
             note="⚠️ 금융 subset. 실재/subset 확인 후 사용(verify)."),
    TaskSpec("FiQA2018", "Retrieval", note="금융 QA 검색(영어). 보조 비교."),
]


# --------------------------------------------------------------------------- #
# 5절. 실행/재현성 설정 (전부 핀 고정)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class RunSettings:
    seed: int = 42
    precision: str = "bf16"  # 품질 평가 기준. 배포 비교는 cost 단계에서 별도 양자화.
    # 공정 비교용 고정 batch (모든 모델 동일). 8B가 OOM이면 낮춰 재기록.
    fixed_batch_size: int = 16
    max_seq_length: int = 512  # RAG chunking truncation 상한(세 모델 동일 고정, 계획안 5절)
    # 코퍼스 큰 Retrieval 시간 제어용 코퍼스 상한(계획안 5절 "코퍼스 샘플링").
    # ⚠️ mteb 의 corpus 상한은 encode kwarg 가 아니라 태스크/평가기별로 다르게 적용된다.
    #    현재 하니스는 이 값을 자동 주입하지 않는다(잘못된 kwarg 전달 방지).
    #    필요 시 해당 Retrieval 태스크에 맞는 방식으로 별도 구현할 것.
    corpus_sample_size: int | None = None
    results_dir: str = "results"


SETTINGS = RunSettings()


# prompt 정책 (계획안 5절: "권장 설정" vs "통제 설정" 분리 기록)
#   "recommended": 각 모델 권장 prefix/instruction 적용(mteb 모델 메타 사용)
#   "controlled" : 모든 모델 prefix 제거(공정 비교)
PROMPT_MODES = ("recommended", "controlled")


# --------------------------------------------------------------------------- #
# 모델 메타 접근자 — 모두 _RAW_CONFIGS(발견된 yaml) 를 읽는다. 코드에 모델값 없음.
#   yaml top-level backend = local|endpoint(실행 위치),
#   precision/max_seq_length 는 공정비교 위해 전역 SETTINGS 고정(yaml 의 값은 참고용).
# --------------------------------------------------------------------------- #
def _raw(key: str) -> dict | None:
    return _RAW_CONFIGS.get(key)


def model_backend(key: str) -> tuple[str, dict]:
    """(backend, endpoint_cfg). backend=local|endpoint. 기본 ('local', {})."""
    cfg = _raw(key)
    if not cfg:
        return "local", {}
    return str(cfg.get("backend", "local")), (cfg.get("endpoint") or {})


def model_full_name(key: str) -> str:
    """결과 디렉토리/summary 의 모델 풀네임(yaml 'model')."""
    cfg = _raw(key)
    if cfg and cfg.get("model"):
        return str(cfg["model"])
    spec = MODELS.get(key)
    return spec.hf_name if spec else key


def model_representations(key: str) -> list[str]:
    """지원 표현 목록(yaml). 기본 ['dense']."""
    reps = (_raw(key) or {}).get("representations")
    return [str(r) for r in reps] if reps else ["dense"]


def model_local_backend(key: str) -> str:
    """로컬 로더 종류(yaml). 'sentence_transformers' | 'flagembedding'."""
    return str((_raw(key) or {}).get("local_backend", "sentence_transformers"))


def model_hybrid(key: str) -> tuple[float, str]:
    """(hybrid_alpha, hybrid_normalization). 기본 (0.5, 'per_query_minmax')."""
    cfg = _raw(key) or {}
    return float(cfg.get("hybrid_alpha", 0.5)), str(cfg.get("hybrid_normalization", "per_query_minmax"))


def models_with_track(track: str) -> list[str]:
    """yaml tracks 에 해당 트랙을 포함하는 모델 키 목록(CLI 기본값 도출용)."""
    return [k for k, c in _RAW_CONFIGS.items() if track in (c.get("tracks") or [])]


def resolve_spec(key: str) -> ModelSpec:
    """local 로딩용 ModelSpec. yaml 발견으로 이미 MODELS 가 구성됐으므로 그대로 반환."""
    if key not in MODELS:
        raise KeyError(f"알 수 없는 모델 키: {key} (configs/models/*.yaml: {list(MODELS)})")
    return MODELS[key]
