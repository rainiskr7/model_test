"""무엇: 공용 경로·바이트 동결 · 입력: 0906d42 앵커 · 출력: 새 셋의 전역 변경 검출 · 계약 판 5 보정 1 §9."""

from hashlib import sha256
from pathlib import Path

from jeveval.io.set_tasks import BASE_TASKS


def test_shared_config_path_set_and_bytes_frozen():
    root = Path(__file__).resolve().parents[2]
    expected = dict(line.split("  ")[::-1] for line in
                    (root / "tests/fixtures/shared_config.sha256").read_text().splitlines())
    paths = {"configs/datasets.yaml", "configs/splits/rules.yaml", "configs/tasks/b1.yaml", "configs/policy.yaml"}
    paths.update("configs/tasks/" + p for names in BASE_TASKS.values() for p in names)
    paths.update(f"configs/splits/{s}.json" for s in BASE_TASKS)
    paths.update(p.relative_to(root).as_posix() for p in (root / "configs/tasks/lists").glob("*.json"))
    assert paths == expected.keys()
    assert {p: sha256((root / p).read_bytes()).hexdigest() for p in paths} == expected
