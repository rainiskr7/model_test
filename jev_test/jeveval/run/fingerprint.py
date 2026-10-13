"""무엇: 불변 실행 입력 식별 · 입력: root·설정·run · 출력: fingerprint · 계약 §1-2·§8-6 F/G."""

from pathlib import Path

from jeveval.io import hashes
from jeveval.io.config import load_taskspec
from jeveval.io.models import load_model_config
from jeveval.run.encoders import ENCODERS


def build_fingerprint(*, root, run_id, model_cfg_path, task_path, set_name,
                      variant, started_at) -> dict:
    """원본·토크나이저를 검증한 뒤 설정과 규칙 소스의 실제 바이트를 식별한다."""
    root = Path(root).resolve()
    model_path, task_path = (root / model_cfg_path).resolve(), (root / task_path).resolve()
    inputs = dict(model_cfg_path=model_path.relative_to(root).as_posix(),
                  task_path=task_path.relative_to(root).as_posix(), set=set_name,
                  variant=variant, run_id=run_id)
    cfg, task = load_model_config(model_path), load_taskspec(task_path)
    if task.set != set_name or task.variant != variant:
        raise ValueError("fingerprint task identity mismatch")
    dataset = root / "dataset" / set_name
    if hashes.verify_dir(dataset):
        raise ValueError("dataset hash mismatch")
    paths = [task_path, root / "configs/tasks/b1.yaml", root / "configs/datasets.yaml",
             root / "configs/splits" / f"{set_name}.json", model_path,
             dataset / "SHA256SUMS", *hashes.glob_files(root / "configs/tasks/lists", "*.json")]
    files = {p.relative_to(root).as_posix(): hashes.sha256_file(p) for p in sorted(set(paths))}
    rule, encoder = cfg.encoder["rule"], None
    if rule is not None:
        if rule not in ENCODERS:
            raise ValueError("unknown encoder rule")
        module = ENCODERS[rule].__module__
        encoder = dict(rule=rule, sha256=hashes.sha256_file(
            root / (module.replace(".", "/") + ".py")))
    path = cfg.tokenizer["path"]
    tokenizer = None if path is None else hashes.tokenizer_sha256(
        root / path, cfg.tokenizer["files_sha256"])
    return dict(schema="fingerprint/1", run_id=run_id, model=cfg.id, set=set_name,
                variant=variant, inputs=inputs, files=files, dataset_verified=True, encoder=encoder,
                tokenizer=tokenizer, code_sha256=hashes.code_sha256(root), started_at=started_at)


def same_fingerprint(old: dict, new: dict) -> bool:
    """최상위 started_at만 제외하고 중첩 값을 그대로 비교한다."""
    return ({k: v for k, v in old.items() if k != "started_at"}
            == {k: v for k, v in new.items() if k != "started_at"})
