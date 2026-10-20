"""무엇: C2 바이트 증거 확인 · 입력: 명시 변형 폴더 · 출력: 검증된 객체/정체성 · 계약 §9 C2."""

from hashlib import sha256
import json


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def _nonfinite(value):
    raise ValueError('nonfinite JSON')


def parse(payload):
    return json.loads(payload, object_pairs_hook=_unique, parse_constant=_nonfinite)


def read(path):
    payload = path.read_bytes()
    value = parse(payload)
    canonical = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=1, allow_nan=False)+'\n').encode()
    if payload != canonical:
        raise ValueError('noncanonical artifact bytes')
    return value


def digest(path):
    payload = path.read_bytes()
    return sha256(payload).hexdigest(), len(payload)


def variant(directory):
    """원본 해시·크기를 먼저 검증한다. 불일치를 정규화로 숨기지 않는다."""
    fp = read(directory / 'fingerprint.json')
    stages = ('dev', 'test', 'extra') if fp['set'] == 'fc_call_decision' else ('dev', 'test')
    values = {n: read(directory / n) for n in ('threshold.json', 'risk.json', 'scores.json')}
    for name, value in values.items():
        if any(value[k] != fp[k] for k in ('model', 'set', 'variant', 'run_id')):
            raise ValueError('artifact identity')
    if (directory / 'summary.json').exists():
        values['summary.json'] = read(directory / 'summary.json')
    dev_sha, dev_size = digest(directory / 'dev/final.jsonl')
    threshold_sha, _ = digest(directory / 'threshold.json')
    if (values['threshold.json']['dev_input']['sha256'], values['threshold.json']['dev_input']['nbytes']) != (dev_sha, dev_size):
        raise ValueError('dev evidence mismatch')
    seal = read(directory / 'test/seal.json')
    if (seal['dev_final_sha256'] != dev_sha or seal['threshold_sha256'] != threshold_sha or
            values['risk.json']['threshold_sha256'] != threshold_sha):
        raise ValueError('seal or risk evidence mismatch')
    finals, derived = {}, {}
    for stage in stages:
        payload = (directory / stage / 'final.jsonl').read_bytes()
        if payload and not payload.endswith(b'\n'):
            raise ValueError('incomplete final line')
        rows = [parse(line) for line in payload.splitlines()]
        if payload != record_bytes(rows):
            raise ValueError('noncanonical final bytes')
        marker = directory / stage / 'derived.json'
        source = read(marker)['derived_from'] if marker.exists() else None
        if any(r.get('derived_from') != source for r in rows):
            raise ValueError('derived evidence mismatch')
        finals[stage], derived[stage] = rows, source is not None
    return fp, values, finals, derived


def record_bytes(rows):
    return ''.join(json.dumps(r, ensure_ascii=False, allow_nan=False, separators=(',', ':'))+'\n'
                   for r in rows).encode()
