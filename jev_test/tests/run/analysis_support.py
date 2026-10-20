"""무엇: 다중 선언 합성 run · 입력: tmp_path/선언 종류 · 출력: dev 완료 Harness · 계약 §9."""

import shutil
from jeveval.io.config import read_yaml
from jeveval.run import cmd_score_variants
from tests.run.cli_support import Harness, REPO
from tests.run.file_support import put_yaml


def prepared(tmp_path, monkeypatch, kinds=('question_risk', 'score_variants')):
    h = Harness(tmp_path, 'kosgd2', 'full')
    shutil.copytree(REPO / 'configs/analysis', tmp_path / 'configs/analysis')
    path = tmp_path / 'configs/sets/kosgd2.yaml'
    value = read_yaml(path)
    names = dict(question_risk='question_risk_v2', score_variants='score_variants_v1')
    if kinds:
        value['analysis'] = {k: f'configs/analysis/{names[k]}.yaml' for k in kinds}
    put_yaml(path, value)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('JEV_TEST_KEY', 'synthetic')
    h.run('dev'); assert h.command('threshold') == 0
    return h


def thresholds(h, kinds=('question_risk', 'score_variants')):
    if 'question_risk' in kinds:
        assert h.command('question-threshold') == 0
    if 'score_variants' in kinds:
        assert cmd_score_variants.run(root=h.root, run_dir=h.directory, mode='threshold')['ok']
