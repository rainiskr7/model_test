"""무엇: C2 명시 경로 정규화 · 입력: 검증된 파일 객체/run 정체성 · 출력: 비교 객체 · 계약 §9 C2."""

from copy import deepcopy
from pathlib import PurePosixPath


def origin(value, identity):
    """파생 출처의 run 경로 성분 하나만 바꾼다. 자유 문자열 치환은 하지 않는다."""
    if value is None:
        return None
    path = PurePosixPath(value)
    expected = (identity['model'], identity['run_id'], 'A', identity['set'], 'full')
    if path.is_absolute() or '..' in path.parts or path.parts[-5:] != expected:
        raise ValueError('invalid derived origin')
    parts = list(path.parts); parts[-4] = '<run>'
    return '/'.join(parts)


def artifact(name, value, identity, derived=False):
    """허용 경로: 최상위 run_id/risk threshold SHA/파생 dev 입력/비용 출처만."""
    result = deepcopy(value)
    if name in ('threshold.json', 'risk.json', 'scores.json', 'summary.json') and 'run_id' in result:
        if result['run_id'] != identity['run_id']:
            raise ValueError('artifact run identity')
        result['run_id'] = '<run>'
    if name == 'risk.json':
        result['threshold_sha256'] = '<verified threshold sha256>'
    if name == 'threshold.json' and derived:
        result['dev_input']['sha256'] = '<verified derived dev sha256>'
        result['dev_input']['nbytes'] = '<verified derived dev nbytes>'
    if name == 'scores.json':
        for stage in result['cost']['by_stage'].values():
            stage['derived_from'] = origin(stage['derived_from'], identity)
    return result


def final(value, identity):
    result = deepcopy(value)
    if 'derived_from' in result:
        result['derived_from'] = origin(result['derived_from'], identity)
    return result


def report(text, run_id):
    """추가 보조 절·감사 줄 및 명시 provenance 줄만 제외한다. 기존 수치는 남긴다."""
    lines, auxiliary = [], False
    boundaries = ('### ', '공통 오류 ', '비교 ', '미완·한계:', '사용자가 지정한', '판 4:')
    for line in text.splitlines():
        if line.startswith(('선택적 예측(보조,', '확신 변형(')):
            auxiliary = True
        if line.startswith(boundaries):
            auxiliary = False
        if auxiliary or not line.strip() or line.startswith('미완·한계:'):
            continue
        if line.startswith('code_sha256: ') or line.startswith(('replay dev: ', 'replay test: ', 'replay extra: ')):
            continue
        if line == f'# 실행 보고서 {run_id}':
            line = '# 실행 보고서 <run>'
        if line.startswith('비교 '):
            # compare ID만 가리고 set/variant 및 본문은 그대로 둔다.
            parts = line.split(' ', 2)
            line = '비교 <compare> ' + parts[2]
        lines.append(line)
    return lines
