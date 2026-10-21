"""무엇: kosgd2 등록 단계 상태 · 입력: root/run · 출력: create/skip/stop · 계약 §7-4b·7-4d."""

from pathlib import Path
import sys
import yaml

from jeveval.io import analysis_artifacts, question_registration as question_io, run_files
from jeveval.io.paths import inside
from jeveval.run import context, question_registration, variant_registration
from jeveval.run.cmd_threshold import recompute
from jeveval.run.cmd_run import read_resume_inputs
from jeveval.run.seal import check_seal
from jeveval.score.question_outcomes import observations
from jeveval.score.question_risk import thresholds

PHASES = ('dev', 'threshold', 'question-threshold', 'variant-threshold', 'test')


def next_registration_action(state):
    """상태만으로 결정한다. 미지 상태도 실행으로 통과시키지 않는다."""
    return {'missing': 'create', 'ready': 'skip', 'sealed': 'skip'}.get(state, 'stop')


def _threshold_states(ctx, dev, question, variant):
    """기존 재계산과 등록 검사기를 조립한다. 봉인 증거를 파일 존재로 대신하지 않는다."""
    directory = ctx.directory
    ordinary = run_files.exists(directory / 'threshold.json')
    qpresent = 'question_threshold.json' in question['artifacts']
    vpresent = 'variant_threshold.json' in variant['artifacts']
    started = question['started']
    if (qpresent or vpresent or started) and not ordinary:
        raise ValueError('ordinary threshold missing')
    if ordinary and run_files.read_json(directory / 'threshold.json') != recompute(ctx, dev).to_dict():
        raise ValueError('ordinary threshold differs')
    states = dict(threshold='ready' if ordinary else 'missing')
    checks = ((question, qpresent, 'question-threshold', lambda: question_registration.check(
               question, thresholds(observations(dev.finals, dev.items, 'dev')), sealed=started)),
              (variant, vpresent, 'variant-threshold', lambda: variant_registration.check_development(
               variant, dev, sealed=started)))
    for evidence, present, phase, validate in checks:
        if evidence['errors'] or evidence['manifest'] is None or evidence['policy']['status'] != 'registered':
            raise ValueError('registered declarations required')
        if (present or started) and validate() != 'registered':
            raise ValueError('registration damaged')
        states[phase] = ('sealed' if started else 'ready') if present else 'missing'
    if vpresent and not qpresent:
        raise ValueError('question threshold must precede variant threshold')
    if started and check_seal(directory):
        raise ValueError('main seal damaged')
    return states


def read_registration_state(root, directory):
    """불완전 dev는 재개할 수 있지만 등록 손상은 전 단계 실행을 막는다."""
    state = dict.fromkeys(PHASES, 'missing')
    try:
        directory = inside(root, directory)
        if not directory.exists():
            return state
        ctx = context.restore(root, directory)
        if ctx.task.set != 'kosgd2':
            raise ValueError('kosgd2 required')
        question = question_io.read(root, directory)
        variant = analysis_artifacts.read(root, directory)
        try:
            dev = context.stage(ctx, 'dev')
        except ValueError:
            if question['started'] or any(run_files.exists(directory / name) for name in
                    ('threshold.json', 'question_threshold.json', 'variant_threshold.json')):
                raise
            return state
        if dev.warnings:
            raise ValueError('undamaged dev required')
        read_resume_inputs(ctx, 'dev', list(dev.items.values()), allow_tail=False)
        state.update(_threshold_states(ctx, dev, question, variant))
        state['dev'] = 'ready'
        if question['started']:
            try:
                trial = context.stage(ctx, 'test')
            except ValueError:
                return state
            if trial.warnings:
                raise ValueError('test warnings')
            read_resume_inputs(ctx, 'test', list(trial.items.values()), allow_tail=False)
            state['test'] = 'sealed'
        return state
    except (ValueError, OSError, KeyError, TypeError, AttributeError, yaml.YAMLError):
        return dict.fromkeys(PHASES, 'damaged')


def main(argv=None):
    """shell에는 고정 action만 출력하며 오류 원문을 내보내지 않는다."""
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2 or args[1] not in (*PHASES, 'preflight'):
        return 2
    states = read_registration_state(Path.cwd(), args[0])
    action = ('stop' if 'damaged' in states.values() else 'skip') if args[1] == 'preflight' else (
        next_registration_action(states[args[1]]))
    print(action)
    return 2 if action == 'stop' else 0


if __name__ == '__main__':
    raise SystemExit(main())
