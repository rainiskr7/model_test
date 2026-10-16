"""무엇: 외부 코드 경로/환경/보존 · 입력: 격리 model_test · 출력: 제한된 외부 파일 · 계약 T-j."""

from types import SimpleNamespace
import tarfile

import pytest
import zstandard

from jeveval.io import environment
from jeveval.io.archive import build_archive, entries_for
from jeveval.io.hashes import sha256_file
from jeveval.io.paths import inside


@pytest.fixture
def external(tmp_path):
    root = tmp_path / "model_test/jev_test"
    root.mkdir(parents=True)
    path = root.parent / "reranker_test/evalcommon/schema.py"
    path.parent.mkdir(parents=True)
    path.write_text("# synthetic external code\n")
    return root, path


def test_actual_package_versions_and_external_hash(external):
    root, path = external
    assert environment.external_hashes(root) == {"reranker_test/evalcommon/schema.py":sha256_file(path)}
    env = environment.versions()
    assert set(env) == {"python", "numpy", "scipy", "zstandard", "pyyaml"}
    assert all(isinstance(v, str) and v for v in env.values())
    with pytest.raises(ValueError):
        inside(root, path)


@pytest.mark.parametrize("name", ["../escape", "/absolute", "./reranker_test/evalcommon/schema.py",
                                  "reranker_test/../secret", "unknown.py", ""])
def test_external_path_does_not_weaken_inside(external, name):
    root, _ = external
    with pytest.raises(ValueError):
        environment.external_path(root, name)


def test_symlink_escape_and_missing_file(external, tmp_path):
    root, path = external
    path.unlink()
    with pytest.raises(ValueError):
        environment.external_hashes(root)
    outside = tmp_path / "outside.py"
    outside.write_text("outside")
    path.symlink_to(outside)
    with pytest.raises(ValueError):
        environment.external_hashes(root)


def test_archive_external_alias_bytes_and_hash_recheck(external):
    root, path = external
    directory = root / "run"
    directory.mkdir()
    (directory / "fingerprint.json").write_text("{}")
    for stage in ("dev", "test"):
        (directory / stage).mkdir()
        for name in ("attempts", "final"):
            (directory / stage / f"{name}.jsonl").write_text("")
    ctx = SimpleNamespace(directory=directory, task=SimpleNamespace(set="s"),
                           fingerprint={"files":{}, "external":environment.external_hashes(root)})
    entries = entries_for(root, [ctx])
    alias = "_external/reranker_test/evalcommon/schema.py"
    assert entries[alias] == path
    out = root / "archive.zst"
    build_archive(entries, out)
    with out.open("rb") as raw, zstandard.ZstdDecompressor().stream_reader(raw) as stream:
        with tarfile.open(fileobj=stream, mode="r|") as archive:
            payload = {m.name:archive.extractfile(m).read() for m in archive}
    assert payload[alias] == path.read_bytes()
    path.write_text("changed")
    with pytest.raises(ValueError, match="hash"):
        entries_for(root, [ctx])
