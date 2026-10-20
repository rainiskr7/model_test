# 저장 응답 재채점

기존 results·summary·publication sidecar를 읽기만 하는 별도 분석이다.
발행 판정이나 기존 보고서 점수를 바꾸지 않는다. paired 통계는 이 패키지에 없다.

| 파일 | 입력 → 출력 |
|---|---|
| `manifest.py` | 오프라인 HF Arrow 캐시 → 고정 문항·이미지 manifest; manifest/저장 행 검증 |
| `kmmbench_circular.py` | 저장 판정·manifest → 순환 묶음별 점수와 요약(순수 함수) |
| `mtvqa_lmms.py` | 저장 응답·singleton gold·manifest → 문항별 점수와 요약(순수 함수) |
| `sessions.py` | 원본 파일 읽기·SHA 기록, 결과 트리 탐색, 보호 경로 밖 원자적 JSON 쓰기 |
| `__main__.py` | CLI 인자 → 위 함수 조립, stdout과 종료 코드 |

## 실행

N 루트에서 실행한다. 기본 출력은 키가 정렬된 JSON이며 파일을 만들지 않는다.
`--base`는 결과 루트이며 코드·manifest는 실행 중인 패키지에서 읽는다.
`--source`는 cwd 기준 벤치 디렉터리이고 여러 번 지정할 수 있다.
`--bench`를 함께 쓰면 명시한 source도 같은 벤치여야 한다.

```bash
.venv/bin/python -B -m shared.multimodal.rescore --base .
.venv/bin/python -B -m shared.multimodal.rescore --bench k_mmbench
.venv/bin/python -B -m shared.multimodal.rescore \
  --source results/MODEL/SESSION/vision/multimodal/mtvqa_kr \
  --out /tmp/official-rescore.json
```

`--out`은 stdout과 같은 JSON을 원자적으로 쓴다. results/data/logs 내부,
그곳으로 향하는 심볼릭 링크, 입력 벤치 내부는 쓰기 전에 거부한다.
운영 `results` 전체 탐색은 미추적 세션도 포함한다. 추적 세션만 검증하려면
`git ls-files`로 얻은 source를 각각 지정한다. 복사 세션은 여기서 합치지 않는다.

rc 0은 모든 세션의 입력 검증·재채점 완료를 뜻하며 점수 0도 성공이다.
rc 2는 입력/manifest 손상, 지원하지 않는 revision, 문항 불일치,
multi-gold 또는 금지된 출력 경로를 뜻한다. 다른 정상 세션 결과도 함께 출력한다.
거부 세션의 최종 accuracy는 null이며 `issues`에 사유를 기록한다.
API 오류의 원문·응답 원문은 출력하지 않는다.
세션마다 results/summary 파일 SHA256, manifest 파일 SHA256, revision,
지표명·버전·방법 출처를 출력한다.

## 판정 계약

`kmmbench_circular_stored_judgement` v1:

- manifest의 전체 index 집합과 정확히 일치해야 한다. 기본/중간 사본 누락,
  중복·추가 index, 질문/정답 지문 불일치는 세션 거부다.
- `correct`는 실제 bool이어야 한다. None·문자열·정수는 거부한다.
- 묶음의 예상 사본이 전부 있고 모두 `correct is True`이며 error가 없으면 1이다.
- 저장된 답 추출 판정을 다시 계산하지 않는다. 행 정답률과 묶음 정답률의
  가중치가 다르므로 두 점수 사이 일반적인 대소 관계를 주장하지 않는다.
- 그룹별 점수·예상/관측 사본 수·row_mean·이미지 cluster를 함께 출력한다.
  입력이 거부된 경우 그룹 자료는 진단용이며 최종 점수로 쓰면 안 된다.

`mtvqa_lmms_eval` v1:

- gold는 문자열 하나를 담은 list만 허용하고 `gold[0]`을 쓴다.
- 응답과 답에 `strip().lower().replace(".", "")`를 적용한 뒤
  답이 응답에 포함되면 정답이다. NFKC, 공백 압축, thinking 태그 제거는 없다.
- 정규화 후 빈 gold와 error 행은 실패로 세고 각각 건수를 기록한다.
  오류 dict를 문자열로 바꿔 매칭하지 않는다. error 없는 비문자열 응답은 거부한다.
- manifest의 `(id, qa_idx)`, 한국어 필터 후 `row_idx`, 질문/정답 지문을 검증한다.
  모든 예상 QA가 한 번씩 있어야 한다. 점수는 이미지 평균이 아닌 QA 평균이다.
- `stored_correct/accuracy`는 비교용 기존 저장 판정이며 새 채점에는 쓰지 않는다.

## upstream 근거와 한계

판정 근거는 `orchestration/SPEC_official_rescore_paired_stats_20261020.md`
판 2(2026-10-20)에 기록된 아래 upstream 정의/함수다.

- MMBench CircularEval 정의: <https://github.com/open-compass/MMBench#evaluation>
- VLMEvalKit `vlmeval/dataset/utils/multiple_choice.py`의 `mcq_circular_eval`:
  <https://github.com/open-compass/VLMEvalKit/blob/main/vlmeval/dataset/utils/multiple_choice.py>
- lmms-eval `lmms_eval/tasks/mtvqa/utils.py`의 `mtvqa_process_results`:
  <https://github.com/EvolvingLMMs-Lab/lmms-eval/blob/main/lmms_eval/tasks/mtvqa/utils.py>

**upstream commit**(2026-10-20 GitHub API 로 각 경로를 마지막으로 바꾼 커밋 확인):
lmms-eval `d8fcb9c345fd89b22b4857244b3fdbb89206f8f5`(98–102행 판정식이 `mtvqa_lmms.lmms_match` 와 같음),
VLMEvalKit `1445ec4f6fd02b25bad0d713690ee01a24b3b689`. 출력 `upstream.commit` 에 같은 값을 남긴다.
upstream 은 정규화 후 빈 gold 를 `"" in pred` 로 정답 처리하지만 여기서는 실패로 센다(아래 예외).

VLMEvalKit의 관측 행만 평가하는 동작과 달리, 이 분석은 manifest 사본 누락을
거부한다. 저장 답 추출기도 그대로이므로 공식 평가 전체의 재현 점수는 아니다.
MTVQA의 빈 gold·오류 처리도 명시적인 로컬 예외다.

## manifest 생성과 근거

캐시만 직접 읽는다. `datasets.load_dataset`이나 다운로드를 호출하지 않으며
`pyarrow`는 `--build`에서만 지연 import한다. 둘 중 하나라도 오프라인 환경
변수가 1이 아니면 거부한다. 캐시가 없으면 중단하고 rc 2를 반환한다.
기본 캐시는 `HF_DATASETS_CACHE`, 또는 `HF_HOME/datasets`를 따른다.
`--cache-dir`로 캐시 루트를 지정할 수 있다.

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 .venv/bin/python -B \
  -m shared.multimodal.rescore.manifest --build k_mmbench
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 .venv/bin/python -B \
  -m shared.multimodal.rescore.manifest --build mtvqa_kr
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 .venv/bin/python -B \
  -m shared.multimodal.rescore.manifest --build k_dtcbench
```

빌더는 git 추적 세션의 저장 revision을 먼저 확인한다. 생성 JSON에는 revision,
원본 Arrow 파일명·SHA256, 확인한 추적 summary 수, 문항의 질문/정답 지문,
전체 예상 키·그룹 구성, 이미지 SHA256과 앞 16자리 cluster ID를 기록한다.
이미지 prefix 충돌은 거부한다. 타임스탬프·절대 캐시 경로는 저장하지 않는다.
이미지 ID는 캐시의 **인코딩된 이미지 bytes** 기준이며 픽셀 동등성 검사는 아니다.

| 벤치 | 고정 revision | 문항/이미지 |
|---|---|---|
| K-MMBench | `03d682e76405292ac5194b6289feb85ef5c4d98b` | 4,329행 / 1,164순환 문항 / 1,121이미지 |
| MTVQA Korean test | `7cdca63ec6cd71cdd0b52f79fc3176bb9ce36a9c` | 558 QA / 250이미지 |
| K-DTCBench | `62128c281b7fcbd5af77593a6b65aa385554cb71` | 240문항 / 120이미지 |

K-MMBench 예상 사본 수: 2×89, 3×149, 4×926.
`four_options_three_variants=59`는 **기본 index 행에 선택지 4개**인 3사본 묶음이다.
그중 366·374·385는 나머지 두 사본에 선택지가 3개여서 `mixed_option_groups=3`이다.
이 배포 특성을 누락으로 판정하지 않고 고정 manifest의 사본 목록을 따른다.
K-DTC manifest는 후속 통계의 이미지 묶음용이며 이 CLI의 채점 대상은 아니다.

## 검증

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m pytest -q \
  -p no:cacheprovider shared/multimodal/tests/test_rescore_*_units.py
```

단위 시험은 합성 행과 tmp_path만 사용한다. 네트워크·실제 HF 캐시·운영 결과가
필요하지 않다. 실제 추적 세션 C2는 별도 scratch 스크립트에서 전체 results 파일
목록·SHA256을 실행 전후 대조하고 그룹별 score ≤ row_mean을 검사한다.
