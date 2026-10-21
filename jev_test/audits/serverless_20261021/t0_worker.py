"""무엇: 독립 T0 합성 실행 · 입력: 소스 트리/외부 scratch · 출력: 다섯 단계 파일·help · 계약 §8-7."""

import argparse
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from audits.stage2_20261021.test_runner import protect


def execute(tree, scratch):
    """기존 fixture factory·fake runtime·고정 AttemptResult를 그대로 재사용한다."""
    protect(ROOT)
    protect(tree)
    sys.path.insert(0, str(tree))
    import pytest
    from jeveval.io.t0_policy import read_t0_policy
    from jeveval.run import cmd_t0, cli
    from tests.t0_io.support import setup, inputs, stage, fake_post
    policy = read_t0_policy(tree / 'configs/t0/tolerance_v1.yaml')
    with pytest.MonkeyPatch.context() as patch:
        factory = setup.__wrapped__(scratch, patch, policy)
        for family in ('clef', 'pplx_v1', 'pplx_v1_1'):
            ctx = factory(family)
            # 지문도 실제 import한 코드 전체를 가리키게 한다.
            shutil.copytree(tree / 'jeveval', ctx.root / 'jeveval',
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            inputs(ctx)
            stage(ctx, 'reference', checkpoint='checkpoint', device='cpu', runtime=ctx.runtime)
            stage(ctx, 'server', base_url='http://127.0.0.1:1', post=fake_post())
            stage(ctx, 'tolerance', rounding='reference=4')
            stage(ctx, 'judge', rounding='reference=4,server=4')
        for name in ('inputs', 'reference', 'server', 'tolerance', 'judge'):
            stream = StringIO()
            with redirect_stdout(stream):
                try:
                    cli.main(['t0', name, '--help'])
                except SystemExit as exc:
                    if exc.code != 0: raise
            (scratch / f'{name}.help.txt').write_text(stream.getvalue())


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--tree', type=Path, required=True)
    parser.add_argument('--scratch', type=Path, required=True)
    args = parser.parse_args(argv)
    tree, scratch = args.tree.resolve(), args.scratch.resolve()
    if scratch.exists() or any(scratch.is_relative_to(root) for root in (ROOT, tree)):
        raise ValueError('new external scratch required')
    scratch.mkdir(parents=True)
    execute(tree, scratch)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
