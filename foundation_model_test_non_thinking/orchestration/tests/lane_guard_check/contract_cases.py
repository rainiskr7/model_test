"""5b model arguments distinguish lanes sharing one track entry."""

import os

from orchestration.tests.lane_guard_check.fixture import Fixture
from orchestration.tests.lane_guard_check.model_cases import process
from orchestration.tests.lane_guard_check.owned import Owned, ps_field
from orchestration.tests.lane_guard_check.report import Inconclusive


def two_lanes(fixture):
    rows = [f'{model}_kmmlu|kmmlu|{model}|fixture.invalid|FIXTURE_KEY|fixture-{model}'
            for model in ('a', 'b')]
    (fixture.orch / 'lanes.conf').write_text('\n'.join(rows) + '\n')
    fixture.env.pop('LANEGUARD_LANES', None)


def same_track_case(repo, root, target, report):
    f = Fixture(repo, root / 'same_track_models', target)
    two_lanes(f)
    script = f.orch / 'lanes/kmmlu.sh'
    f.table({'800001': process(f'/bin/bash {script} a'),
             '800002': process(f'/bin/bash {script} b')})
    f.cycle()
    for model, pid in (('a', '800001'), ('b', '800002')):
        report.check(f'C5b.3 {model}_kmmlu distinct root',
                     f'{model}_kmmlu: 레인 식별 root={pid} ' in f.log())
        report.check(f'C5b.3 {model}_kmmlu state ownership',
                     (f.base / 'state' / f'{model}_kmmlu.state').read_text().startswith(f'state|{pid}:'))
    report.check('C5b.3 other model is neither duplicate nor unsupported',
                 '미지원' not in f.log() and '레인 2개 이상' not in f.log() and not f.signals())
    f.values('down', '84 96')
    f.cycle(2)
    report.check('C5b.3 each model owns its STOP', f.stopped())
    f.values('up', '72 85')
    f.cycle(3)
    report.check('C5b.3 each model resumes its own root',
                 all(row['stat'] == 'S' for row in f.records().values()))


def same_track_real_case(repo, root, target, report):
    if ps_field(os.getpid(), 'pid') != str(os.getpid()):
        raise Inconclusive('owned-PID ps unavailable')
    f = Fixture(repo, root / 'same_track_real', target, mode='real')
    two_lanes(f)
    owned = Owned(f)
    try:
        groups = {model: owned.launch(f.orch / 'lanes/kmmlu.sh', model, [model])
                  for model in ('a', 'b')}
        f.cycle()
        for model, pids in groups.items():
            report.check(f'C5b.4 real {model}_kmmlu root',
                         f'{model}_kmmlu: 레인 식별 root={pids[0]} ' in f.log())
        report.check('C5b.4 distinct owned roots', groups['a'][0] != groups['b'][0])
    finally:
        owned.close()


def invalid_rows_case(repo, root, target, report):
    f = Fixture(repo, root / 'invalid_rows', target)
    rows = ['a|a|host|KEY|model', 'a_kmmlu|kmmlu|a|host|KEY|model|',
            'a_kmmlu|kmmlu|a|host|KEY|model|extra', 'wrong|kmmlu|a|host|KEY|model',
            'a_bad|bad|a|host|KEY|model', 'A_kmmlu|kmmlu|A|host|KEY|model',
            'a_kmmlu|kmmlu|a||KEY|model']
    for index, row in enumerate(rows):
        f.env['LANEGUARD_LANES'] = row
        try:
            f.cycle()
        except RuntimeError as exc:
            report.check(f'C5b.3 invalid row {index} rejected', 'guard rc=4:' in str(exc))
        else:
            report.check(f'C5b.3 invalid row {index} rejected', False)
    report.check('C5b.3 invalid rows signal nothing', not f.signals())
