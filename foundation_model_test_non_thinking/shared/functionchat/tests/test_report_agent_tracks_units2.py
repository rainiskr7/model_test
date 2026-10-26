"""R4 contracts captured by executing original blocks on synthetic inputs."""
import reports.report_agent_tracks as subject


def test_exact_claims_empty():
    actual = subject._exact_claims({}, lambda runs: {}, lambda a, b: {})
    assert actual == ({}, [])


def test_exact_claims_mixed_keys():
    grouped = {('v', None, 'b'): [{'session': 's', 'items': {}}], ('v', ('x',), 'a'): [{'session': 'r', 'items': {}}]}
    creds, verdicts = subject._exact_claims(grouped, lambda runs: {'claim_class': 'repeatability_observed', 'runs': runs}, lambda a, b: {'comparable': False})
    actual = (list(creds.items()), verdicts)
    assert actual == ([(('v', ('x',), 'a'),
       {'claim_class': 'repeatability_observed', 'runs': [{'run_id': 'r', 'items': {}}]}),
      (('v', None, 'b'),
       {'claim_class': 'repeatability_observed', 'runs': [{'run_id': 's', 'items': {}}]})],
     [('a', 'b', {'comparable': False})])


def test_judge_verdicts_empty():
    actual = subject._judge_verdicts([], lambda a, b: {})
    assert actual == []


def test_judge_verdicts_skip_same_model(tmp_path, capsys):
    entries = [{'model': model, 'credential': {'n': i}} for i, model in enumerate(['b', 'b', 'a'])]
    actual = subject._judge_verdicts(entries, lambda a, b: [a['n'], b['n']])
    assert actual == [('b', 'a', [0, 2]), ('b', 'a', [1, 2])]
    import json
    for model, verdict in (("a", "pass"), ("b", "fail")):
        directory = tmp_path / "results" / model / "session/language/functionchat"
        directory.mkdir(parents=True)
        (directory / "judge.json").write_text(json.dumps({
            "judge": {"model": "alias", "human_validation": "not performed"},
            "records": [{"status": "judged", "verdict": verdict, "unstable": False}],
        }))
    baseline = subject.collect_claims(tmp_path)
    assert all(entry["judge_profile"] == ("alias", None, None, 700)
               for entry in baseline["judge_credentials"])
    rendered = subject._render_claim_verdicts(baseline)
    path = directory / "judge.json"
    saved = json.loads(path.read_text())
    request = {"model": "alias", "provider": None, "reasoning_effort": None,
               "max_tokens_requested": 700, "max_tokens_effective": 700, "temperature": 0}
    for field, value in (("model", "other"), ("provider", "deepinfra/bf16"),
                         ("reasoning_effort", "medium"), ("max_tokens_effective", 2000)):
        path.write_text(json.dumps({**saved, "judge_request": {**request, field: value}}))
        claims = subject.collect_claims(tmp_path)
        assert claims["judge_verdicts"] == [("a", "b", {
            "comparable": False, "reason": "판정기 프로파일 불일치 — 비교 불가"})]
        assert "판정기 프로파일 불일치 — 비교 불가" in "\n".join(subject._render_claim_verdicts(claims))
    path.write_text(json.dumps({**saved, "judge_request": request}))
    assert subject._render_claim_verdicts(subject.collect_claims(tmp_path)) == rendered

    import pytest
    for model in ("a", "b"):
        directory = tmp_path / "results" / model / "session/language/functionchat"
        (directory / "summary.json").write_text(json.dumps({
            "model": model, "scoring_version": "test", "overall": {"passed": 1, "measured": 2},
            "publish_status": {"publishable": True, "failures": []},
        }))
        default = json.loads((directory / "judge.json").read_text())
        default["overall"] = {"passed": 1, "judged": 2}
        (directory / "judge.json").write_text(json.dumps(default))
        (directory / "judge.oss.json").write_text(json.dumps({
            **default, "overall": {"passed": 2, "judged": 2},
            "judge_request": {**request, "model": "cohort-judge"},
        }))
    original = {p: p.read_bytes() for p in tmp_path.rglob("*.json")}
    defaults = subject.collect(tmp_path)
    selected = subject.collect(tmp_path, "oss")
    assert all(row["axes"][-1][1:3] == (1, 2) for row in defaults)
    assert all(row["axes"][-1][1:3] == (2, 2) for row in selected)
    assert all(len(row["axes"]) == 1 for row in subject.collect(tmp_path, "absent"))
    assert not subject.collect_claims(tmp_path, "absent")["judge_credentials"]
    assert "judge_cohort" not in subject.collect_claims(tmp_path)
    claims = subject.collect_claims(tmp_path, "oss")
    assert claims["judge_cohort"] == "oss"
    assert all(entry["judge_profile"][0] == "cohort-judge" for entry in claims["judge_credentials"])
    assert all(entry["judge_profile"][0] == "alias" for entry in subject.collect_claims(tmp_path)["judge_credentials"])
    heading = "판정 코호트: oss (judge.oss.json)"
    markdown_path = tmp_path / "report.md"
    assert subject.main(["--base", str(tmp_path), "--judge-cohort", "oss",
                         "--write-markdown", str(markdown_path)]) == 0
    assert capsys.readouterr().out.count(heading) == 1
    assert markdown_path.read_text().count(heading) == 1
    assert "판정 코호트:" not in subject.render_markdown(defaults, claims=subject.collect_claims(tmp_path))
    for value in ("Oss", "a b", ".", "a/b", "a" * 33, "a\n"):
        with pytest.raises(SystemExit) as rejected:
            subject.main(["--base", str(tmp_path), "--judge-cohort", value])
        assert rejected.value.code == 2
    capsys.readouterr()
    assert original == {p: p.read_bytes() for p in tmp_path.rglob("*.json")}
    cohort_path = directory / "judge.oss.json"
    cohort = json.loads(cohort_path.read_text())
    cohort["judge_request"]["provider"] = "different-provider"
    cohort_path.write_text(json.dumps(cohort))
    assert subject.collect_claims(tmp_path, "oss")["judge_verdicts"] == [("a", "b", {
        "comparable": False, "reason": "판정기 프로파일 불일치 — 비교 불가"})]
    assert subject.collect(tmp_path) == defaults
    cohort_path.unlink()
    assert len(subject.collect_claims(tmp_path, "oss")["judge_credentials"]) == 1
    assert [len(row["axes"]) for row in subject.collect(tmp_path, "oss")] == [2, 1]


def test_render_exact_empty():
    actual = subject._render_exact_credentials({})
    assert actual == ['### exact-match 축', '', '']


def test_render_exact_classes():
    actual = subject._render_exact_credentials({
        ('v', None, 'snap'): {'claim_class': 'snapshot', 'k': 1, 'reason': 'one'},
        ('v', None, 'repeat'): {'claim_class': 'repeatability_observed', 'k': 3, 'instability_envelope': [1, 3], 'majority_passed': 2, 'measured_items': 4, 'count_range': [1, 2], 'unstable_items': ['x']},
    })
    assert actual == ['### exact-match 축',
     '',
     '- `snap` (`v`) — `snapshot` (k=1) · one',
     '- `repeat` (`v`) — `repeatability_observed` (k=3) · 다수결 2/4 · 건수범위 [1, 2] · 뒤집힘 1건 · 불안정 예산 1–3',
     '']


def test_render_judge_empty():
    actual = subject._render_judge_credentials([])
    assert actual == []


def test_render_judge_provisional():
    actual = subject._render_judge_credentials([{'model': 'm', 'run': 'r', 'provisional': True, 'credential': {'claim_class': 'judge', 'k': 3, 'instability_envelope': [0, 2], 'majority_passed': 1, 'measured_items': 2, 'unstable_items': ['x']}}])
    assert actual == ['### judge 축 — 런 내부 3표',
     '',
     '판정 축은 exact-match 축과 합치지 않는다. 이 예산은 반복 실행 간 뒤집힘이 아니라, 같은 런에서 항목별 3표가 갈린 수로 만든 판정기 내부 불안정이다.',
     '',
     '- `m` / `r` — `judge` (런 내부 3표, k=3) · 다수결 1/2 · 표 갈림 1건 · 불안정 예산 0–2 · **PROVISIONAL — 판정기 기준, '
     '인간 검증 없음**',
     '']


def test_render_verdicts_empty():
    actual = subject._render_claim_verdicts({'verdicts': []})
    assert actual == ['### 발행 가능한 우열 주장', '', '**exact-match 축**', '', '- 반복 관측된 코호트가 2개 미만이라 비교할 대상이 없다.', '']


def test_render_verdicts_conflicting_axes():
    actual = subject._render_claim_verdicts({'verdicts': [('z', 'a', {'comparable': True, 'winner': 'left', 'reason': 'exact'})], 'judge_verdicts': [('z', 'a', {'comparable': True, 'winner': 'right', 'reason': 'judge'}), ('a', 'b', {'comparable': False, 'reason': 'blocked'})]})
    assert actual == ['### 발행 가능한 우열 주장',
     '',
     '**exact-match 축**',
     '',
     '- `z` 우세 — exact',
     '',
     '**judge 축** (판정기 기준, 인간 검증 없음)',
     '',
     '- `a` 우세 — judge',
     '- `a` vs `b` — **발행 불가**: blocked',
     '',
     '> **두 축의 승자가 다르다** — exact: `z` / judge: `a`. 한 축만 인용하면 그 자체가 과대 주장이다. 두 축은 다른 채점기로 다른 것을 재며, 어느 '
     "쪽이 '진짜'인지 이 데이터는 말하지 않는다.",
     '']
