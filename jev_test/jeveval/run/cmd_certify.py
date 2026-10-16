"""무엇: 봉인 인증 명령 · 입력: 동결 입력/개발 기록 · 출력: (a)(b)(c) · 계약 §5-7."""

from datetime import datetime

from jeveval.io import run_files
from jeveval.io.paths import file_info
from jeveval.run import context
from jeveval.io.hashes import sha256_file
from jeveval.run.cmd_threshold import recompute
from jeveval.types import ThresholdFile


def run(*, root, run_dir):
    ctx = context.restore(root, run_dir)
    dev = context.stage(ctx, "dev")
    directory = ctx.directory
    threshold = run_files.read_json(directory / "threshold.json", ThresholdFile)
    seal = run_files.read_json(directory / "test/seal.json")
    risk = run_files.read_json(directory / "risk.json")
    context.check_identity(ctx, threshold.to_dict())
    context.check_identity(ctx, risk)
    current = recompute(ctx, dev)
    checks = dict(a=current.dev_input["sha256"] == threshold.dev_input["sha256"] == seal["dev_final_sha256"],
                  b=current.to_dict()["by_tau"] == threshold.to_dict()["by_tau"],
                  c=sha256_file(directory / "threshold.json") == seal["threshold_sha256"] ==
                    risk["threshold_sha256"])
    sealed = datetime.fromisoformat(seal["sealed_at"])
    if sealed.tzinfo is None:
        raise ValueError("seal timestamp requires timezone")
    warnings = list(dev.warnings)
    if file_info(directory / "threshold.json")[1] > sealed.timestamp():
        warnings.append("threshold_mtime_after_seal")
    return dict(ok=all(checks.values()), checks=checks, warnings=warnings)
