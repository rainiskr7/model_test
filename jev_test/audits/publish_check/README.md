# 공개 전 원문 검사 — 판 5 보정 4

무엇: reader가 반환하는 원문과 공개 예정 Git 이력의 텍스트 일치 검사. 입력: jev_test root, 고정 base/head, 외부 보고 경로. 출력: 원문 없는 JSON과 수량 요약. 실데이터 실행은 Claude가 담당하며 구현 시험은 합성 입력만 사용한다.

```bash
BASE=$(git rev-parse origin/main)
HEAD_OID=$(git rev-parse HEAD)
"$JEV_PY" -B -m audits.publish_check --root . --base "$BASE" --head "$HEAD_OID" --out "$SCRATCH_REPORT"
```

`SCRATCH_REPORT`는 저장소 밖 scratchpad의 **새 파일**이어야 한다. 기존 출력은 거부한다. 운영 venv의 패키지를 변경하지 않는다. numpy와 기존 reader의 pyarrow·PyYAML 환경이 필요하다. 최종 커밋 후 실행하고 보고의 head가 실제 push할 SHA인지 확인한다. origin/main의 최신성 확인은 실행자가 담당한다.

## 범위와 판정

base..head의 모든 커밋에서 저장소 전체 tree를 순회하며, 금지 경로·미지원 항목 검사는 전체 tree에 대해 유지한다. base의 이력에서 도달 가능한 blob은 이미 공개된 것으로 보고 읽기·디코딩·대조를 생략하며 blob 보고 row도 만들지 않는다. 나머지 새 blob만 OID별로 한 번 읽기·디코딩하고, 해당 blob의 모든 커밋·경로 연결을 보고에 보존한다. counts의 `already_public_blobs`는 범위 안 tree에서 건너뛴 고유 blob 수이며, `total_blobs`는 검사 대상인 새 blob 수다. 각 셋의 창 색인을 순차로 만들며 디코딩한 blob view는 보고 경로 옆의 임시 디렉터리에 보관했다가 삭제한다. 빈 커밋 범위, Git 실패, 원문 로딩 실패를 성공으로 처리하지 않는다.

6셋 모두 기존 `entry`·`read_set_rows` API를 사용하며 풀/split으로 원문 행을 줄이지 않는다. KoSGD 발화, FunctionChat 메시지와 중첩 도구 문자열, K-MHaS/KOTE text, KorFin SRC/ASPECT, KLUE context/question/answer 문자열을 추출한다. NFC 뒤 모든 `str.isspace()` 문자를 제거하고 기본 L=12 **코드포인트** 창으로 비교한다. 필드별 경계를 넘는 창은 만들지 않는다. 같은 정규화 필드는 한 번 색인하고 출처 ID·필드를 함께 보존한다.

UTF-8 원시 blob과 `.json`/`.jsonl`의 디코딩한 문자열 값들을 모두 검사한다. JSON 키 자체는 decoded view 대상이 아니지만 raw view에는 남는다. 문자열값에 중첩 직렬화된 JSON이나 다른 인코딩·압축을 재귀적으로 풀지는 않는다. 바이너리, UTF-8/JSON 디코드 실패, 크기 초과는 미검사 실패다. 동일 OID가 JSON과 일반 텍스트 경로에 있으면 두 view를 모두 검사한다.

64비트 해시는 후보 검색만 담당하고 원문 창과 정확 비교해서 확정한다. 같은 원문·blob 위치 차이를 유지하는 겹치거나 인접한 창을 구간으로 합친다. raw view 오프셋은 정규화한 blob, JSON view는 `value_index`번째 문자열 값 안의 정규화 문자 오프셋이다. 원본 파일 바이트 오프셋이 아니다. `source_start`도 정규화한 원문 필드 안의 위치다.

출력은 OID·경로·커밋·셋·원문 ID/필드·위치·길이만 포함하며 일치 문구나 예외 원문은 출력하지 않는다. 원문 ID가 필요한 검토 증거이므로 보고서는 저장소에 커밋하지 않는다. JSON 파일은 원문 manifest(행·고유 필드·창 수·투영 해시), 도구 소스 해시, 정규화와 제한, 전체/검사/실패 blob 수를 포함한다.

종료 코드 0은 모든 검사 대상 새 blob과 원문 입력을 검사했고 일치·금지 경로·미지원 항목이 없다는 뜻이다. 1은 일치 또는 검사 실패가 있는 보고서, 2는 검사 자체를 완료하지 못했음을 뜻한다. 일치가 있으면 Claude가 해당 blob·view·구간별로 원문을 확인하고 공개 문구·라이선스 근거를 별도 기록한다. 무해 목록을 자동 적용하지 않는다.

## 한계와 자원

base에서 도달 가능한 blob을 다른 경로로 복사해도 OID가 같으면 내용 검사를 생략한다. 금지 경로 검사는 그대로 적용한다.

이 검사는 reader에 의존하며 독립 라벨 감사가 아니다. KoSGD의 마지막 USER 뒤 SYSTEM 발화와 schema 파일 등 reader가 내놓지 않는 원문은 범위 밖이다. **검사한 reader 텍스트에서 유래한 연속 조각**에 한해서 검출 범위를 주장한다. 사람이 직접 붙인 원문뿐 아니라 다른 reader·schema 경로에서 생긴 산출물, 변환·요약·이미지 속 텍스트까지 덮는다는 보장은 없다.

L보다 짧은 조각, 공백 이외의 문자 변형, 지원하지 않는 escape는 놓칠 수 있다. 반복 문구·도구 설명·대화 prefix·공유 문맥은 일치 구간을 많이 만든다. exact match는 재배포 허용 여부를 결정하지 않는다.

배열은 창마다 16바이트(해시8+문서4+위치4)이며 1천만 창은 본체만 약160MB다. 원문 reader 목록·출처·정렬·blob view가 추가된다. reader 자체가 전체 행을 목록으로 반환하므로 원자료 로딩의 메모리를 제한하지 못한다. `--max-blob-bytes` 기본 256MiB, `--max-candidates`는 view·셋당 기본 2,000,000 후보다. 제한 초과는 검사를 생략한 성공이 아니라 실패다. 필요하면 자원 확인 후 제한을 올리고 그 값을 보고에 남긴다.

## 파일 지도와 시험

| 파일 | 역할 |
|---|---|
| `sources.py` | reader 호출·셋별 필드 추출·정규화·중복 제거 |
| `windows.py` | numpy 창 색인·충돌 제거·구간 병합 |
| `git_objects.py` | 고정 OID·전체 tree·batch blob·금지 경로 |
| `decode.py` | UTF-8·JSON/JSONL view |
| `scan.py` | blob 임시 캐시·셋별 실행·실패 집계 |
| `report.py` | 도구 해시·외부 새 JSON 파일 |
| `__main__.py` | 인자·고정 오류 출력·종료 코드 |

합성 시험은 `tests/publish_check/`다. 금지 경로는 attempts/final, dataset, .work, .env, archive와 T0 inputs/reference/server/variants 원기록이다. submodule 같은 비blob 항목도 미지원으로 보고하며 승인하지 않는다.
