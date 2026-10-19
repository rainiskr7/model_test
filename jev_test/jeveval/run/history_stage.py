"""무엇: 검증한 역사 단계 재구성 · 입력: History·단계 · 출력: StageData · 계약 §5-1b."""

from jeveval.io.history_inputs import checked_task
from jeveval.io.config import load_taskspec
from jeveval.io.models import load_model_config
from jeveval.io.paths import inside
from jeveval.io.tasks import read_b1_config
from jeveval.run import history_check, stage_inputs
from jeveval.run.plan_calls import plan_calls
from jeveval.score.tasks import outcome
from jeveval.types import StageData


def restore(root, history, name):
    """현재 fingerprint 대조 대신 동결 입력과 실제 호출 해시를 대조한다. 파생은 보수적으로 거부한다."""
    checked = history_check.check(history)
    if checked.status == "damaged" or not any(s.name == name and s.status == "verified_complete" for s in checked.stages):
        raise ValueError("verified historical stage required")
    task_path = checked_task(root, history)
    task = load_taskspec(inside(root, task_path))
    fp = history.artifacts["fingerprint.json"]
    cfg = load_model_config(inside(root, fp["inputs"]["model_cfg_path"]))
    b1 = read_b1_config(inside(root, "configs/tasks/b1.yaml"))
    items = stage_inputs.load_items(root=root, task_path=task_path, stage=name)
    by_id = {f"{i.set}:{i.group_id}:{i.item_id}": i for i in items}
    stage = next(s for s in history.stages if s.name == name)
    if set(by_id) != {f.logical_id for f in stage.finals}:
        raise ValueError("historical Item identity differs")
    for final in stage.finals:
        if final.derived_from is not None:
            raise ValueError("historical derived reconstruction is unspecified")
        plans = plan_calls(by_id[final.logical_id], task, cfg, b1)
        if {p.call_id: p.request_sha256 for p in plans} != {c.call_id: c.request_sha256 for c in final.calls}:
            raise ValueError("historical request bytes differ")
    return StageData(stage.finals, by_id, [outcome(f, by_id[f.logical_id], name) for f in stage.finals], stage.warnings)
