# 저장 결과의 paired 이미지 bootstrap

검증된 두 모델의 반복 평균을 같은 문항·이미지에서 비교한다.
기존 발행·보고 지표는 바꾸지 않으며 파일을 쓰지 않는다. 입력은 저장 세션,
publication sidecar, 묶음 1의 고정 manifest뿐이다. HF 캐시·네트워크가 필요 없다.

| 파일 | 입력 → 출력 |
|---|---|
| `item_scores.py` | 저장 행·manifest → 문항/이미지 점수; 반복 점수 → 문항별 평균(순수) |
| `paired.py` | 두 모델의 반복 평균 → 이미지 단위 paired bootstrap 95% 구간(순수) |
| `selection.py` | 결과 루트·모델 폴더 → 검증된 코호트·반복·SHA 근거 |
| `__main__.py` | CLI 조립; 비교 객체 → Markdown/JSON 문자열 |

## 실행

N 루트에서 실행한다. `--base`는 결과 루트만 바꾸며 코드는 현재 패키지를 쓴다.
`--a`, `--b`는 `base/results` 바로 아래 모델 폴더명, base 상대 경로,
또는 절대 경로다. 세션 하나를 모델 폴더인 것처럼 지정할 수 없다.

```bash
.venv/bin/python -B -m shared.stats \
  --a qwen_qwen3.8_27b --b qwen_qwen3.8_27B_FP8 \
  --bench k_mmbench --seed 0 --resamples 2000
.venv/bin/python -B -m shared.stats \
  --a qwen_qwen3.8_27b --b qwen_qwen3.8_27B_FP8 \
  --bench mtvqa_kr --format json
```

기본 seed=0, resamples=2000, format=markdown이다. stdout만 사용하고 `--out`은
제공하지 않는다. 저장이 필요하면 운영 results/data/logs 밖으로 리디렉션한다.
JSON 점수·차이·구간은 [−1,1] 범위의 비율이며 Markdown 점수는 %, 차이·구간은
퍼센트포인트(pp)다. 차이는 항상 **A−B**이다. JSON에는 선택된 원본 경로,
results/summary SHA256, 읽은 sidecar SHA256, manifest SHA256·revision,
접힌 사본 목록, upstream 경로·commit, 지표 버전·재표집 인자를 남긴다.

rc 0은 입력 검증과 비교 완료다. rc 2는 선택 모호함, 손상된 입력/sidecar,
비발행 코호트, 문항·반복 수·코호트 불일치다. 오류는 stderr JSON에 안전한
식별자 후보와 함께 출력하며 응답·키·프로토콜 원문은 출력하지 않는다.
다중 코호트라면 `--cohort 'sha256:전체지문'`으로 양쪽에 적용할 코호트를
명시할 수 있다. 이 옵션도 불일치 조건을 완화하지 않는다.

## 지표와 클러스터

| `--bench` | 지표 v1 | 통계 문항 | 이미지 클러스터 | 전체 문항 / 이미지 |
|---|---|---|---|---:|
| `k_dtcbench` | `kdtc_stored_judgement` | 문자열 index | manifest 이미지 SHA 앞 16자리 | 240 / 120 |
| `k_mmbench` | `kmmbench_circular_stored_judgement` | manifest circular 묶음 | manifest 이미지 SHA 앞 16자리 | 1,164 / 1,121 |
| `mtvqa_kr` | `mtvqa_lmms_eval` | `(id, qa_idx)` | manifest 이미지 SHA 앞 16자리(고정 split의 250개 이미지 id에 대응) | 558 / 250 |

K-DTC는 `correct`가 bool이어야 하며 True이고 error가 없을 때만 1이다.
행 정답이나 기존 MTVQA 등 대체 지표 선택은 제공하지 않는다. 세 벤치 모두
고정 revision의 전체 문항 집합·질문/정답 지문이 일치해야 한다.
`--limit`/부분집합은 두 모델끼리 같더라도 현재 전체 manifest 계약에서 거부한다.

K-MMBench와 MTVQA는 각각
`shared.multimodal.rescore.kmmbench_circular.score`,
`shared.multimodal.rescore.mtvqa_lmms.score`의 문항 결과를 그대로 쓴다.
요약 accuracy를 역산하지 않는다. 세부 판정·로컬 예외·manifest 근거는
[rescore README](../multimodal/rescore/README.md)를 따른다.
고정 upstream은 VLMEvalKit
`1445ec4f6fd02b25bad0d713690ee01a24b3b689`의
`vlmeval/dataset/utils/multiple_choice.py`, lmms-eval
`d8fcb9c345fd89b22b4857244b3fdbb89206f8f5`의
`lmms_eval/tasks/mtvqa/utils.py`다.

## 코호트와 반복

모델 폴더의 대상 벤치 원본을 모두 탐색한다(미추적 파일도 포함).
원본이 있는데 sidecar가 없거나 손상됐다면 조용히 제외하지 않고 거부한다.
`validate_sidecar`와 `validate_artifact_integrity`를 통과한 sidecar에 현재 모델
정체성 매핑을 적용하고 `select_representatives`를 호출한다. publishable만
선택되며 `.bad` **동일 사본**은 기존 규칙대로 접힌다. 대표 하나를 채점하는 것이
아니라 `_selection.cohort_runs`의 모든 반복을 사용한다. r1/r2/r3 이름,
점수, 최신 실행만으로 반복을 자르지 않는다. 시각이 없는 실행도 선택기가
`cohort_runs`에 남겼다면 포함한다.

양쪽 `cohort_key(...)[:3]`(벤치·variant·프로토콜 fingerprint), 지표/버전/출처,
문항 집합·이미지 매핑, 반복 수가 모두 같아야 한다. 반복 내부에서도 같은
지표·문항·이미지 매핑이어야 한다. 공통 문항만 추리는 비교는 없다.
같은 모델 비교도 허용하며 차이와 구간은 정확히 0이다.

예를 들어 현재 Gemma 4 26B와 DiffusionGemma는 temperature·서빙 제약 때문에
서로 다른 코호트다. Gemma 폴더에는 r1~r3 외 과거 실행도 있어 반복 수를
3으로 가정하면 안 된다. 이 비교를 강제하는 옵션은 제공하지 않는다.

## 통계 해석

먼저 문항마다 관측 반복들의 산술 평균을 낸다. 이미지 G개에서 G개를 복원
추출하며 같은 추출을 두 모델에 적용한다. 선택된 이미지의 모든 문항을
중복 횟수만큼 포함하여 **문항 가중** A−B 평균을 계산한다. 이미지별 평균을
동일 가중하는 방식이 아니다. 서로 다른 반복의 r 번호를 짝짓거나 반복 자체를
재표집하지 않는다. 문항·이미지 정렬과 지역 `random.Random(seed)`로 입력 순서와
전역 RNG 상태에 의존하지 않는다.

구간은 재표집 차이의 2.5%, 97.5% 선형 보간 분위수(`(n−1)p` 위치)다.
**관측한 반복 평균에 조건부인 문항 표집 불확실성**이며 반복 간 변동을
포함하지 않는다. 모델 훈련·서빙 변동, 다중 비교 보정, 모집단 일반화까지
보장하지 않는다. 이미지가 하나이거나 차이가 일정하면 구간이 퇴화할 수 있다.
양의 resamples는 허용하지만 작은 횟수의 분위수는 거칠다.

## 검증

```bash
PYTHONDONTWRITEBYTECODE=1 bash tests/run_pytests.sh stats -q
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m pytest -q \
  -p no:cacheprovider shared/stats/tests
bash tests/run_pytests.sh --list
```

`pytest.ini`의 `testpaths=shared ...`와 선택기의 `shared/<track>` 재귀 탐색이
`shared/stats/tests/test_stats_*_units.py`를 자동 발견한다. 등록 파일 수정은 없다.
C3은 합성 데이터·tmp_path만 쓴다. C4는 별도 scratch 스크립트로 실제 추적
입력임을 확인하고 CLI 전후 results 전체 파일 목록·SHA256을 비교한다.

## 보고서에서 재사용

`report_pairs.py`는 이미 채점된 코호트를 받아 CLI와 같은 `comparison()`으로
계산하고 표를 만든다. 파일·YAML을 읽지 않으며 표준 라이브러리 계약을 유지한다.
`SelectionError`만 비교 불가로 표시하고 구현 예외는 호출자에게 전파한다.
보고서의 기본 seed=0·resamples=2000은 CLI 기본값과 같다.

`selection.read_collected_run()`은 이미 수집된 sidecar를 디스크 기록과 대조한 뒤
기존 `read_run()`을 호출한다. 보고서의 전역 별칭·반복 선택을 폴더별로 다시
수집하지 않기 위한 공개 함수 추가이며 기존 CLI의 선택 동작은 바꾸지 않는다.
paired 정책·서빙 선언·`--no-official` 사용법은
[reports README](../../reports/README.md)에 있다.
