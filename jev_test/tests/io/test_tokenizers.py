"""무엇: 토크나이저 파일/로더 경계 · 입력: 합성 폴더·주입 로더 · 출력: 검증 경로/핸들 · 계약 §8-6 G."""

from hashlib import sha256
from pathlib import Path
from unittest.mock import Mock

import pytest

from jeveval.io.tokenizers import load_offline, verified_directory


@pytest.fixture
def tokenizer(tmp_path):
    directory = tmp_path / "tokenizer"
    directory.mkdir()
    payload = b'{"synthetic": true}'
    (directory / "tokenizer.json").write_bytes(payload)
    return {"path": str(directory), "files_sha256": {"tokenizer.json": sha256(payload).hexdigest()}}


@pytest.mark.parametrize("changes", [{"path": None}, {"path": ""}, {"path": 1},
    {"files_sha256": None}, {"files_sha256": {}}, {"files_sha256": []}])
def test_verified_directory_rejects_incomplete_configuration(tokenizer, changes):
    with pytest.raises(ValueError, match="^incomplete tokenizer configuration$"):
        verified_directory({**tokenizer, **changes})


@pytest.mark.parametrize("missing", ["path", "files_sha256"])
def test_verified_directory_requires_configuration_keys(tokenizer, missing):
    del tokenizer[missing]
    with pytest.raises(ValueError, match="^incomplete tokenizer configuration$"):
        verified_directory(tokenizer)


@pytest.mark.parametrize("name", ["missing", "tokenizer.json"])
def test_verified_directory_requires_directory(tokenizer, name):
    tokenizer["path"] = str(Path(tokenizer["path"]) / name)
    with pytest.raises(ValueError, match="^tokenizer path must be a directory$"):
        verified_directory(tokenizer)


def test_verified_directory_rejects_missing_manifest_file(tokenizer):
    (Path(tokenizer["path"]) / "tokenizer.json").unlink()
    with pytest.raises(ValueError) as error:
        verified_directory(tokenizer)
    assert str(error.value) == "tokenizer file missing or outside directory: tokenizer.json"


def test_verified_directory_rejects_symlink_escape(tokenizer, tmp_path):
    path = Path(tokenizer["path"]) / "tokenizer.json"
    outside = tmp_path / "outside.json"
    path.rename(outside)
    path.symlink_to(outside)
    with pytest.raises(ValueError) as error:
        verified_directory(tokenizer)
    assert str(error.value) == "tokenizer file missing or outside directory: tokenizer.json"


def test_verified_directory_reports_hash_mismatch_filename(tokenizer):
    (Path(tokenizer["path"]) / "tokenizer.json").write_bytes(b"changed")
    with pytest.raises(ValueError) as error:
        verified_directory(tokenizer)
    assert str(error.value) == "tokenizer hash mismatch: tokenizer.json"


def test_verified_directory_returns_resolved_path(tokenizer, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    tokenizer["path"] = "tokenizer"
    assert verified_directory(tokenizer) == (tmp_path / "tokenizer").resolve()


def test_load_offline_returns_loader_handle(tmp_path, monkeypatch):
    from transformers import AutoTokenizer

    handle = object()
    loader = Mock(return_value=handle)
    monkeypatch.setattr(AutoTokenizer, "from_pretrained", loader)
    for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        monkeypatch.setenv(key, "0")
    # 정확한 인자/호출 시점 환경은 test_encoders.test_verified_load_and_manual_length에서 검증한다.
    assert load_offline(tmp_path) is handle
    loader.assert_called_once()
