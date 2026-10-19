"""감사 입력/소스 파일 해시와 명시된 역사 호출 해시를 읽는다. 원문은 반환하지 않는다."""

import hashlib
from pathlib import Path

from jeveval.io import hashes, records, run_files
from jeveval.io.config import read_yaml
from jeveval.io.paths import inside

MODELS = ("clef", "clef_flash", "pplx_v1", "pplx_v1_1", "b1_qwen3_8_27b", "b1_qwen3_8_27b_fp8")
FROZEN = MODELS[3:]


def inputs(root, set_name):
    names = ["configs/tasks/b1.yaml", "configs/datasets.yaml", "configs/splits/rules.yaml", "configs/policy.yaml",
             "configs/t0/fixture_v1.json", "audits/kosgd_audit/audit_result.json", f"configs/splits/{set_name}.json",
             f"dataset/{set_name}/SHA256SUMS", f"dataset/{set_name}/extended_schema.json"]
    names += [f"configs/tasks/{set_name}_{v}.yaml" for v in ("full", "actions_only")]
    names += [p.relative_to(root).as_posix() for p in sorted((root / "configs/tasks/lists").glob("*.json"))]
    names += [p.relative_to(root).as_posix() for p in sorted((root / "dataset" / set_name).glob("dialogues_*.json"))]
    if set_name == "kosgd2":
        names += ["configs/sets/kosgd2.yaml", "audits/kosgd2_selection/selection.json"]
    tokenizers = {}
    for model in MODELS:
        name = f"configs/models/{model}.yaml"
        names.append(name)
        cfg = read_yaml(root / name)
        for relative in cfg["tokenizer"]["files_sha256"]:
            path = Path(cfg["tokenizer"]["path"]) / relative
            tokenizers[f"{model}/{relative}"] = hashes.sha256_file(path) if path.is_file() else None
    return dict(files={n: hashes.sha256_file(root / n) if (root / n).is_file() else None for n in sorted(set(names))},
                tokenizers=tokenizers)


def code(root):
    paths = sorted((root / "audits/audit_v4").rglob("*.py"))
    files = {p.relative_to(root).as_posix(): hashes.sha256_file(p) for p in paths if "__pycache__" not in p.parts and "out" not in p.parts}
    digest = hashlib.sha256()
    for name, value in files.items():
        digest.update((name + "\0" + value + "\n").encode())
    return dict(files=files, audit_sha256=digest.hexdigest(), jeveval_sha256=hashes.code_sha256(root))


def historical(root, directories, models, frozen_inputs):
    output = []
    for directory in directories:
        try:
            folder = inside(root, directory)
            fp = run_files.read_json(folder / "fingerprint.json")
            if fp["set"] != "kosgd":
                raise ValueError("history set differs")
            dependencies = [fp["inputs"]["task_path"], fp["inputs"]["model_cfg_path"], "configs/tasks/b1.yaml", "configs/splits/kosgd.json"]
            dependencies += [p for p in frozen_inputs["files"] if p.startswith("configs/tasks/lists/")]
            if any(fp["files"].get(p) != frozen_inputs["files"][p] for p in dependencies):
                raise ValueError("history frozen inputs differ")
            planned = models[fp["model"]]["variants"][fp["variant"]]["calls"]
            checked, mismatch, seen = 0, 0, set()
            for stage in ("dev", "test"):
                finals, warnings = records.read_finals(folder / stage / "final.jsonl")
                if warnings:
                    raise ValueError("history records incomplete")
                for final in finals:
                    if final.derived_from is not None:
                        raise ValueError("derived history needs source run")
                    for call in final.calls:
                        mismatch += int(call.call_id in seen or call.call_id not in planned or planned[call.call_id]["planned"] != call.request_sha256)
                        seen.add(call.call_id)
                        checked += 1
            output.append(dict(model=fp["model"], variant=fp["variant"], run_id=fp["run_id"],
                               status="FAIL" if mismatch else "PASS" if checked and seen == set(planned) else "INCOMPLETE", checked=checked, mismatch=mismatch))
        except Exception:
            output.append(dict(status="INCOMPLETE", reason="history_unavailable_or_unlinked"))
    return dict(status="INCOMPLETE" if not output else ("FAIL" if any(r["status"] == "FAIL" for r in output) else
                "PASS" if all(r["status"] == "PASS" for r in output) else "INCOMPLETE"), runs=output)
