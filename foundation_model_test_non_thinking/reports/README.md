# 트랙 보고 스크립트

- `report_harness_tracks.py`: KMMLU 채점·발행 보고서.
- `report_agent_tracks.py`: functionchat의 발행 가능한 exact·judge 결과.
- `report_nlu_tracks.py`: NLU 항목 벡터 보고서(stdout).
- `report_taubench_tracks.py`: taubench 발행 결과와 거부 사유.
- `report_multimodal_tracks.py`: multimodal sidecar 기반 발행 보고서.

모든 보고서는 `python3 -m reports.report_<track>_tracks`로 실행한다.
어디서 실행해도 `<N>` 기준(`--base` 기본값)으로 산출물을 읽는다.
`<N>`은 `foundation_model_test_non_thinking`, `<R>`은 그 상위 디렉터리다.
`report_agent_levels.{py,sh}`는 두 저장소 공용이라 `<R>`에 있다.
`--write-markdown`의 상대 경로는 호출 cwd 기준이며, NLU는 stdout만 지원한다.
모든 보고서(harness 포함)의 `--base`는 산출물 위치만 지정하며, 채점 코드는 실행 중인 저장소의 패키지를 쓴다. 저장소 밖 cwd에서는 `PYTHONPATH`에 N 루트를 지정한다.

세 cwd 실행 예(먼저 실제 `<N>` 절대 경로를 지정):

```bash
N=/absolute/path/to/foundation_model_test_non_thinking
R="$(dirname "$N")"

(cd "$N" && python3 -m reports.report_harness_tracks)
(cd / && PYTHONPATH="$N${PYTHONPATH:+:$PYTHONPATH}" python3 -m reports.report_agent_tracks --write-markdown /tmp/agent-from-root.md)
(cd "$R" && PYTHONPATH="$N${PYTHONPATH:+:$PYTHONPATH}" "$N/.venv/bin/python" -m reports.report_multimodal_tracks --write-markdown /tmp/multimodal-from-parent.md)
(cd "$N" && env -u PYTHONPATH python3 -m reports.report_taubench_tracks --write-markdown /tmp/taubench-from-n.md)
(cd "$N" && env -u PYTHONPATH "$N/.venv/bin/python" -m reports.report_nlu_tracks)
(cd / && PYTHONPATH="$N${PYTHONPATH:+:$PYTHONPATH}" "$N/.venv/bin/python" -m reports.report_nlu_tracks)
```

## Multimodal 참고 부록

기본 보고서는 기존 발행 보고서 byte를 그대로 접두로 두고 세 절을 덧붙인다:
공식 방식 재채점, 모델 간 paired 비교, multimodal 평가 조건.
발행 게이트·기존 지표·strict 판정은 바꾸지 않는다.

```bash
python -B -m reports.report_multimodal_tracks --base . \
  --write-markdown MULTIMODAL_TRACK_RESULTS.md
python -B -m reports.report_multimodal_tracks --base . --no-official
python -B -m reports.report_multimodal_tracks --base . --run SESSION
```

`--no-official`은 YAML 읽기와 재채점을 모두 생략하며 이전 보고서와 byte가 같다.
`--run`은 수집된 해당 세션만 사용한다. `--strict --run`은 기존 보고서와 같이
그 세션의 코호트에 속한 전체 반복을 비교 입력으로 사용한다. 부록에서 결과
트리를 다시 탐색하지 않는다. 다른 범위의 쌍은 “비교 불가”로 표시한다.

`reports/paired_pairs.yaml`은 실행 중인 **코드 루트**의 비교 정책이다.
각 행은 `{a: 모델폴더, b: 모델폴더, bench: 벤치}`이며 벤치는
`k_mmbench`, `mtvqa_kr`, `k_dtcbench`만 허용한다. 폴더는 실제 철자의 단일 이름이다.
같은 모델 쌍의 같은 벤치는 역방향까지 중복으로 거부한다.
기본 12조합 중 현재 Qwen3.6 27B FP8의 K-DTC는 비발행이라 숫자를 내지 않는다.
seed=0, resamples=2000이며 차이는 A−B, 표의 차이·구간 단위는 pp다.

`--base/configs/serving_conditions.yaml`은 **결과 루트**의 서빙 선언이다.
파일 부재 또는 `[]`는 전부 “미기록”이다. 현재 기본 파일은 `[]`다.
선언은 다음 필드를 모두 요구하며 정확한 세션명만 지원한다(기간 추정 없음).

```yaml
- model: canonical_model_id
  sessions: [20261020_r1]
  generation_config: vllm
  evidence: "해당 세션 배포 기록의 위치 또는 식별자"
```

`model`은 sidecar에 적용된 canonical id, `generation_config`는 `vllm` 또는
`auto`다. 모델·세션 중복 선언은 거부한다. 선언은 실측으로 취급하지 않으며
다른 세션이나 별도 `--base`에 전파하지 않는다. judge는 선택 코호트의
`protocol.recorded.judge_model`을 표시하고 tau 조건은 다루지 않는다.

YAML 형식·구조 오류는 rc 2이며 출력 파일을 쓰기 전에 실패한다.
재채점 검증 거부는 제외 사유를, paired `SelectionError`는 비교 불가 사유를 표시한다.
그 밖 구현 오류는 보고서 실패(rc 2)이며 비교 불가로 숨기지 않는다.
응답·키·YAML 원문은 오류 메시지에 싣지 않는다.
`--write-markdown` 출력은 운영 results/data/logs 밖에 지정한다.

검증: C6은 `610e8b1` 임시 코드의 stdout과 `--no-official`을 byte 비교하고
기본 출력의 접두·부록을 검사한다. 기준선 전체 SHA 비교는 의도된 multimodal
1개 DIFF(rc 1), 나머지 215개 동일이어야 한다. C8은 모든 공식 지표 반복 평균과
paired 11개 성공·1개 거부, 대표·반복 출처를 독립 CLI 결과와 대조한다.
