"""무엇: 불변 입력 해시 검증 · 입력: tmp_path·resume fixture · 출력: fingerprint/변조 거부 · 계약 §1-2."""

from copy import deepcopy
import hashlib
from pathlib import Path

import pytest
import yaml

from jeveval.io.hashes import sha256_file
from jeveval.io.models import load_model_config
from jeveval.run.fingerprint import build_fingerprint, same_fingerprint
from tests.run.t0_support import add_external


REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def inputs(tmp_path):
    add_external(tmp_path)
    paths = ["configs/tasks/kmhas.yaml", "configs/tasks/b1.yaml", "configs/datasets.yaml",
             "configs/models/b1_qwen3_8_27b.yaml", "configs/splits/rules.yaml",
             "jeveval/run/encoders/hf_chat_template.py"]
    paths += [str(p.relative_to(REPO)) for p in (REPO / "configs/tasks/lists").glob("*.json")]
    for name in paths:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((REPO / name).read_bytes())
    (tmp_path / "configs/splits").mkdir(exist_ok=True)
    (tmp_path / "configs/splits/kmhas.json").write_text("{}\n")
    data = tmp_path / "dataset/kmhas"
    data.mkdir(parents=True)
    (data / "source").write_text("PRIVATE_DATA")
    (data / "SHA256SUMS").write_text(sha256_file(data / "source") + "  source\n")
    tok = tmp_path / "tokenizer"
    tok.mkdir()
    (tok / "tokenizer.json").write_text("PRIVATE_TOKENIZER")
    cfg_path = tmp_path / "configs/models/b1_qwen3_8_27b.yaml"
    cfg = load_model_config(cfg_path).to_dict()
    cfg["tokenizer"] = dict(path="tokenizer", files_sha256={"tokenizer.json": sha256_file(tok / "tokenizer.json")})
    cfg_path.write_text(yaml.safe_dump(cfg))
    return dict(root=tmp_path, run_id="r1", model_cfg_path=cfg_path,
                task_path="configs/tasks/kmhas.yaml", set_name="kmhas", variant="default", started_at="now")


def test_exact_hashes_and_only_started_at_ignored(inputs, fixture_json):
    root = inputs["root"]
    (root / "jeveval/z.py").write_bytes(b"# z\n")
    (root / "jeveval/a.py").write_bytes(b"# a\n")
    (root / "jeveval/__pycache__").mkdir()
    (root / "jeveval/__pycache__/ignored.py").write_bytes(b"ignored")
    result = build_fingerprint(**inputs)
    assert result["schema"] == "fingerprint/1" and result["dataset_verified"] is True
    assert (result["model"], result["set"], result["variant"], result["run_id"]) == (
        "b1_qwen3_8_27b", "kmhas", "default", "r1")
    expected = ["configs/tasks/kmhas.yaml", "configs/tasks/b1.yaml", "configs/datasets.yaml", "configs/splits/kmhas.json",
                "configs/models/b1_qwen3_8_27b.yaml", "configs/splits/rules.yaml", "dataset/kmhas/SHA256SUMS"]
    expected += [p.relative_to(root).as_posix() for p in (root / "configs/tasks/lists").glob("*.json")]
    assert result["files"] == {p: sha256_file(root / p) for p in expected}
    assert result["inputs"] == dict(model_cfg_path="configs/models/b1_qwen3_8_27b.yaml",
        task_path="configs/tasks/kmhas.yaml", set="kmhas", variant="default", run_id="r1")
    assert result["encoder"] == dict(rule="hf_chat_template_no_think",
        sha256=sha256_file(root / "jeveval/run/encoders/hf_chat_template.py"))
    assert result["tokenizer"] == {"tokenizer.json": sha256_file(root / "tokenizer/tokenizer.json")}
    assert result["external"] == {"reranker_test/evalcommon/schema.py":
                                  sha256_file(root.parent / "reranker_test/evalcommon/schema.py")}
    assert set(result["env"]) == {"python", "numpy", "scipy", "zstandard", "pyyaml"}
    assert all(isinstance(v, str) and v for v in result["env"].values())
    payload = b"".join(p.relative_to(root).as_posix().encode() + b"\0" + p.read_bytes()
                       for p in sorted((root / "jeveval").rglob("*.py")) if "__pycache__" not in p.parts)
    assert result["code_sha256"] == hashlib.sha256(payload).hexdigest()
    assert "PRIVATE_" not in str(result)
    assert same_fingerprint(result, build_fingerprint(**{**inputs, "started_at": "later"}))
    source = fixture_json("resume/fingerprint.json")
    for name in ("same", "different"):
        assert same_fingerprint(source["existing"], source[name]) == source["expected"][name + "_allowed"]
    for key in result.keys() - {"started_at"}:
        changed = deepcopy(result)
        changed[key] = "changed"
        assert not same_fingerprint(result, changed)


@pytest.mark.parametrize("name", ["dataset/kmhas/source", "tokenizer/tokenizer.json"])
def test_tampered_and_missing_input_rejected(inputs, name):
    path = inputs["root"] / name
    path.write_text("changed")
    with pytest.raises(ValueError, match="hash mismatch"):
        build_fingerprint(**inputs)
    path.unlink()
    with pytest.raises(ValueError):
        build_fingerprint(**inputs)


def test_nulls_unknown_rule_and_empty_tokenizer_manifest(inputs):
    path = inputs["model_cfg_path"]
    cfg = load_model_config(path).to_dict()
    cfg["encoder"]["rule"] = None
    cfg["tokenizer"]["path"] = None
    path.write_text(yaml.safe_dump(cfg))
    result = build_fingerprint(**inputs)
    assert result["encoder"] is result["tokenizer"] is None
    cfg["encoder"]["rule"] = "unregistered"
    path.write_text(yaml.safe_dump(cfg))
    with pytest.raises(ValueError, match="encoder"):
        build_fingerprint(**inputs)
    cfg["encoder"]["rule"] = None
    cfg["tokenizer"] = dict(path="tokenizer", files_sha256={})
    path.write_text(yaml.safe_dump(cfg))
    with pytest.raises(ValueError, match="tokenizer"):
        build_fingerprint(**inputs)


def test_task_identity_and_code_or_list_changes(inputs):
    with pytest.raises(ValueError, match="identity"):
        build_fingerprint(**{**inputs, "variant": "wrong"})
    before = build_fingerprint(**inputs)
    (inputs["root"] / "jeveval/added.py").write_text("# code change\n")
    assert not same_fingerprint(before, build_fingerprint(**inputs))
    before = build_fingerprint(**inputs)
    (inputs["root"] / "configs/tasks/lists/added.json").write_text("{}")
    assert not same_fingerprint(before, build_fingerprint(**inputs))
    before = build_fingerprint(**inputs)
    rules = inputs["root"] / "configs/splits/rules.yaml"
    rules.write_text(rules.read_text() + "\n# changed\n")
    assert not same_fingerprint(before, build_fingerprint(**inputs))


def test_external_and_environment_changes_invalidate_fingerprint(inputs, monkeypatch):
    from jeveval.io import environment
    original = build_fingerprint(**inputs)
    path = inputs["root"].parent / "reranker_test/evalcommon/schema.py"
    path.write_bytes(path.read_bytes() + b"\n# changed\n")
    assert not same_fingerprint(original, build_fingerprint(**inputs))
    original = build_fingerprint(**inputs)
    monkeypatch.setattr(environment, "versions", lambda: {**original["env"], "scipy":"changed"})
    assert not same_fingerprint(original, build_fingerprint(**inputs))
