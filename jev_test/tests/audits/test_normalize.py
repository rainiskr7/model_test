"""무엇: 명시 경로 정규화 · 입력: 허용/비허용 필드 · 출력: 보존 범위 · 계약 §9 C2."""

from audits.stage2_20261021 import normalize


def test_only_named_paths_change():
    fp = dict(model='m', set='s', run_id='old')
    value = dict(run_id='old', dev_input=dict(sha256='a', nbytes=1), arbitrary='old', seed='old')
    result = normalize.artifact('threshold.json', value, fp, True)
    assert result['run_id'] == '<run>' and result['dev_input']['nbytes'] != 1
    assert result['arbitrary'] == result['seed'] == 'old'
    assert value['dev_input']['sha256'] == 'a'
    assert normalize.origin('results/m/old/A/s/full', fp) == 'results/m/<run>/A/s/full'


def test_report_removes_only_new_sections_and_provenance():
    old = '# 실행 보고서 old\n### m / s / v\ncode_sha256: abc; started_at: now\n| .02 | FAILS |\n미완·한계: old'
    new = '# 실행 보고서 new\n### m / s / v\ncode_sha256: def; started_at: later\n| .02 | FAILS |\n선택적 예측(보조, 인증과 별개)\nnew data\n확신 변형(등록; 주 지표 인증과 별개)\nnew data\n미완·한계: new'
    assert normalize.report(old, 'old') == normalize.report(new, 'new')
    assert normalize.report(old, 'old') != normalize.report(new.replace('FAILS', 'MEETS'), 'new')
