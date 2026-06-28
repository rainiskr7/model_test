"""cost 순수 헬퍼 검증 — torch/GPU 없이 동작하는 부분만(GPU 불필요)."""

from embeval import cost


def test_make_corpus_is_deterministic_and_sized():
    a = cost._make_corpus(10)
    b = cost._make_corpus(10)
    assert a == b  # 결정적(시드 영향 없음)
    assert len(a) == 10
    assert all(isinstance(s, str) and s for s in a)


def test_make_corpus_length_bound():
    docs = cost._make_corpus(3, seq_chars=200)
    # 프리픽스 "[i] " 제외 본문이 대략 seq_chars 길이
    assert all(len(d) >= 200 for d in docs)


def test_dtype_bytes_matches_precision():
    # SETTINGS 는 frozen — 기본 precision(bf16) 기준 2바이트인지 확인.
    assert cost.SETTINGS.precision in {"bf16", "fp16", "fp32"}
    expected = {"bf16": 2, "fp16": 2, "fp32": 4}[cost.SETTINGS.precision]
    assert cost._dtype_bytes() == expected


def test_vectordb_estimate_formula():
    # 1M docs × 1024 dim × 2 bytes = 2.0 GiB
    dim, dbytes = 1024, 2
    gb = (1_000_000 * dim * dbytes) / (1024 ** 3)
    assert abs(gb - 1.9073) < 1e-2
