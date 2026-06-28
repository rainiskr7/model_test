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


MODELS: dict[str, ModelSpec] = {
    "qwen3-8b": ModelSpec(
        key="qwen3-8b",
        hf_name="Qwen/Qwen3-Embedding-8B",
        revision=None,  # TODO: 실행 직전 커밋 해시로 고정
        uses_prompts=True,  # query: "Instruct: ...\nQuery: ..." 형식
        notes="8B 대형. FP16/BF16 약 16GB+. 24GB GPU에서도 batch/length에 따라 OOM 가능(계획안 5절).",
    ),
    "kanana-2.1b": ModelSpec(
        key="kanana-2.1b",
        hf_name="kakaocorp/kanana-nano-2.1b-embedding",
        revision=None,  # TODO: 고정
        uses_prompts=True,  # instruction 기반 권장
        notes="2.1B 국산 경량.",
    ),
    "bge-m3-ko": ModelSpec(
        key="bge-m3-ko",
        hf_name="upskyy/bge-m3-korean",
        revision=None,  # TODO: 고정
        uses_prompts=False,  # BGE-M3 계열은 query instruction 불필요
        notes="BGE-M3 한국어 파인튜닝. dense 전용(sparse/colbert 헤드 없음).",
    ),
    "bge-m3": ModelSpec(
        key="bge-m3",
        hf_name="BAAI/bge-m3",
        revision=None,  # TODO: 고정
        uses_prompts=False,
        notes="원본 멀티기능 BGE-M3. dense+sparse(+colbert). repr 트랙(sparse/hybrid)용.",
    ),
}


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
# repr 트랙 — dense/sparse/hybrid 표현 비교(멀티기능 BGE-M3 전용).
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
# 운영 설정 오버레이 — configs/models/<key>.yaml (model_test 규약).
#   MODELS(위)는 평가 로직의 SSOT(로컬 로딩/태스크). YAML 은 "어떻게 서빙/실행할지"
#   (backend: local|endpoint, endpoint 정보)를 덧씌우는 운영 레이어다.
#   yaml 이 없거나 PyYAML 미설치면 조용히 local 로 폴백 → 기존 동작/테스트 불변.
# --------------------------------------------------------------------------- #
from pathlib import Path as _Path

_CONFIG_DIR = _Path(__file__).resolve().parents[1] / "configs" / "models"


def load_yaml_model(key: str) -> dict | None:
    """configs/models/<key>.yaml 로드(있으면). 없거나 yaml 미설치면 None.

    파싱 오류는 조용히 삼키지 않고 경고를 찍는다(잘못된 config 가 hardcoded local 런으로
    둔갑하는 사고 방지). 단, 평가 자체는 fallback 으로 계속할 수 있도록 None 을 반환한다.
    """
    path = _CONFIG_DIR / f"{key}.yaml"
    if not path.exists():
        return None
    try:
        import yaml
    except ImportError:
        return None
    try:
        return yaml.safe_load(path.read_text())
    except Exception as exc:
        print(f"[config] ⚠️ yaml 파싱 실패({path}): {exc} → MODELS 하드코딩값으로 폴백")
        return None


def model_backend(key: str) -> tuple[str, dict]:
    """모델 key 의 (backend, endpoint_cfg). 기본 ('local', {})."""
    cfg = load_yaml_model(key)
    if not cfg:
        return "local", {}
    return str(cfg.get("backend", "local")), (cfg.get("endpoint") or {})


def model_full_name(key: str) -> str:
    """결과 디렉토리/summary 의 모델 풀네임(safe_model_name 의 입력).

    yaml 의 `model` 필드(원본 풀네임)를 우선, 없으면 MODELS 의 hf_name.
    """
    cfg = load_yaml_model(key)
    if cfg and cfg.get("model"):
        return str(cfg["model"])
    spec = MODELS.get(key)
    return spec.hf_name if spec else key


def model_representations(key: str) -> list[str]:
    """모델이 지원하는 표현 목록(yaml). 기본 ['dense']."""
    cfg = load_yaml_model(key)
    reps = (cfg or {}).get("representations")
    return [str(r) for r in reps] if reps else ["dense"]


def model_local_backend(key: str) -> str:
    """로컬 로더 종류(yaml local_backend). 'sentence_transformers' | 'flagembedding'."""
    cfg = load_yaml_model(key)
    return str((cfg or {}).get("local_backend", "sentence_transformers"))


def model_hybrid(key: str) -> tuple[float, str]:
    """(hybrid_alpha, hybrid_normalization). 기본 (0.5, 'per_query_minmax')."""
    cfg = load_yaml_model(key) or {}
    return float(cfg.get("hybrid_alpha", 0.5)), str(cfg.get("hybrid_normalization", "per_query_minmax"))


def resolve_spec(key: str) -> "ModelSpec":
    """local 로딩용 ModelSpec — yaml 의 local 블록을 MODELS[key] 위에 덧씌운다.

    yaml 이 model 식별값(hf_name/revision/uses_prompts)의 SSOT 가 되게 한다(혼동 방지).
    precision/max_seq_length 는 모델 간 공정비교를 위해 전역 SETTINGS 로 고정(계획안 5절) →
    의도적으로 per-model override 하지 않는다.
    """
    from dataclasses import replace
    spec = MODELS[key]
    cfg = load_yaml_model(key)
    loc = (cfg or {}).get("local") or {}
    if not loc:
        return spec
    return replace(
        spec,
        hf_name=loc.get("hf_name", spec.hf_name),
        revision=loc.get("revision", spec.revision),
        uses_prompts=bool(loc.get("uses_prompts", spec.uses_prompts)),
    )
