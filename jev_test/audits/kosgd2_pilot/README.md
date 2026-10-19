# kosgd2 W1 1회 파일럿 도구

실데이터 선정과 모델 호출은 이번 구현에서 실행하지 않는다. 질문은 kosgd2_full 13개,
모델은 pplx_v1_1과 b1_qwen3_8_27b(BF16)이며 두 모델의 200 논리 ID가 같아야 한다.
정답·정확도·직전 정답 기준선을 만들지 않는다. 원 JSON의 라벨은 reader의 prefix에 투영하지 않는다.

- `select_pilot.py`: 옛 풀 유일 3,000 ID 정렬 → 동일 RNG sample200 → 결과 정렬 → USER index choice.
  T0/새 풀 교집합이면 거부하며 다시 뽑지 않는다. Python 버전·입력 SHA·선정 SHA를 기록한다.
- `prepare.py`: `read_prefixes`/라벨 없는 Request 입구로 계획만 만들며 선택/task/model/b1/lists/요청
  해시 manifest만 쓴다. 요청 원문을 공개 파일에 쓰지 않고 서버 전송 기능을 제공하지 않는다.
- `gate.py`: 원응답을 기존 systemone/B1 검증기로 판정하고 B1 13 호출을 논리 요청 하나로 합친다.
  누락은 INCOMPLETE, 중복/여분 ID나 요청 해시 불일치는 거부한다. 부분 HTTP 실패는 전체 무효다.
  유효 응답에서 두 칸이 같은 비NONE이면 중복. 모델별 중복≤10/200 그리고 무효≤10/200일 때 PASS.
- 짝 시험: `tests/audits/test_pilot_select_pilot.py`, `test_pilot_prepare_gate.py`.

저장소 루트에서 Claude가 실행할 선정 명령(기존 출력 거부):

```sh
python -B -I audits/audit_v4/offline_check.py -- audits/kosgd2_pilot/select_pilot.py --source dataset/kosgd --old audits/kosgd_audit/audit_result.json --fixture configs/t0/fixture_v1.json --new audits/kosgd2_selection/selection.json --out audits/kosgd2_pilot/pilot_selection.json
```

아래는 후속 파일럿 준비/응답 단계 명령이며 C7의 이번 출력 허용 범위 밖이다. 전송은 별도 레인이다.

```sh
python -B -I audits/kosgd2_pilot/prepare.py --root . --source dataset/kosgd --selection audits/kosgd2_pilot/pilot_selection.json --out results/_pilot/kosgd2_w1/manifest.json
python -B -I audits/kosgd2_pilot/gate.py --root . --source dataset/kosgd --selection audits/kosgd2_pilot/pilot_selection.json --manifest results/_pilot/kosgd2_w1/manifest.json --responses results/_pilot/kosgd2_w1/responses.json --out results/_pilot/kosgd2_w1/gate.json
```

responses.json은 모델 ID→목록이다. 각 항목은 `{logical_id, calls}`이며 call은
`{call_id, request_sha256, http_status, raw}`다. raw는 서버 원응답 JSON 문자열 또는 null이다.
자동 재시도는 없고 동일 call_id의 여러 시도를 입력하면 거부한다. B1의 call_id는 파일럿 논리 ID에
`/question_id`가 붙는다. systemone은 논리 ID와 같다. 응답 없음은 기록 부재면 INCOMPLETE,
명시된 null 응답이면 무효다. gate 출력에 응답 SHA와 completed_manifest를 보존하고 원 manifest를
덮어쓰지 않는다. 일반 history/report/archive는 이 디렉터리를 열거하지 않는다.
