"""무엇: C2 합성 run 복제 · 입력: 완료 Harness · 출력: 유효한 새 provenance · 계약 §9 C2."""

import json
import shutil
from jeveval.io import run_files
from jeveval.io.hashes import sha256_file


def copied(h):
    old = h.directory.parents[2]
    new = old.with_name('new_long_run')
    shutil.copytree(old, new)
    for path in new.glob('A/*/*/fingerprint.json'):
        _variant(path.parent, old.name, new.name)
    return old, new


def _origin(value, old, new):
    if value is None:
        return None
    parts = value.split('/')
    assert parts[-4] == old
    parts[-4] = new
    return '/'.join(parts)


def _variant(folder, old, new):
    for stage in ('dev', 'test', 'extra'):
        path = folder / stage / 'final.jsonl'
        if not path.exists(): continue
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        for r in rows:
            r['derived_from'] = _origin(r.get('derived_from'), old, new)
        path.write_text(''.join(json.dumps(r, ensure_ascii=False, separators=(',', ':'))+'\n' for r in rows))
        marker = folder / stage / 'derived.json'
        if marker.exists():
            value = run_files.read_json(marker)
            value['derived_from'] = _origin(value['derived_from'], old, new)
            run_files.write_json(marker, value)
    for name in ('fingerprint.json', 'threshold.json', 'risk.json', 'scores.json', 'summary.json'):
        path = folder / name
        if not path.exists(): continue
        v = run_files.read_json(path)
        if 'run_id' in v: v['run_id'] = new
        if name == 'fingerprint.json': v['inputs']['run_id'] = new
        if name == 'threshold.json':
            v['dev_input'].update(sha256=sha256_file(folder / 'dev/final.jsonl'), nbytes=(folder / 'dev/final.jsonl').stat().st_size)
        if name == 'risk.json': v['threshold_sha256'] = sha256_file(folder / 'threshold.json')
        if name == 'scores.json':
            for cell in v['cost']['by_stage'].values():
                cell['derived_from'] = _origin(cell['derived_from'], old, new)
        run_files.write_json(path, v)
    seal = run_files.read_json(folder / 'test/seal.json')
    seal.update(dev_final_sha256=sha256_file(folder / 'dev/final.jsonl'), threshold_sha256=sha256_file(folder / 'threshold.json'))
    run_files.write_json(folder / 'test/seal.json', seal)
