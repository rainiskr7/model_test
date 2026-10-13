"""무엇: 등록 모델·로더 통합 · 입력: 모델 YAML/합성 오류 · 출력: 설정·누락 · 계약 §8-6."""

from pathlib import Path

import pytest

from jeveval.contract.model_config import missing_for_run
from jeveval.io.config import DuplicateKeyError
from jeveval.io.models import ModelConfigError, load_model_config
from jeveval.io.tasks import read_b1_config
from jeveval.types import ModelConfig


ROOT = Path(__file__).resolve().parents[2]
EXPECTED = {
    "clef": ("systemone", "joint", "Cloudflare/clef", "0b33120"),
    "clef_flash": ("systemone", "joint", "Cloudflare/clef-flash", "8b2e5fd"),
    "pplx_v1_1": ("systemone", "separate", "perplexity-ai/pplx-decider-v1.1-27b", "6195aa5"),
    "pplx_v1": ("systemone", "separate", "perplexity-ai/pplx-decider-v1-27b", "b01a5cb"),
    "b1_qwen3_8_27b": ("b1", "separate", None, None),
    "b1_qwen3_8_27b_fp8": ("b1", "separate", None, None),
}
B1_SERVING = {
    "b1_qwen3_8_27b": ("qwen_qwen3.8_27b", "OPENAI_API_KEY"),
    "b1_qwen3_8_27b_fp8": ("qwen_qwen3.8_27B_FP8", "OPENAI_API_KEY_7"),
}


def test_six_registered_models_and_pending_run_fields():
    paths = sorted((ROOT / "configs/models").glob("*.yaml"))
    assert {p.stem for p in paths} == set(EXPECTED)
    labels = read_b1_config(ROOT / "configs/tasks/b1.yaml").labels
    assert len(labels) == 62
    for path in paths:
        cfg = load_model_config(path)
        assert cfg.id == path.stem
        assert (cfg.kind, cfg.question_scoring, cfg.repo["id"], cfg.repo["sha"]) == EXPECTED[cfg.id]
        assert cfg.concurrency == 1 and cfg.t0 == {"status": "not_run", "record": None}
        assert cfg.notes
        assert cfg.input_limit_response == (
            {"status": 400, "body_regex": "maximum context length is"}
            if cfg.id in B1_SERVING else None)
        assert ModelConfig.from_dict(cfg.to_dict()) == cfg
        expected = ["served_name", "base_url", "limit.tokens", "limit.overflow", "encoder.rule",
                    "tokenizer.path", "tokenizer.files_sha256"]
        if cfg.kind == "b1":
            expected = ["base_url"]
            assert cfg.serving["engine"] == "vllm"
            assert (cfg.served_name, cfg.auth_env) == B1_SERVING[cfg.id]
        else:
            assert cfg.served_name is None
        assert missing_for_run(cfg, labels) == expected


@pytest.mark.parametrize("body", ["id: m\nid: m\n", "tokenizer: {path: a, path: b}\n"])
def test_duplicate_keys(tmp_path, body):
    path = tmp_path / "m.yaml"
    path.write_text(body)
    with pytest.raises(DuplicateKeyError):
        load_model_config(path)


def test_schema_errors_are_exposed_as_list(tmp_path):
    path = tmp_path / "m.yaml"
    path.write_text("id: other\nunknown: 1\n")
    with pytest.raises(ModelConfigError) as caught:
        load_model_config(path)
    assert "id: invalid value" in caught.value.errors
    assert "unknown: unknown key" in caught.value.errors
    assert str(caught.value) == "\n".join(caught.value.errors)
