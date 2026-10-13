# jev_test — 결정 모델(Jev 계열) 공용 평가 틀

`POST /v1/systemone` 형식의 오픈웨이트 결정 모델을 로컬에서 서빙해 평가한다. 등록된 모델은 전부 돌린다
(처음: Cloudflare Clef · Clef-Flash, Perplexity pplx-decider v1 · v1.1). 결정 모델은 글을 쓰지 않고
타입이 정해진 질문(`noul` · `choice` · `score`)에 확률로 답하므로, 정확도와 함께 **보정(calibration)** 과
**오류율을 지킬 때 자동 처리할 수 있는 비율**을 잰다. 결과는 **공개 벤치마크 정답지 기준**이다 — 사람이
정답을 다시 확인하지 않으므로 "실제 업무에서 오류 몇 %" 가 아니라 "이 정답지 기준으로 오류 몇 % 이하" 로 읽는다.

- 계획: [`JEV_TEST_PLAN.md`](JEV_TEST_PLAN.md) (요약이 맨 앞에 있다)
- 데이터셋 목록: [`configs/datasets.yaml`](configs/datasets.yaml)
- 외부에서 받은 원본 데이터는 `dataset/` 에 두고 커밋하지 않는다 (`.gitignore`).

- 사전 감사 기록(라벨만 읽는 스크립트·실행 기록): [`audits/`](audits/README.md)

현재 상태: **계획 단계** (개정 12, 평가 코드 없음). 첫 실행은 A 묶음 + B1.
