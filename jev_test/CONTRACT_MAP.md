# 계약 현행 대응표 — 기준 d41e8b9

보정 4의 판정 해석을 유지하고 보정 5의 현행 추가·대체는 아래 별도 표로 명시한다. 기존 원문 해시·보존 블록은 불변이다.

계약 이력은 §11, 계획 이력은 §12다. 아래 21행은 1판 반박의 모든 체크리스트 항목을 다루며, 이력 절 위치와 기존 문장 효력을 한 행으로 묶었다. 각 현행 위치는 실제 본문 소절 제목이다. 이력에만 남긴 시행 상태·옛 명령은 대체 사유를 함께 기록했고 현재 규칙을 그 상태로 되돌리지 않는다.

`원문 앞 40자 sha` 열은 원문 앞 40자를 함께 표시하며(표 안 개행은 ↵), 해시는 아래 옛 문서의 지정 줄 범위 원문(줄바꿈 포함) 첫 40개 Unicode 문자를 UTF-8로 인코딩한 SHA-256이다. 줄 번호는 d41e8b9 기준이며 현재 줄 번호가 아니다. 보존 블록은 4백틱 코드 블록으로 감싸 제목/들여쓰기/개행/중복을 원문 그대로 둔다. fence와 안내 문장은 보존 payload 밖에 있다.

| 번호·쟁점 | 옛 문서·절·줄 | 원문 앞 40자 sha (SHA-256) | 적용 대상/시점 | 현행 규칙 위치(새 절) | 유지/대체/이력만 + 사유 |
|---|---|---|---|---|---|
| 1. 이력 절 위치·기존 문장의 효력 | P1_CONTRACT.md §11 / 계획 §12, 702–704행 | “기존 절의 문장은 역사 실행 규칙으로 보존하며 아래 명시적 추가 사항만 ”<br>`d5dad1b1a5ea23cb3ef9dea27754f99822038e10198d79324b639c47936dad47` | 모든 판의 규칙·당시 실행 기록 | 계약 §11; 계획 §12 | 대체: 현행과 당시 효력을 구분하고 보존 블록은 현재 지시가 아님 |
| 2. 셋 위치·family·primary | P1_CONTRACT.md §1-1, 708–713행 | “datasets 항목의 family 기본값은 set ID이며 splits”<br>`5d6a480ad1721ce6e05717506134f7021ac3172c93adce26ed77af6a3a960c2d` | 공용/overlay 각 셋 | 계약 §1-1a; 계획 §3-a | 대체: 공용 등록 대신 자기 overlay·고정 task 소유; 별칭 ID와 임시 primary 범위 유지 |
| 3. overlay 키 | P1_CONTRACT.md 보정 1 §1-1, 838–843행 | “최상위 키는 schema=set_overlay/1, id, tasks, ”<br>`4491c0e91d49622741f1a9674f7b11a4a0f79fa8f1cd6c0ab7643e5f40bc1b96` | overlay 스키마 | 계약 §1-1a; 계획 §3-a | 대체: 필수 5 + 선택 analysis만; 전역 키/lists 금지 유지 (관련 옛 계약 946행) |
| 4. 설정 격리 예외 | P1_CONTRACT.md 보정 1 §1-1, 845–850행 | “&#96;entry(root, set_id)&#96;는 공용 셋이면 overlay 디렉”<br>`b3991d64c3d5b8eb9d4200f2ce2962f42bedd144a1324b58c6318cb000624116` | 단일 셋 / T0·all | 계약 §1-1a; 계획 §3-a | 유지: T0 가족 합집합·all 선검사 예외, I/O 트랜잭션 보장으로 확대하지 않음 |
| 5. 동결 해시·역사 읽기 세 경계 | P1_CONTRACT.md 보정 1 §1-2, 862–869행 | “기존 셋 fingerprint의 파일 집합은 그대로다. overlay 셋”<br>`cd9c66877c147dfca704ecbd11d83334750aa20f91cca30ee12fda3b3145b81d` | 현재 restore / 역사 집계 / 역사 Item 재구성 | 계약 §1-2a·§5-1b; 계획 §7-1a | 유지: 현재 엄격 비교·역사 집계 면제·overlay 재구성 추가 SHA를 구별 |
| 6. 선정 1,200 현행·1,201 이력 | P1_CONTRACT.md 보정 1 §6-2 / 보정 2 정정, 882–885행 | “현재 커밋된 selection.json·kosgd2.json은 판 5의 ”<br>`191a2704fe0d02a8fa629811efe464b98f1048c500f46c3a7537d3180195411f` | 249f096 이후·이번 리팩터 | 계약 §6-2a; 계획 §4-6a | 대체: 이미 1,200/dev240/test960; 재생성하지 않음 (계획 529/531행·NOTES 422/425행도 원문 보존) |
| 7. 선정 RNG·T0 제외 순서 | P1_CONTRACT.md 보정 1 §6-2, 873–881행 | “kosgd2 항목과 기존 규칙은 configs/sets/kosgd2.ya”<br>`84e80ba8fe7f1a2c079f01c1c5acb1149b83301e33754a4b191c290d3d95ea5b` | 선정 재현 규칙 | 계약 §6-2a; 계획 §4-6a | 유지: T0도 choice 소비 후 제거; 대표 턴 보존과 분할 소속 보존을 구별 |
| 8. T0 미정·D1=A와 노출 검증 | jeveval/NOTES.md Phase A 변경 기록, 170–173행 | “Phase B 미정 사항: 새 선정이 옛 풀 밖의 USER 있는 모든 대”<br>`c4f50c5374f638714202fdcde51ad811e691f6b8d012ce9a493d7df92e193bb6` | 가족 풀 밖 조건·노출 발견 시 | 계약 §6-2a; 계획 §4-6a | 대체: D1 승인만 기록; 실제 노출 검증 완료 아님. 후보 부재/가족 split 부재 거부 유지 |
| 9. 감사 이름 | P1_CONTRACT.md 보정 2 §2-2, 915–918행 | “&#96;audits/audit_v4/run.py --set kosgd&#124;kosg”<br>`b43e20aec4cc276c331e8043b39adae3cb8f7c40f31bbdc385746be2814cef51` | 현행 v4 / 역사 v3 | 계약 §2-2a; 계획 §7-1a | 대체: v5는 v4 kosgd2 프로필; v3 원문·결과 보존 (계획 311/481행) |
| 10. 감사 후보 규칙 | JEV_TEST_PLAN.md 보정 2, 548–551행 | “종전 v4/v5는 audit_v4의 kosgd/kosgd2 프로필로 통합”<br>`2f6cef7bcc2b64fc221208b6b9ae40c4f483f4e9bf40a0e582a67ed55d7048c4` | 일반 후보 / 이번 수용 | 계약 §2-2a; 계획 §7-1a | 대체: 적용 규칙 전부 통과·full 우선·fallback, 이번 수용 full 아니면 사용자에게 중단; 옛 329행은 v3 당시 기록 |
| 11. 감사 증거 등급 | P1_CONTRACT.md 보정 2 §2-2, 920–927행 | “pplx_v1_1/B1 BF16/B1 FP8은 계획 body, execu”<br>`c2eb41e1f7d26b9752d1c39277bc492c6205de26e3549f5ca102daef166a66ca` | 동결 3모델 / 측정용 3모델 / 파생 가정 | 계약 §2-2a; 계획 §7-1a | 유지: 길이 PASS·전송 INCOMPLETE·hypothetical_direct를 실제 전송 증거와 구별 |
| 12. 독립 감사·주입 6/13 | P1_CONTRACT.md 보정 2 §2-2, 929–942행 | “R5 full은 의도 범위·최대2·act11종, actions_only는”<br>`70a2d08c4fac40f0b505118f21388317f08caa95fa18a6082bdfc3162dbc8d00` | v3 당시 / v4 / 외부 oracle 수용 | 계약 §2-2a·§9a; 계획 §7-1a | 유지: R5/R6 적용 범위·ID/type/role/label·13 주입·외부 oracle 별도 수용 |
| 13. Phase A/B 완료 의미 | P1_CONTRACT.md 보정 2 머리, 908–911행 | “이 절은 보정 1 이후의 등록·감사·파일럿 도구 계약이다. 앞선 문장과 ”<br>`5f9308c8af3ec00fa2a1dcbe666bfa1f819af9a9b097a5a76f09c04e4ec3ea29` | 구현 종료 / 운영 검증 | 계약 §9a; 계획 §7-1a·§8-a | 대체: 예정·미실행은 당시 기록; 오프라인 CLOSE를 파일럿/실험 동결/최종 서빙 완료로 읽지 않음 |
| 14. 질문 등록 세 상태 | P1_CONTRACT.md 보정 2 §7-4b, 946–964행 | “overlay는 선택적 최상위 &#96;analysis: configs/anal”<br>`988f1f9aadd28a7322709029f584801a126b0120de3195542b42f2249f1cab54` | 공용/역사 / 등록 overlay / 손상 | 계약 §7-4b; 계획 §4-2a | 대체: 항상 exploratory는 Phase A 범위; 선언 threshold 누락 test 거부·손상 수치 비공개 |
| 15. 봉인 순서 | P1_CONTRACT.md 보정 2 §7-4b, 951–958행 | “순서: dev 완료 → 일반 threshold → question-thr”<br>`6f9946c1fd0052c1d9a657fcf9b8758759e3caf83e1eeefdc66bd46ab7484908` | dev 완료부터 첫 test 전 | 계약 §7-4b; 계획 §4-2a | 유지: 일반 threshold→question-threshold→question_seal→주 seal; 빈 파일도 시작, 두 seal 사이 중단 복구 금지 |
| 16. 역사 완료·재구성 예외 | P1_CONTRACT.md 판 5 §5-1b, 740–759행 | “현재 code_sha256·공용 files와 비교하지 않는다. finge”<br>`3d4825475ed5f7c0b7ff22c826584cad61e5ba614a5a13b3aacb5fba701a7e73` | 역사 집계·Item·질문 분석 | 계약 §5-1b; 계획 §7-1a | 유지: unknown 분모·선택적 summary/run_id·파생 Item 거부; 원 산출물 집계는 허용 |
| 17. 파일럿 RNG·라벨 없는 입구 | JEV_TEST_PLAN.md 보정 2, 553–556행 | “파일럿 RNG 호출 순서: 옛 풀 유일 대화 3,000 ID 정렬 → R”<br>`7e5638d63d2f7a58abf1175f98572df9be570b80841ecc4b2635e07e61bd4174` | 한 번의 200 논리 요청 게이트 | 계약 §8-1b; 계획 §4-6a | 대체: sample→재정렬→같은 RNG choice 확정; gold/baseline 금지·부분 B1·10/11 경계·재시도 금지 |
| 18. 보고·출력 덮어쓰기 거부 | P1_CONTRACT.md 보정 2 §8-1, 969–970행 | “보고 renderer는 Report.audit_notes만 받으며 파일을”<br>`cd942ddbc0aad42592d67293310472366e36458fff4e8d0ab86f4556f72a35a2` | 감사 연결·새 report·역사 question-risk | 계약 §7-6a·§7-4b; 계획 §7-1a·§8-a | 유지: 입력 SHA·run identity 연결·새 파일만. 감사 script 변경은 출처 변경으로 검증 |
| 19. replay/offline 예외 | jeveval/NOTES.md 판 4 변경 기록, 149–153행 | “- replay는 검사 후 출처 바이트 복사와 replay/1 metad”<br>`5da0ae2576b595458f68cde65da9a623688e50e4993f0f042c4c03b82102c594` | 원본 복사·새 run 재판정 | 계약 §5-5c·§5-5d·§5-5e; 계획 §8-a | 유지: 전체 계획·논리 요청 전체 미룸·기존 final 거부·파생 full 출처·비용 재집계 |
| 20. archive SHA 잔존 충돌 | P1_CONTRACT.md §5-6 (정정: §8-6 F, 옛 608행), 274–274행 | “- 실행이 끝나면 &#96;jev_test/archive/&lt;run_id&gt;.tar”<br>`d2276613d84d6746c8f585e87c0d9e75aae9c318d7f2f0d6263aee30c86e1c31` | 완료 run 비공개 보존 | 계약 §5-6·§8-6 F | 대체: SHA는 archive.json, fingerprint는 불변 입력. 옛 본문 문장은 §11로 그대로 이동 |
| 21. extra FunctionChat만 | P1_CONTRACT.md §6-1 (관련 195/341행), 328–330행 | “### 6-1. &#96;extra&#96; (묶음 대표가 아닌 행)↵- Functio”<br>`e9f2f3d2510119c3934120ca96f1ddce528cf5ae9140b871b9dfcdeeb5c901eb` | 현재·역사 원 셋 fc_call_decision | 계약 §6-1·§6-1a; 계획 §3-a | 유지: stage_names 단일 소유·별칭/overlay 확장 없음·의미 분기 유지·현재 설정으로 역사 재해석 금지 |

## 보정 5 현행 대응 (기준 eb8e2fa 이후)

| 변경 | 현행 계약 | 대응·효력 |
|---|---|---|
| 선택적 예측·조건부 통과 확률 | §7-4c·§5-1b | selective/1 추가; 주 역사 상태·certify·compare 격리; archive 선택 수집 |
| family 의미 | §7-6b·§7-6c | 21행의 단계 ID 규칙은 유지하고 지표 의미만 family 승계; RNG·ID 해시는 실제 set |
| 복수 분석 선언·등록 | §7-4b·§7-4d | 14·15행 확장: 선언별 threshold, 전부 선검사, question→variant→주 seal; replay 복사 전 봉인 |
| 명시 감사 증거·독립 보조 보고 | §7-6a | 18행 확장: 기본 경로 유지, --audit-evidence로 명시한 적격 증거만 연결 |
| 수용 도구 | audits/stage2_20261021/README.md | C1 AST/nodeid, C2 명시 경로 정규화, C3 독립 열거 oracle; 실 run 실행은 운영자 |

## 원문 블록 정확 보존 근거

아래 SHA는 원문 전체 블록의 바이트(끝 개행 포함)다. 기존 본문의 대체된 문장도 각 이력 절의 `원문 보존 — 기존 본문 N행`에 별도로 남겼다. NOTES의 d41e8b9 전체 본문은 안내 머리 뒤에 바이트 그대로 남아 있다.

| 문서 | 옛 범위 | 바이트 수 | 전체 SHA-256 |
|---|---|---|---|
| P1_CONTRACT.md | 700–828 | 10102 | `5d711f29274efcd36b3e67a4120b1e72fbb56d1f2425e3d29a5343379f6d154c` |
| P1_CONTRACT.md | 829–905 | 7235 | `57c97ae3c2875111722ebddd4a7a4701d0e92ca16da17dcc2ed83e14c40e3a8f` |
| P1_CONTRACT.md | 906–984 | 6963 | `57c894b3293f3b97043d84204532ec5740be04c2e7f9fa8cce3bb24c5026bb37` |
| JEV_TEST_PLAN.md | 421–502 | 6906 | `a2766d4e8ddd376837a8ac141c9849067661dcb55c3a870c9c8c52c1acafca4e` |
| JEV_TEST_PLAN.md | 503–541 | 3399 | `f7cbec3695e5a945176e9698644ad31f10d5e8ab2d632bb12840854dfd6fc623` |
| JEV_TEST_PLAN.md | 542–567 | 2514 | `3ae784bcf20e8ac872f0a82c2966dc0bf44b8727fab1cc41bc111a2851946367` |

## NOTES 세부 규칙의 본문 위치

| d41e8b9 NOTES 범위 | 현행 위치 | 처리 |
|---|---|---|
| 3–15 | 계약 §8-1c | 타입·검증·전송 세부 규칙 유지 |
| 16 | 계약 §8-1c·§2-2a | 순수 함수 유지; systemone 미구현은 당시 상태로만 보존 |
| 17–29 | 계약 §7-6b | 채점 입력·모집단·비용·bootstrap 규칙 유지 |
| 31–36, 125–129 | 계약 §5-5e | 실행·파생·기록 예산 및 경고 반환·seal 선행 범위 유지 |
| 126, 136, 138 | 계약 §1-2a·§8-7a | 코드 지문 경로·B1 offsets·extra 구성원 및 항목 요약 경계 유지 |
| 145–153 | 계약 §3-1·§3-2·§5-5c·§5-5d | confidence/ECE와 replay 판 4 규칙 유지 |
| 155–173, 403–447 | 위 21행의 해당 현행 위치 | family/overlay/등록/감사/파일럿의 최신 범위 명시; 당시 검증 수·명령·변경 파일 목록은 이력 |
