"""config 무결성 + aggregate primary 추출 검증(GPU 불필요)."""

from rerankeval import config as C
from rerankeval import aggregate as A


def test_rerankers_discovered_from_yaml():
    # 리랭커는 코드 하드코딩이 아니라 configs/models/*.yaml 발견이어야 함(모델 비종속).
    from pathlib import Path
    cfg_dir = Path(C.__file__).resolve().parents[1] / "configs" / "models"
    stems = {p.stem for p in cfg_dir.glob("*.yaml")}
    assert stems and set(C.RERANKERS) == stems
    for spec in C.RERANKERS.values():
        assert spec.backend in C.SCORING_BACKENDS  # cross_encoder|causal_lm 만
        assert "/" in spec.hf_name


def test_no_model_specific_backend_baking():
    # 'qwen3' 같은 모델명을 backend 로 박지 않는다(스코어링 백엔드는 일반명만).
    assert C.SCORING_BACKENDS == ("cross_encoder", "causal_lm")
    assert all(s.backend in C.SCORING_BACKENDS for s in C.RERANKERS.values())


def test_causal_lm_prompt_comes_from_yaml():
    # 생성형 리랭커 템플릿은 코드 기본값이 아니라 그 모델의 yaml(데이터)에서 온다.
    spec = C.resolve_spec("qwen3-reranker-0.6b")
    assert spec.backend == "causal_lm"
    assert spec.prompt and all(k in spec.prompt for k in
                               ("prefix", "suffix", "instruct", "body_template"))


def test_korean_tasks_kinds_and_subset():
    by = {t.name: t for t in C.KOREAN_TASKS}
    # 계획안 3-2: native reranking 은 MIRACL, 나머지는 retrieval
    assert by["MIRACLReranking"].kind == "reranking"
    for r in ("Ko-StrategyQA", "AutoRAGRetrieval", "MultiLongDocRetrieval"):
        assert by[r].kind == "retrieval"
    # AutoRAG 는 금융 subset
    assert by["AutoRAGRetrieval"].domain == "finance"
    assert by["AutoRAGRetrieval"].subset == "finance"


def test_primary_k_matches_plan():
    by = {t.name: t for t in C.KOREAN_TASKS}
    assert by["Ko-StrategyQA"].primary_k == 1
    assert by["MIRACLReranking"].primary_k == 10
    assert by["MultiLongDocRetrieval"].primary_k == 5


def test_candidate_top_ns_for_sensitivity():
    # 계획안 3절: top-N 20/50/100 민감도 곡선
    assert C.SETTINGS.candidate_top_ns == (20, 50, 100)


def test_default_embedder_valid():
    assert C.DEFAULT_EMBEDDER in C.FIRST_STAGE_EMBEDDERS


def test_aggregate_primary_value():
    rec = {"primary": "ndcg@5",
           "baseline": {"ndcg@5": 0.40}, "reranked": {"ndcg@5": 0.55}}
    assert A._primary_value(rec, "baseline") == 0.40
    assert A._primary_value(rec, "reranked") == 0.55


def test_aggregate_markdown_renders_delta():
    recs = [{"task": "Ko-StrategyQA", "reranker": "ko-reranker", "embedder": "bge-m3-ko",
             "mode": "recommended", "top_n": 100, "primary": "ndcg@1",
             "baseline": {"ndcg@1": 0.30}, "reranked": {"ndcg@1": 0.50}}]
    md = A.to_markdown(recs, None)
    assert "0.500 (+0.200)" in md
