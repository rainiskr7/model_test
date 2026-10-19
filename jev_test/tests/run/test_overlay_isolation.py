"""무엇: overlay 격리 통합 · 입력: 합성 완료 run/무관 오류 · 출력: 요청·분할·역사 불변 · 계약 판 5 보정 1 §9."""

from pathlib import Path

from jeveval.io import history, report_inputs
from jeveval.io.config import read_yaml
from jeveval.io.set_config import entry
from jeveval.io.splits import split_bytes
from jeveval.run import context, history_stage
from jeveval.run.make_splits import _make_plan
from jeveval.run.plan_calls import plan_calls
from jeveval.run.stage_inputs import load_items
from tests.run.cli_support import Harness, put_yaml


def snapshot(h, saved):
    selected = entry(h.root, h.set)
    ctx = context.configuration(h.root, h.args["model"], h.args["task"])
    items = load_items(root=h.root, task_path=h.args["task"], stage="dev")
    plan = _make_plan(h.set, selected.split_rules, {"seed": 1, "dev_fraction": .5}, h.root, selected)
    return (selected, items, [p.request_sha256 for i in items for p in plan_calls(i, ctx.task, ctx.cfg, ctx.b1)],
            split_bytes(plan), context.primary_variant(ctx), report_inputs.metadata(h.root, h.set, "default"),
            context.fingerprint(ctx, "r1", "fixed"), history_stage.restore(h.root, saved, "dev"))


def test_unrelated_overlay_and_task_cannot_change_existing_execution(tmp_path, monkeypatch):
    h = Harness(tmp_path)
    cfg = read_yaml(tmp_path / "configs/splits/rules.yaml")
    cfg["sets"][h.set].update(group_key="context", pool={"kind": "all"})
    put_yaml(tmp_path / "configs/splits/rules.yaml", cfg)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("JEV_TEST_KEY", "synthetic-key")
    h.finish()
    saved = history.read(tmp_path, h.directory)
    before = snapshot(h, saved)
    overlay = tmp_path / "configs/sets/unrelated.yaml"
    task = tmp_path / "configs/tasks/unrelated.yaml"
    for text in ("broken: [", "schema: wrong", "id: klue_mrc_answerable", "lists: {}"):
        overlay.parent.mkdir(exist_ok=True)
        overlay.write_text(text)
        task.write_text(text)
        assert snapshot(h, saved) == before
    overlay.unlink()
    task.unlink()
    assert snapshot(h, saved) == before
    # 디렉터리나 무관 task를 읽기만 해도 실패하도록 하여 값만 우연히 같은 경우를 배제한다.
    original = Path.open
    def guarded(path, *args, **kwargs):
        assert "sets" not in path.parts and path.name != "unrelated.yaml"
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", guarded)
    assert snapshot(h, saved) == before
