"""무엇: 감사 존재/연결 검사 · 입력: 합성 증거 · 출력: 보고 범위 · 계약 §7-6."""

from jeveval.io import audit_evidence, run_files
from tests.run.history_support import finished


def test_missing_linked_and_stale_audit(tmp_path, monkeypatch):
    h = finished(tmp_path, monkeypatch, "kosgd", "full")
    assert audit_evidence.summary(tmp_path, h.directory) is None
    fp = run_files.read_json(h.directory / "fingerprint.json")
    audit = dict(schema="audit_v4/1", set="kosgd", profile="kosgd", retrospective=True,
                 inputs=dict(files=fp["files"]), code=dict(audit_sha256="a"*64),
                 models=dict(synthetic=dict(variants=dict(full=dict(measurement_config=False)))),
                 per_variant=dict(full={r: dict(status="PASS") for r in audit_evidence.RULES}),
                 historical_calls=dict(status="INCOMPLETE"))
    target = tmp_path / "audits/audit_v4/out/kosgd.json"
    target.parent.mkdir(parents=True)
    run_files.write_json(target, audit)
    text = audit_evidence.summary(tmp_path, h.directory)
    assert "사후 감사" in text and "script=aaaaaaaaaaaa" in text and "뒷받침" in text
    audit["inputs"]["files"][fp["inputs"]["task_path"]] = "b"*64
    run_files.write_json(target, audit)
    assert "연결 불가" in audit_evidence.summary(tmp_path, h.directory)


def test_only_audit_line_changes_and_existing_report_is_preserved(tmp_path, monkeypatch):
    from jeveval.run import cmd_report
    import pytest
    h = finished(tmp_path, monkeypatch, "kosgd", "full")
    cmd_report.run(root=tmp_path, run_id="r1", models=["synthetic"], out="before.md")
    before = (tmp_path / "before.md").read_bytes()
    fp = run_files.read_json(h.directory / "fingerprint.json")
    audit = dict(schema="audit_v4/1", set="kosgd", profile="kosgd", retrospective=True,
                 inputs=dict(files=fp["files"]), code=dict(audit_sha256="a"*64),
                 models=dict(synthetic=dict(variants=dict(full=dict(measurement_config=False)))),
                 per_variant=dict(full={r: dict(status="PASS") for r in audit_evidence.RULES}),
                 historical_calls=dict(status="PASS"))
    path = tmp_path / "audits/audit_v4/out/kosgd.json"
    path.parent.mkdir(parents=True)
    run_files.write_json(path, audit)
    cmd_report.run(root=tmp_path, run_id="r1", models=["synthetic"], out="after.md")
    after = (tmp_path / "after.md").read_bytes()
    strip = lambda b: [line for line in b.decode().splitlines() if not line.startswith("미완·한계:")]
    assert strip(before) == strip(after) and before != after
    assert (tmp_path / "before.md").read_bytes() == before
    with pytest.raises(ValueError):
        cmd_report.run(root=tmp_path, run_id="r1", models=["synthetic"], out="before.md")


def test_explicit_paths_confined_and_do_not_select_newest(tmp_path, monkeypatch):
    import pytest
    from jeveval.io.hashes import sha256_file
    from tests.score.test_audit_selection import evidence
    h = finished(tmp_path, monkeypatch, "kosgd2", "full")
    fp = run_files.read_json(h.directory / "fingerprint.json")
    audit, _ = evidence()
    audit['inputs']['files'] = fp['files']
    audit['models'] = {'synthetic': audit['models']['m']}
    folder = tmp_path / 'audits/audit_v4/out'; folder.mkdir(parents=True)
    chosen = folder / 'kosgd2.old.json'; newer = folder / 'kosgd2.99999999.json'
    run_files.write_json(chosen, audit); newer.write_text('{')
    digest = sha256_file(chosen)
    selected = audit_evidence.overrides(tmp_path, ['kosgd2=audits/audit_v4/out/kosgd2.old.json'])
    text = audit_evidence.summary(tmp_path, h.directory, selected['kosgd2'])
    assert 'synthetic' in text and 'kosgd2.old.json' in text and digest[:12] in text
    assert sha256_file(chosen) == digest
    for values in (['kosgd2=README.md'], ['kosgd2=audits/audit_v4/out/a.json']*2):
        with pytest.raises(ValueError): audit_evidence.overrides(tmp_path, values)


def derived_audit(tmp_path, monkeypatch):
    """실제 파생 명령으로 만든 합성 기록에만 원천 PASS를 연결한다."""
    h = finished(tmp_path, monkeypatch, 'kosgd', 'full')
    full = h.directory
    h.variant = 'actions_only'; h.finish()
    fingerprints = {v: run_files.read_json(full.parent / v / 'fingerprint.json') for v in ('full', 'actions_only')}
    audit = dict(schema='audit_v4/1', set='kosgd', profile='kosgd', retrospective=True,
        inputs=dict(files={k: v for fp in fingerprints.values() for k, v in fp['files'].items()}),
        code=dict(audit_sha256='a'*64), models=dict(synthetic=dict(variants={v:
            dict(measurement_config=False, request_mode='hypothetical_direct' if v == 'actions_only' else 'executor_capture')
            for v in fingerprints})), per_variant={v: {r: dict(status='PASS') for r in audit_evidence.RULES}
            for v in fingerprints}, historical_calls=dict(runs=[dict(model='synthetic', set='kosgd',
                variant='full', run_id='r1', status='PASS')]))
    path = tmp_path / 'audits/audit_v4/out/kosgd.json'; path.parent.mkdir(parents=True)
    run_files.write_json(path, audit)
    return h, full, path, audit


def test_derived_source_link_keeps_hypothetical_scope(tmp_path, monkeypatch):
    h, full, path, audit = derived_audit(tmp_path, monkeypatch)
    audit['per_variant']['actions_only']['R4']['status'] = 'FAIL'
    run_files.write_json(path, audit)
    text = audit_evidence.summary(tmp_path, h.directory)
    assert '파생 출처 검증 PASS' in text and '원천 full 저장 호출 연결 PASS' in text
    assert '이어지는 actions_only 규칙은 가상 직접 요청 감사' in text and '자체 전송의 증거가 아님' in text
    assert 'R4=FAIL' in text and '원문 대응' in text
    assert '파생 변형' not in audit_evidence.summary(tmp_path, full)


import pytest


@pytest.mark.parametrize('attack', ['missing_source', 'missing_marker', 'stage_origin', 'model', 'run_id',
                                    'set', 'joint', 'FAIL', 'INCOMPLETE', 'request_hash'])
def test_derived_unverified_provenance_never_promotes(tmp_path, monkeypatch, attack):
    h, full, path, audit = derived_audit(tmp_path, monkeypatch)
    if attack in ('FAIL', 'INCOMPLETE'):
        audit['historical_calls']['runs'][0]['status'] = attack
        run_files.write_json(path, audit)
    elif attack == 'missing_source':
        (full / 'fingerprint.json').unlink()
    elif attack == 'missing_marker':
        (h.directory / 'dev/derived.json').unlink()
    elif attack in ('model', 'run_id', 'set'):
        fp = run_files.read_json(full / 'fingerprint.json'); fp[attack] = 'other'
        run_files.write_json(full / 'fingerprint.json', fp)
    elif attack == 'joint':
        from jeveval.io.config import read_yaml
        from tests.run.file_support import put_yaml
        model = tmp_path / 'configs/models/synthetic.yaml'
        cfg = read_yaml(model); cfg['question_scoring'] = 'joint'; put_yaml(model, cfg)
    else:
        import json
        target = h.directory / 'test/final.jsonl'
        value = json.loads(target.read_text())
        if attack == 'stage_origin': value['derived_from'] = 'results/synthetic/other/A/kosgd/full'
        else: value['calls'][0]['request_sha256'] = 'b'*64
        target.write_text(json.dumps(value) + '\n')
    text = audit_evidence.summary(tmp_path, h.directory)
    assert '원천 full 저장 호출 연결 PASS' not in text and '연결 미확인' in text
