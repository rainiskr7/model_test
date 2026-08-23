"""FunctionChat-Bench의 call 전용 exact-match 채점.

Ported from ``data/FunctionChat-Bench/src/evaluation_handler.py`` at commit
``5ddb0b5bb37d6423e1f3381ef693cda811a7847e``. Provider SDK가 필요한 원본
모듈을 import하지 않고, 원본의 결정론 채점 분기만 그대로 유지한다.
"""

import json
import logging
from typing import Any, Dict, Optional


CALL = "call"
SOURCE_COMMIT = "5ddb0b5bb37d6423e1f3381ef693cda811a7847e"
_EMPTY_ACCEPTABLE_SENTINELS = (
    "Only ground truth is allowed.",
    "The date should be expressed as 'tomorrow'. A specific date should not be designated.",
    "Since the user did not mention a specific year, it will fail if the date was created including the year in the submission.",
)


def get_acceptable_arguments(inp: Dict[str, Any]) -> Dict[str, Any]:
    acceptable_arguments = inp.get("acceptable_arguments", None)
    # Dialog 데이터에는 acceptable_arguments 가 **이미 dict 인** 항목이 있다 (핀 데이터 3건).
    # 상류는 호출 직전에 json.dumps 로 문자열화해서 이 경우를 피한다
    # (src/evaluation_handler.py:129). 여기서는 dict 를 그대로 돌려준다 —
    # dumps -> loads 왕복과 결과가 같고 불필요한 변환이 없다.
    #
    # 이걸 빠뜨리면 dict 가 f'"{...}"' 경로로 들어가 파이썬 repr 문자열이 되고,
    # 마지막 json.loads 에서 "Expecting property name enclosed in double quotes" 로
    # 죽는다 (2026-08-23 dialog 도입 시 실제로 발생).
    if isinstance(acceptable_arguments, dict):
        return acceptable_arguments
    if acceptable_arguments:
        try:
            acceptable_arguments = json.loads(acceptable_arguments)
        except Exception:
            acceptable_arguments = json.loads(f'"{acceptable_arguments}"')
    if acceptable_arguments is None:
        return {}
    if acceptable_arguments in _EMPTY_ACCEPTABLE_SENTINELS:
        return {}
    if isinstance(acceptable_arguments, str):
        acceptable_arguments = json.loads(acceptable_arguments)
    return acceptable_arguments


def compare_arguments(
    g_func_args: str,
    p_func_args: str,
    acceptable_arguments: Dict[str, Any],
) -> bool:
    def compare_value(val1: Any, val2: Any) -> bool:
        if isinstance(val1, str) and isinstance(val2, str):
            val1, val2 = val1.replace(" ", "").lower(), val2.replace(" ", "").lower()
        return val1 == val2

    try:
        j_g_func_args = json.loads(g_func_args)
        j_p_func_args = json.loads(p_func_args)
    except json.JSONDecodeError as exc:
        logging.error("Failed to parse JSON: %s", exc)
        return False

    # argument 할루시네이션: 정답에 없는 예측 key는 즉시 실패한다.
    for key, _val in j_p_func_args.items():
        if key not in j_g_func_args:
            return False
    for key, val in j_g_func_args.items():
        p_val = j_p_func_args.get(key)
        if not compare_value(p_val, val):
            acceptable_values = acceptable_arguments.get(key, [])
            if isinstance(acceptable_values, list) and not any(
                compare_value(p_val, acc) for acc in acceptable_values
            ):
                return False
            if isinstance(acceptable_values, str) and not compare_value(
                p_val, acceptable_values
            ):
                return False
    return True


def exact_match(inp: Dict[str, Any], out: Optional[Dict[str, Any]]) -> bool:
    """원본 ``EvaluationHandler.exact_match``의 boolean 결과만 반환한다."""
    if inp.get("type_of_output") != CALL:
        return False
    if out is None:
        return False

    ground_truth = inp.get("ground_truth", {})
    acceptable_arguments = get_acceptable_arguments(inp)

    if "tool_calls" in ground_truth:
        ground_truth_func = ground_truth.get("tool_calls", [{}])[0].get("function", {})
    else:
        ground_truth_func = ground_truth

    g_func_name = ground_truth_func.get("name")
    g_func_args = ground_truth_func.get("arguments")

    predict_tools = out.get("tool_calls", [])
    if predict_tools:
        predicted_func = predict_tools[0].get("function", {})
        p_func_name = predicted_func.get("name")
        p_func_args = predicted_func.get("arguments")
        if g_func_name == p_func_name:
            return compare_arguments(g_func_args, p_func_args, acceptable_arguments)
    return False
