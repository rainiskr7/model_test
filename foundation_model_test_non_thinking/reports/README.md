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
