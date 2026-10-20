# jev_test — 결정 모델(Jev 계열) 공용 평가 틀

## 현재 상태 (2026-10-20, Claude 확인)

구현 판은 판 5 보정 3이며, 보정 4에서 문서·운영 절차를 보완했다. 최신 run은 `main_20261019T141841`이다. B1 BF16·FP8은 6셋 완료, pplx v1.1은 KoSGD full·actions_only test가 미완이고 나머지 셋은 완료했다. full test는 2,400 중 1,770 수신 후 10-20 중단되어 재개 대기 중이다.

[최신 보고서](results/_report/main_20261019T141841.md) · [운영 절차](ops/README.md)

남은 일은 pplx KoSGD 마무리·compare, 파일럿 200턴 → W1 동결 → kosgd2 전 모델, Clef·Clef-Flash·pplx v1 서빙 뒤 감사 v4 바이트 증거·T0다.

`POST /v1/systemone` 형식의 오픈웨이트 결정 모델을 로컬에서 서빙해 평가한다. 등록된 모델은 전부 돌린다
(처음: Cloudflare Clef · Clef-Flash, Perplexity pplx-decider v1 · v1.1). 결정 모델은 글을 쓰지 않고
타입이 정해진 질문(`noul` · `choice` · `score`)에 확률로 답하므로, 정확도와 함께 **보정(calibration)** 과
**오류율을 지킬 때 자동 처리할 수 있는 비율**을 잰다. 결과는 **공개 벤치마크 정답지 기준**이다 — 사람이
정답을 다시 확인하지 않으므로 "실제 업무에서 오류 몇 %" 가 아니라 "이 정답지 기준으로 오류 몇 % 이하" 로 읽는다.

- 계획: [`JEV_TEST_PLAN.md`](JEV_TEST_PLAN.md) (요약이 맨 앞에 있다)
- 데이터셋 목록: [`configs/datasets.yaml`](configs/datasets.yaml)
- 외부에서 받은 원본 데이터는 `dataset/` 에 두고 커밋하지 않는다 (`.gitignore`).

- 사전 감사 기록(라벨만 읽는 스크립트·실행 기록): [`audits/`](audits/README.md)

## 이력

현재 상태: **계획 단계** (개정 12, 평가 코드 없음). 첫 실행은 A 묶음 + B1.

판 5 Phase A는 역사 산출물 보고(`report`), 탐색적 질문 위험(`question-risk --history`),
kosgd2 가족 디스패치와 선정 스크립트를 추가한다. 명령 예와 모듈 지도는
[`jeveval/README.md`](jeveval/README.md)의 판 5 절에 있다. 데이터 생성·모델 호출·
파일럿·감사 v4/v5·최종 동결은 Phase B이며 이번 구현에 포함하지 않는다.

## 판 5 보정 1: 셋 전용 설정

기존 셋의 공용 설정은 0906d42 바이트로 동결한다. 새 셋의 목록은
[`configs/sets/`](configs/sets/)이며 kosgd2 항목·규칙·primary는 이곳으로 이동했다.
조회 격리와 전체 카탈로그/T0 예외는 [계약 보정 1](P1_CONTRACT.md)에 명시했다.
D1a는 T0 참조 대화를 선정 결과에서만 제외하고 RNG 소비를 보존한다.
현재 kosgd2 selection/split은 보정 전 산출물이며 Claude의 실데이터 재생성이 필요하다.

> 보정 2 정정(10-19): 위 문장은 구현 당시의 역사 설명이다. 기준 249f096의 실제 selection은 이미 1,200대화이고 split은 dev 240/test 960이며 26_00068은 제외되어 있다. 이번 구현은 해당 파일을 변경하거나 재생성하지 않는다. D1 = A는 사용자 승인(10-19)으로 기록하며, T0 실행·노출이 드러나면 동결 경계를 재검토한다.

## 판 5 보정 2: 오프라인 도구 구현

앞선 Phase A 범위 설명은 당시 이력이다. 보정 2는 감사 v4의 kosgd/kosgd2 프로필,
첫 fingerprint에 묶는 질문 지표 등록, 정답을 사용하지 않는 파일럿 선정·요청 준비·응답 게이트를 추가한다.
현재 selection/split 1,200/dev240/test960은 유지한다. 구현 단계에서 실데이터 감사·파일럿 선정·
모델 호출은 실행하지 않는다. W1 게이트 통과와 실험 동결은 아직 별도 단계다.
실행은 [감사 도구 지도](audits/README.md), 모듈 경계는 [jeveval 지도](jeveval/README.md)를 따른다.
