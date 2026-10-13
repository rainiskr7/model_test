# 참조 구현 호출 층 (⑥b-2 R1·H·I)

어댑터는 로컬 체크포인트 폴더를 필수로 받으며 로더 진입 전에
`HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`을 설정한다. 다운로드 경로를
호출하지 않는다. 환경 설정은 후속 로딩에도 유지한다. 패키지 import에는
torch·transformers·autojev가 필요하지 않으며 모델 import는 함수 안에서만 한다.

| 어댑터 | 로딩 및 호출 | 읽기 전용 근거 |
| --- | --- | --- |
| Clef·Clef-Flash | `load(checkpoint)` → `(reference, model, processor)`; `respond(reference, model, processor, request, max_length=...)` → `reference.systemone(...)` | `.work/hf_cards/clef/joint_schema_model.py:494–520,547–579`; `.work/hf_cards/clefflash/joint_schema_model.py:494–520,547–579` |
| pplx v1 | `load_v1(checkpoint)` → `Decider.from_pretrained(local_path)`; `respond_v1(decider, request)` → 질문마다 `Decider.predict(state, question, images=...)` | `.work/hf_cards/pplx10/inference.py:35–64` |
| pplx v1.1 | `load_v11(checkpoint)` → `autojev.model.DecisionModel(checkpoint=...)`; `respond_v11(model, request)` → `server.EvaluationRequest(**request)` → `server.predict(model, body)` | `.work/hf_cards/pplx11/source_src_autojev_server.py:121–127,190–212` |

Clef의 참조 파일은 로컬 체크포인트의 `joint_schema_model.py`, v1은
`inference.py`에서 읽는다. v1.1은 미리 로컬 설치한 `autojev`를 사용한다.
`.work/hf_cards/`는 API 확인용이며 복사하거나 런타임/시험 의존성으로 사용하지 않는다.
로딩의 `reference=` 및 v1.1 응답의 `server=` 인자는 같은 API의 주입 지점이다.

Clef 응답은 전체 dict를 그대로 반환한다. v1은 이미 확률·choice를 포함한
Answer를 질문 ID 아래 그대로 놓으며 알 수 없는 usage를 만들어 내지 않는다.
v1.1의 8개 묶음·`(model(batch) / model.temperature).softmax(-1)`·`answer`
변환은 참조 서버가 소유한다. 어댑터에는 확률 변환·잘림·반올림·choice 선택이 없다.

P1 시험은 가짜 참조 서버의 동일 API 경계에 `prepare`·고정 logit `__call__`·
`temperature`를 가진 모델과 가짜 `autojev.model.answer`를 주입한다.
temperature fixture의 expected를 허용오차 1e-12로 대조하고 0회·2회 적용값과
구별한다. 동률 logit은 세 기대값이 같으므로 차이를 주장하지 않는다.
17개 질문은 8·8·1 묶음으로 처리되는지 확인한다. v1의 Answer 보존은 별도 검사다.

P0에 남는 것: 실제 `autojev` 모델 소스를 확보한 뒤 고정 logit을 실제 서버
경로에 주입하는 temperature 검사, 로컬 가중치·토크나이저와 실제 인코더의
잘림 동작, T0 전체 동등성 검사. 가짜 모듈 시험은 실제 모델 검증을 뜻하지 않는다.

v1.1 을 앱 밖에서 부를 때의 P0 확인 거리 (Claude 리뷰, `.work/hf_cards/pplx11/source_src_autojev_server.py`):
- `EvaluationRequest` 의 `model` 검사는 `ALIASES | {service.name}` (:79–81) 이고, `service` 는 모듈 전역으로
  앱 lifespan (:125–132) 에서만 채워진다. 어댑터가 lifespan 없이 `predict` 를 부르면 `service.name` 은
  `DEFAULT_MODEL` 그대로라 요청 `model` 은 별칭이어야 하고, 응답 `model` 도 `DEFAULT_MODEL` 이 된다.
- `load_v11` 은 `autojev` 가 이미 import 가능해야 한다 (v1 `Decider.from_pretrained` 와 달리
  `checkpoint/source/src` 를 `sys.path` 에 넣지 않는다).
