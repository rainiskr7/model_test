"""무엇: T0 CLI 조립 · 입력: 단계 인자/주입 seam · 출력: 단계 요약 · 계약 §8-1·§8-7."""

from pathlib import Path

from jeveval.io import t0_chain, t0_fingerprint, t0_inputs
from jeveval.io.models import load_model_config
from jeveval.io.reference import local_checkpoint
from jeveval.io.paths import inside
from jeveval.reference import t0_runner
from jeveval.run import t0_evaluate, t0_reference, t0_server


def configure(commands):
    parser = commands.add_parser("t0")
    stages = parser.add_subparsers(dest="stage", required=True)
    inputs = stages.add_parser("inputs")
    inputs.add_argument("--model", required=True)
    inputs.add_argument("--run-id", required=True)
    inputs.add_argument("--fixture", default="configs/t0/fixture_v1.json")
    inputs.add_argument("--results", default="results")
    inputs.add_argument("--reference-name")
    for name in ("reference", "server", "tolerance", "judge"):
        stage = stages.add_parser(name)
        stage.add_argument("--run-dir", required=True)
        if name == "reference":
            stage.add_argument("--checkpoint", required=True)
            stage.add_argument("--device", default="cuda")
        elif name == "server":
            stage.add_argument("--base-url", required=True)
            stage.add_argument("--timeout", type=float, default=600)
        else:
            stage.add_argument("--rounding")
            if name == "judge":
                stage.add_argument("--no-reference", action="store_true")


def run(*, root, stage, model=None, run_id=None, fixture="configs/t0/fixture_v1.json",
        results="results", reference_name=None, run_dir=None, checkpoint=None, device="cuda",
        base_url=None, timeout=600, rounding=None, no_reference=False, sources=None,
        boundary_builder=None, measurer=None, runtime=None, post=None):
    root = Path(root)
    if stage == "inputs":
        cfg = load_model_config(inside(root, model))
        directory = inside(root, f"{results}/_t0/{t0_inputs.identifier(cfg.id)}/{t0_inputs.identifier(run_id)}")
        bundle = t0_inputs.freeze(directory / "inputs.jsonl", inside(root, fixture), cfg, root, run_id,
            sources=sources, reference_name=reference_name, boundary_builder=boundary_builder, measurer=measurer)
        t0_fingerprint.initialize(directory, bundle, root)
        return dict(ok=True, cases=len(bundle.rows), inputs_sha256=bundle.sha256)
    directory = inside(root, run_dir)
    bundle = t0_inputs.load(directory / "inputs.jsonl")
    t0_chain.fingerprint(directory, bundle)
    if stage == "reference":
        if checkpoint is None:
            raise ValueError("local checkpoint required")
        limit = bundle.metadata["config"]["limit"]["tokens"]
        if type(limit) is not int or limit <= 0:
            raise ValueError("limit.tokens is required for reference execution")
        # 실제 가중치는 GPU 장비의 저장소 밖 폴더에 있다 — 로컬 폴더이기만 하면 된다 (H·I, 다운로드 금지).
        path = Path(checkpoint)
        checkpoint = local_checkpoint(path if path.is_absolute() else root / path)
        runtime = runtime or t0_runner.load(bundle.metadata["model"], checkpoint, device=device, max_length=limit)
        return t0_reference.execute(directory, bundle, runtime, checkpoint, device)
    if stage == "server":
        options = {} if post is None else {"post": post}
        return t0_server.execute(directory, bundle, base_url, timeout=timeout, **options)
    if stage == "tolerance":
        return t0_evaluate.tolerance(directory, bundle, rounding)
    if stage == "judge":
        return t0_evaluate.evaluate(directory, bundle, rounding, no_reference)
    raise ValueError("unknown T0 stage")
