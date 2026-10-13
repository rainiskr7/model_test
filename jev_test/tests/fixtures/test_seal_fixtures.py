"""무엇: 봉인 fixture 독립 대조 · 입력: 기록 바이트·해시 · 출력: 판정 · 계약 §5-5·§5-7."""

import hashlib
import json

from jeveval.types import FinalRecord, ThresholdFile
from reference_scoring import threshold_reference
from test_fixtures_wellformed import ROOT, read


def sha(raw):
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def test_seal_content_and_mtime():
    for case in read(ROOT / 'seal/cases.json')['cases']:
        expected = case['expected']
        assert expected['start_allowed'] == (case['threshold_raw'] is not None)
        if case['threshold_raw'] is None:
            assert expected['certify'] is False
            continue
        threshold = ThresholdFile.from_dict(json.loads(case['threshold_raw']))
        dev = [FinalRecord.from_dict(json.loads(line)) for line in case['dev_final_raw'].splitlines() if line]
        rows = []
        for record in dev:
            answers = {k:v for call in record.calls for k,v in (call.answers_parsed or {}).items()}
            rows.append(dict(valid=record.status=='ok', mask_empty=not case['gold'],
                             s=min(a.confidence for a in answers.values()),
                             wrong=any(answers[q].answer != gold for q,gold in case['gold'].items())))
        recomputed = {t:threshold_reference(rows,t) for t in threshold.by_tau}
        seal = case['seal']
        checks = dict(a=sha(case['dev_final_raw']) == threshold.dev_input['sha256'] == seal['dev_final_sha256'],
                      b=recomputed == {k:v.to_dict() for k,v in threshold.by_tau.items()},
                      c=sha(case['threshold_raw']) == seal['threshold_sha256'] == case['risk_threshold_sha256'])
        assert checks == expected['checks']
        assert all(checks.values()) == expected['certify']
        assert (case['threshold_mtime'] > case['test_start_mtime']) == expected['mtime_warning']


def test_resume_threshold_replacement_rejected():
    fixture = read(ROOT / 'resume/threshold_replaced.json')
    assert sha(fixture['sealed_threshold_raw']) == fixture['seal']['threshold_sha256']
    allowed = sha(fixture['current_threshold_raw']) == fixture['seal']['threshold_sha256']
    assert allowed == fixture['expected']['resume_allowed']
