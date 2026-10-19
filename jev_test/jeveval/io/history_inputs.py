"""무엇: 역사 Item 재구성 입력 확인 · 입력: root/History · 출력: task 경로 · 계약 §5-1b."""

from jeveval.io.hashes import sha256_file
from jeveval.io.paths import inside


def checked_task(root, history):
    """task·split·목록·원본 manifest가 동결 바이트와 같을 때만 재구성한다."""
    fp = history.artifacts["fingerprint.json"]
    task = fp["inputs"]["task_path"]
    required = {task, f"configs/splits/{fp['set']}.json", f"dataset/{fp['set']}/SHA256SUMS"}
    required.update(name for name in fp["files"] if name.startswith("configs/tasks/lists/"))
    if not required <= fp["files"].keys():
        raise ValueError("historical item evidence unavailable")
    for name in required:
        if sha256_file(inside(root, name)) != fp["files"][name]:
            raise ValueError("historical item inputs differ")
    return task
