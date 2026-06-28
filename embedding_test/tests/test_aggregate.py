"""aggregate 점수 추출/매트릭스 — mteb 결과 JSON 파싱 로직 검증(GPU 불필요)."""

from embeval import aggregate


def test_extract_score_new_format():
    payload = {
        "task_name": "STSBenchmark",
        "scores": {"test": [{"main_score": 0.8123, "spearman": 0.8123}]},
    }
    name, score = aggregate._extract_score(payload)
    assert name == "STSBenchmark"
    assert abs(score - 0.8123) < 1e-9


def test_extract_score_flat_main_score():
    payload = {"mteb_dataset_name": "Banking77Classification",
               "scores": {"main_score": 0.71}}
    name, score = aggregate._extract_score(payload)
    assert name == "Banking77Classification"
    assert score == 0.71


def test_extract_score_missing_returns_none():
    assert aggregate._extract_score({"scores": {}}) is None
    assert aggregate._extract_score({"task_name": "X"}) is None


def test_extract_score_prefers_test_split():
    payload = {"task_name": "T", "scores": {
        "validation": [{"main_score": 0.10}],
        "test": [{"main_score": 0.90}],
    }}
    assert aggregate._extract_score(payload) == ("T", 0.90)


def test_extract_score_averages_multi_subset():
    # 다중 subset(언어별) → 평균 (0.6+0.8)/2 = 0.7
    payload = {"task_name": "Multi", "scores": {
        "test": [{"hf_subset": "ko", "main_score": 0.6},
                 {"hf_subset": "en", "main_score": 0.8}],
    }}
    name, score = aggregate._extract_score(payload)
    assert name == "Multi" and abs(score - 0.7) < 1e-9


def test_markdown_matrix_groups_by_mode_and_computes_avg():
    rows = [
        {"prompt_mode": "controlled", "model": "bge-m3-ko", "task": "KorSTS", "score": 0.80},
        {"prompt_mode": "controlled", "model": "bge-m3-ko", "task": "KLUE-STS", "score": 0.60},
        {"prompt_mode": "recommended", "model": "qwen3-8b", "task": "KorSTS", "score": 0.90},
    ]
    md = aggregate.to_markdown_matrix(rows)
    assert "prompt_mode = `controlled`" in md
    assert "prompt_mode = `recommended`" in md
    # bge-m3-ko 평균 = (0.80+0.60)/2 = 0.70
    assert "0.7000" in md


def test_markdown_matrix_empty():
    assert "결과 없음" in aggregate.to_markdown_matrix([])
