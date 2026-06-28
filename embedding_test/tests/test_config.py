"""config 무결성 — 계획안과 코드가 어긋나지 않는지 검증(GPU 불필요)."""

from embeval import config


def test_models_discovered_from_yaml():
    # 모델은 코드 하드코딩이 아니라 configs/models/*.yaml 발견이어야 함(모델 비종속).
    from pathlib import Path
    cfg_dir = Path(config.__file__).resolve().parents[1] / "configs" / "models"
    stems = {p.stem for p in cfg_dir.glob("*.yaml")}
    assert stems, "configs/models/*.yaml 없음"
    assert set(config.MODELS) == stems  # 코드가 yaml 을 발견해 구성
    for spec in config.MODELS.values():
        assert spec.hf_name and "/" in spec.hf_name


def test_repr_tasks_are_retrieval_only():
    # repr(sparse/hybrid)는 retrieval 태스크에서만 의미.
    assert config.REPR_TASKS, "REPR_TASKS 비어있음"
    assert all(t.kind == "Retrieval" for t in config.REPR_TASKS)


def test_finparasts_removed():
    # 계획안 3-B: FinParaSTS 는 Finnish(핀란드어)라 제거 — 다시 들어오면 회귀 버그.
    names = [t.name for t in config.all_task_specs()]
    assert "FinParaSTS" not in names


def test_smoke_has_light_and_heavy_marked():
    names = {t.name for t in config.SMOKE_TASKS}
    assert {"Banking77Classification", "STSBenchmark"} <= names
    # 무거운 태스크엔 fallback 후보가 정의돼야 함(계획안 3-0)
    fb = {t.fallback_for for t in config.SMOKE_TASKS if t.status == "fallback"}
    assert {"MSMARCO", "RedditClustering"} <= fb


def test_korean_covers_four_task_kinds():
    kinds = {t.kind for t in config.KOREAN_TASKS}
    assert {"STS", "Classification", "Retrieval", "Clustering"} <= kinds


def test_uncertain_tasks_marked_unverified():
    # 계획안 8절: 미존재 추정 태스크는 confirmed 로 적혀 있으면 안 됨(검증 전).
    by_name = {t.name: t for t in config.all_task_specs()}
    for risky in ("KlueMrcDomainClustering", "KorFin-ASC"):
        assert by_name[risky].status != "confirmed"


def test_prompt_modes():
    assert config.PROMPT_MODES == ("recommended", "controlled")
