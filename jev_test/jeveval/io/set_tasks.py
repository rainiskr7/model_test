"""무엇: 셋 소유 task·주판 조회 · 입력: SetEntry/root · 출력: 경로/primary · 계약 판 5 보정 1 §1-1."""

from jeveval.io.config import load_taskspec
from jeveval.io.paths import identifier, inside

# 0906d42의 소유 경로. overlay를 읽어 제외하면 오류 격리가 깨지므로 양의 목록을 쓴다.
BASE_TASKS = {
    "kosgd": ("kosgd_full.yaml", "kosgd_actions_only.yaml"),
    "fc_call_decision": ("fc_call_decision.yaml",),
    "kmhas": ("kmhas.yaml",),
    "kote_escalation": ("kote_escalation.yaml",),
    "korfin_asc": ("korfin_asc.yaml",),
    "klue_mrc_answerable": ("klue_mrc_answerable.yaml",),
}


def primary_variant(root, selected):
    """자기 소유 task만 읽는다. 알 수 없는 공용 셋의 주판은 추정하지 않는다."""
    mapping = selected.dataset.get("map", {})
    if "primary_variant" in mapping:
        return identifier(mapping["primary_variant"])
    tasks = [load_taskspec(inside(root, name)) for name in selected.task_files]
    if any(t.set != selected.set_id for t in tasks):
        raise ValueError("base task ownership mismatch")
    variants = {t.variant for t in tasks}
    if len(variants) != 1:
        raise ValueError("SPEC_AMBIGUOUS: primary variant")
    return variants.pop()


def require_task(root, selected, task_path):
    """overlay 실행 task는 선언된 파일에 한정한다. 기존 호출 경로는 보존한다."""
    if selected.overlay_path and inside(root, task_path) not in {
            inside(root, name) for name in selected.task_files}:
        raise ValueError("task is not declared by overlay")
