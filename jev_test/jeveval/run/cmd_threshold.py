"""무엇: 개발 임계값 명령 · 입력: 실행 폴더 · 출력: threshold.json · 계약 §5-7·⑥b R3."""

from jeveval.io import run_files, run_inputs
from jeveval.io.hashes import sha256_file
from jeveval.score.threshold import threshold_file


def recompute(ctx, dev):
    path = ctx.directory / "dev/final.jsonl"
    return threshold_file(**run_inputs.identity(ctx), dev_sha256=sha256_file(path),
        dev_nbytes=run_inputs.file_info(path)[0], dev=dev.outcomes)


def run(*, root, run_dir):
    ctx = run_inputs.restore(root, run_dir)
    if run_files.exists(ctx.directory / "test/seal.json"):
        raise ValueError("threshold is sealed")
    dev = run_inputs.stage(ctx, "dev")
    result = recompute(ctx, dev)
    run_files.write_json(ctx.directory / "threshold.json", result)
    return dict(ok=True, warnings=dev.warnings)
