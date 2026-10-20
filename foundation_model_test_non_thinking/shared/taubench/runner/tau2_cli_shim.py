#!/usr/bin/env python3
"""tau2.cli 를 그대로 실행하되, 서빙 백엔드가 거부하는 sampling 파라미터를
**요청 직전에** 제거하고 무엇을 뺐는지 기록한다.

왜 여기여야 하는가
------------------
후보(candidate) 요청의 llm_args 는 우리가 `--agent-llm-args` 로 넘긴 것이
전부가 아니다. tau2 의 Orchestrator 가 시뮬레이션마다

    orchestrator.py:527  self.agent.set_seed(self.seed)
    agent/base/llm_config.py:41  self.llm_args["seed"] = seed

로 **런타임에 seed 를 주입**한다. 그래서 run_manifest.json 의 agent_info.llm_args
에는 seed 가 없는데도 실제 HTTP 요청에는 들어간다. diffusion 백엔드는 seed 를
거부한다 — 같은 엔드포인트에 seed 만 넣고 빼서 확인했다 (200 vs 400,
"The temperature, min_p, seed, ... are not yet supported with diffusion models").
그 결과 telecom 40 태스크가 전부 BadRequestError 로 죽었고 r1·r2·r3 세 런이
모두 not_measured 로 남았다.

upstream 은 이 저장소가 SHA 로 핀한 외부 체크아웃이라 고치지 않는다. 대신
tau2.cli 를 부르기 전에 `tau2.utils.llm_utils.completion` 을 감싼다. llm_utils 는
`from litellm import completion` 으로 이름을 가져오므로 litellm 쪽을 패치해도
소용이 없다 — 반드시 llm_utils 의 이름을 바꿔야 한다.

무엇을 적용하는가
-----------------
파라미터 제거만으로는 부족하다. 제거만 하면 400 은 사라지지만 **본문이 빈
응답**이 온다 — 실측: 같은 엔드포인트에 skip_special_tokens 없이 보내면
content=None (completion_tokens 8, finish_reason=stop), `skip_special_tokens:
false` 를 넣으면 "1+1은 **2**입니다." 가 온다. Gemma4 계열 파서가 special
token 경계로 content 를 잘라내기 때문이고, 이 저장소는 이미 그 사실을
shared/serving/constraints.py 의 주석에 기록해 두었다.

그래서 손으로 파라미터를 고르지 않고 **serving.constraints.apply() 를 그대로
호출한다.** 그것이 이 저장소의 단일 진실 공급원이고, 다른 트랙(nlu·multimodal
·functionchat)이 이미 통과시킨 규약이다. apply() 는 세 가지를 한다:
미지원 sampling 파라미터 제거 · skip_special_tokens 강제 · max_tokens 상한.
litellm 은 OpenAI 비표준 필드를 extra_body 로 받으므로 sdk=True 로 부른다.

- **요청이 제약 있는 엔드포인트로 갈 때만** 적용한다
  (`TAUBENCH_CONSTRAINED_API_BASE` 와 요청의 api_base 가 같을 때). 사용자
  시뮬레이터를 다른 서버나 외부 API 로 붙였다면 그쪽 프로토콜은 이 프로파일이
  말하는 대상이 아니다. 말없이 바꾸면 그 비교 자체가 무효가 된다.

정직성
------
빼는 것은 공짜가 아니다. seed 를 빼면 그 런은 **서버측 결정론 제어 없이** 돈
것이다. 뺀 목록을 `TAUBENCH_REMOVED_PARAMS_OUT` 에 적어 부모 러너가
run_manifest.json 에 남기게 한다. 게이트가 이 값을 코호트 키로 쓸 수 있어야
seed 있는 런과 없는 런이 한 표에 섞이지 않는다.
"""

from __future__ import annotations

import json
import os
import sys
from copy import deepcopy
from pathlib import Path


def _load_apply():
    """shared/serving/constraints.apply 를 가져온다.

    shim 은 tau2 전용 venv(.venv-taubench)에서 파일로 실행된다.
    run_taubench.py 가 자식 PYTHONPATH 에 이 저장소 루트를 공급한다.
    """

    from shared.serving.constraints import apply

    return apply


def _normalize_base(url: str) -> str:
    """비교용 정규화. 끝의 '/' 만 다른 주소를 다른 서버로 보지 않는다."""
    return (url or "").strip().rstrip("/")


def _write_record(path: str | None, payload: dict) -> None:
    if not path:
        return
    try:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(out.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(out)
    except Exception as exc:  # 기록 실패가 평가를 죽이면 안 된다
        print(f"[tau2-shim] 제거 기록 실패: {exc}", file=sys.stderr)


def _profile_is_active() -> bool:
    """이 모델에 서빙 프로파일이 걸려 있는가.

    셋 다 미설정이면 apply() 는 payload 를 건드리지 않는다. 그럴 때는 아예
    패치하지 않아 수정 전과 실행 경로가 같게 둔다 (gemma 등 제약 없는 모델).
    """

    return any(
        os.environ.get(name)
        for name in (
            "SERVING_UNSUPPORTED_SAMPLING_PARAMS",
            "SERVING_MAX_OUTPUT_TOKENS",
            "SERVING_FORCE_SKIP_SPECIAL_TOKENS",
        )
    )


def _request_base(kwargs: dict) -> str | None:
    """이 요청이 실제로 향하는 주소.

    litellm 은 ``api_base`` 와 ``base_url`` 을 모두 받고 ``base_url`` 이
    우선한다(litellm/main.py). 한쪽만 보면 shim 이 검사한 주소와 실제 목적지가
    갈릴 수 있다. 둘 다 없으면 litellm 이 환경변수로 주소를 정하므로 여기서는
    **알 수 없음**(None)이고, 조용히 통과시키는 대신 그 사실을 센다.
    """

    for key in ("base_url", "api_base"):
        value = kwargs.get(key)
        if value:
            return _normalize_base(str(value))
    return None


def _wrap_completion(original_completion, apply, constrained_base, candidate_model,
                     removed, adjusted, counts):
    """요청 주소별로 제약을 적용하고 호출자가 소유한 역할별 상태를 누적한다."""
    def completion_with_serving_profile(*args, **kwargs):
        base = _request_base(kwargs)
        if base is None:
            counts["base_unknown"] += 1
            return original_completion(*args, **kwargs)
        if base != constrained_base:
            counts["unmatched"] += 1
            return original_completion(*args, **kwargs)
        counts["matched"] += 1
        model = str(kwargs.get("model") or "")
        role = "candidate" if (candidate_model and model == candidate_model) else "user"
        before = deepcopy(kwargs)
        # litellm 은 OpenAI 비표준 필드를 extra_body 로 받는다 → sdk=True.
        apply(kwargs, sdk=True)
        for name in before:
            if name not in kwargs:
                removed[role].add(name)
        before_extra = before.get("extra_body") or {}
        after_extra = kwargs.get("extra_body") or {}
        for name in before_extra:
            if name not in after_extra:
                removed[role].add(name)
        if before.get("max_tokens") != kwargs.get("max_tokens"):
            adjusted[role].add("max_tokens")
        if before_extra.get("skip_special_tokens") != after_extra.get("skip_special_tokens"):
            adjusted[role].add("skip_special_tokens")
        return original_completion(*args, **kwargs)

    return completion_with_serving_profile


def _record_payload(patched, constrained_base, candidate_model, counts, removed, adjusted):
    """역할별 변경 사항을 정렬하고 기존 키 순서로 기록 본문을 조립한다."""
    return {
        "patched": patched,
        "constrained_api_base": constrained_base or None,
        "candidate_model": candidate_model or None,
        # patched=True 는 함수를 갈아끼웠다는 뜻일 뿐이다. 후보 요청을
        # 한 번이라도 실제로 매칭했는지는 이 카운터로만 알 수 있다.
        "request_counts": counts,
        "removed_params": sorted(removed["candidate"]),
        "adjusted_params": sorted(adjusted["candidate"]),
        "user_removed_params": sorted(removed["user"]),
        "user_adjusted_params": sorted(adjusted["user"]),
    }


def main() -> None:
    constrained_base = _normalize_base(os.environ.get("TAUBENCH_CONSTRAINED_API_BASE", ""))
    candidate_model = (os.environ.get("TAUBENCH_CANDIDATE_MODEL") or "").strip()
    out_path = os.environ.get("TAUBENCH_REMOVED_PARAMS_OUT")

    # 역할별로 나눠 기록한다. 주소만 보고 뭉치면, 사용자 시뮬레이터를 후보와
    # 같은 주소에 붙였을 때 사용자 쪽 제거가 후보 기록으로 새어 들어가
    # "사용자 제어가 제거되면 비교 자격을 뺀다"는 게이트를 우회한다.
    removed = {"candidate": set(), "user": set()}
    adjusted = {"candidate": set(), "user": set()}
    counts = {"matched": 0, "unmatched": 0, "base_unknown": 0}
    patched = False

    if constrained_base and _profile_is_active():
        apply = _load_apply()
        from tau2.utils import llm_utils

        llm_utils.completion = _wrap_completion(
            llm_utils.completion, apply, constrained_base, candidate_model, removed, adjusted, counts,
        )
        patched = True
        print(
            f"[tau2-shim] {constrained_base} 로 가는 요청에 서빙 프로파일을 적용한다"
            f" (후보 모델={candidate_model or '미지정'})",
            file=sys.stderr,
        )

    from tau2.cli import main as tau2_main

    try:
        tau2_main()
    finally:
        _write_record(
            out_path,
            _record_payload(patched, constrained_base, candidate_model, counts, removed, adjusted),
        )


if __name__ == "__main__":
    main()
