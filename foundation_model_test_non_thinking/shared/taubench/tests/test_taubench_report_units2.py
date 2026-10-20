"""R4 contracts captured by executing original blocks on synthetic inputs."""
import shared.taubench.scoring.report as subject


def test_cohort_verdicts_empty():
    actual = subject._cohort_verdicts([])
    assert actual == []


def test_cohort_verdicts_model_and_protocol():
    entries = [{'fingerprint': 'f', 'model': model, 'removed_sampling_controls': controls, 'protocol': {'comparable_across_candidates': False, 'reason': 'unpinned'}} for model, controls in [('a', ''), ('a', 'seed'), ('b', '')]]
    actual = subject._cohort_verdicts(entries)
    assert actual == [{'left': 'a',
      'right': 'a',
      'left_removed_sampling_controls': '',
      'right_removed_sampling_controls': 'seed',
      'verdict': {'comparable': False,
                  'reason': "같은 모델의 두 서빙 조건이다 — 모델 간 우열이 아니다 (제거된 제어: '' vs 'seed')"}},
     {'left': 'a',
      'right': 'b',
      'left_removed_sampling_controls': '',
      'right_removed_sampling_controls': '',
      'verdict': {'comparable': False, 'reason': 'unpinned'}},
     {'left': 'a',
      'right': 'b',
      'left_removed_sampling_controls': 'seed',
      'right_removed_sampling_controls': '',
      'verdict': {'comparable': False, 'reason': 'unpinned'}}]


def test_render_cohorts_empty():
    actual = subject._render_comparison_cohorts([])
    assert actual == ['## 비교 코호트', '']


def test_render_cohorts_single():
    actual = subject._render_comparison_cohorts([{'model': 'm', 'split': {'domain': 'retail', 'name': 'test'}, 'harness_integrity': {'mode': 'solo'}}])
    assert actual == ['## 비교 코호트',
     '',
     '### retail/test — protocol `872d4b56646895d4`',
     '',
     '사용자 시뮬레이터: `None` · mode `solo` · tau2 `None`',
     '',
     '> **모델 간 비교 불가 (UNCOMPARABLE).** 아래는 개별 런의 관측값이며 서로 나란히 읽으면 안 된다.',
     '',
     '| 모델 | 축 | Pass^1 | 비교 제외 사유 |',
     '|---|---|---:|---|',
     '| m | retail/test | - | — |',
     '']


def test_render_repro_empty():
    actual = subject._render_reproducibility([])
    assert actual == ['## 재현성', '', '비교할 런이 없습니다.', '', '']


def test_render_repro_single():
    actual = subject._render_reproducibility([{'model': 'm', '_session': 's', 'split': {'domain': 'retail', 'name': 'test'}, 'harness_integrity': {'mode': 'solo'}}])
    assert actual == ['## 재현성',
     '',
     '- `m` · protocol `872d4b56646895d4` — **UNVERIFIED**',
     '  - 런 1개: `s`',
     '  - 이 규약으로 이 모델을 한 번만 돌렸다 — 비교 대상이 없다',
     '']
