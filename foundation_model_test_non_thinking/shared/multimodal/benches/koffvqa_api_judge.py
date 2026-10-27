"""KOFFVQA API judge — 외부 OpenAI-compat 모델로 KOFFVQA 응답 채점.

KOFFVQA 의 generate.py 결과 .xlsx 를 입력으로 받아서, 지정한 API judge 모델
(OpenAI/Anthropic/사내 큰 모델 등) 로 Rubric 채점한다.

KOFFVQA 기본 judge (google/gemma-2-9b-it 로컬) 의 단일 모델 편향 완화 + 로컬 GPU 부담 제거.
2-judge 교차 비교 시 본 모듈 결과를 보조 점수로 활용 가능.

판정 prompt 버전: JUDGE_PROMPT_VERSION (점수 anchor + 근거 강제 형식).
prompt 변경 시 버전 문자열 갱신 → run_config 에 기록되어 추적 가능.

Usage:
  python -m shared.multimodal.benches.koffvqa_api_judge \\
    --predfile /path/to/KOFFVQA/result/<dir>/*_gen.xlsx \\
    --target-model "Qwen/Qwen3.5-35B-A3B" \\
    --judge-model openai/gpt-4o-mini \\
    --judge-base-url https://api.openai.com/v1 \\
    --judge-api-key-env JUDGE_API_KEY
"""

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

from shared.multimodal.benches.koffvqa_judge_complete import completion_rc, valid_score

try:
    import pandas as pd
except ImportError as e:
    raise SystemExit("pandas 미설치 — `uv pip install pandas openpyxl`") from e

JUDGE_PROMPT_VERSION = "v3-anchored-with-examples"
# The version string is written by hand and can stay put while the template
# below is edited.  The hash cannot: it is the template itself.
def _prompt_template_hash(prompt_profile=""):
    template = ORIGINAL_JUDGE_PROMPT if prompt_profile == "original" else JUDGE_PROMPT
    return "sha256:" + hashlib.sha256(template.encode("utf-8")).hexdigest()

JUDGE_PROMPT = """아래는 한국어 시각 질의응답에 대한 객관적 채점 작업입니다.

질문:
{question}

평가 기준 (rubric / criteria):
{criteria}

모델 응답:
{response}

위 평가 기준에 따라 모델 응답을 0~10점 정수로 채점하세요.

점수 anchor (반드시 준수):
- 0~2점: 응답이 질문과 무관하거나 명백히 틀림. 평가 기준을 거의 충족하지 못함.
- 3~5점: 부분 정답. 일부 평가 기준만 충족. 사실 오류·환각 일부 존재.
- 6~8점: 대체로 정답. 대부분 기준 충족. 사소한 오류·누락 존재.
- 9~10점: 완전 정답 + 모든 평가 기준 충족 + 추가 가치 있는 설명.

채점 케이스 예시 (한국어 시각 VQA 도메인):
- 예 1) OCR 일부 오인식 (단어 1개 누락 또는 1글자 오타) → 4~6점 (부분정답).
- 예 2) 시각 근거 부족 (이미지를 보지 않고 말로만 짐작한 답) → 0~2점, reason 에 "시각 근거 부족" 명시.
- 예 3) 정답이지만 평가 기준 외 부가 설명만 풍부 → 평가 기준 자체로만 채점, 부가 설명은 가산점 안 줌.
- 예 4) 환각 (이미지에 없는 객체·텍스트 인용) → 즉시 0~2점, reason 에 "환각" 명시.

응답 시 주의:
- score 는 반드시 0~10 정수.
- reason 은 어느 기준이 충족·미충족인지 1~2 문장으로 명시 (단순히 "좋다/나쁘다" 금지).
- 시각 근거 부족·환각인 경우 reason 에 명시할 것.
- 평가 기준 외의 주관 평가 (말투, 길이) 는 채점 사유에서 제외.

반드시 다음 JSON 한 줄로만 답하세요:
{{"score": <0-10 integer>, "reason": "<채점 근거 1~2 문장>"}}"""


# Upstream maum-ai/KOFFVQA src/judges.py base_judge_prompt, stripped.
ORIGINAL_JUDGE_PROMPT = """어떤 사진에 대한 질문과 답변, 그리고 채점 기준이 다음과 같이 주어질 때, 주어진 채점 기준 항목을 기준으로 답변이 얼마나 옳은 답변인지 채점을 한 결과가 필요합니다.

사진은 주어지지 않지만, 아래 주어질 채점 기준을 바탕으로 어떤 내용인지 추정이 가능합니다. 채점 기준을 기반으로만 채점해 주세요.

채점의 목적은 주어진 답변이 사람이 보기에 얼마나 올바르고 질이 좋은 답변인지 판단하는 것입니다. 이것을 고려해서 채점해 주세요.

질문은 아래와 같습니다.
> "{0}"

그리고 이 질문에 대한 답변은 아래와 같습니다.
> "{1}"

위의 답변을 채점할 채점 기준은 다음과 같습니다.

{2}

위 기준을 바탕으로 답변을 10점 만점의 점수로 채점하세요. 단, 채점 기준의 각 항목을 부분적으로만 만족하는 경우에도 부분 점수는 없습니다. 무조건 0에서 10 사이의 점수로 채점해야 합니다.

단, 유의어 또는 유사한 표현을 사용한 설명은 말이 정확히 같지 않더라도 옳을 수 있습니다. 단, 여기에 예외가 있는데, 사진에 있는 글을 그대로 읽어야 하는 질문의 경우에는 유의어라도 정확히 일치하지 않게 잘못 읽었다면 틀린 답변입니다.

먼저 각 채점 기준에 대한 판단을 나열하고, 채점 결과를 종합하여 맨 마지막 줄에 "최종 점수: 10점 만점에 X점"의 형식으로 최종 점수를 쓰세요."""


def judge_one(client, judge_model: str, question: str, response: str, criteria,
              seed: Optional[int] = None, max_tokens: int = 1024,
              identity: Optional["ServedIdentity"] = None, *, provider=None, reasoning_effort=None, temperature_mode="", prompt_profile="") -> tuple:
    crit_str = criteria if isinstance(criteria, str) else json.dumps(criteria, ensure_ascii=False, indent=2)
    prompt = JUDGE_PROMPT.format(question=question, criteria=crit_str, response=response)
    if prompt_profile == "original":
        prompt = ORIGINAL_JUDGE_PROMPT.format(question, response, crit_str)
    kwargs = {
        "model": judge_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": max_tokens,
    }
    if temperature_mode == "omit":
        kwargs.pop("temperature")
    if seed is not None:
        kwargs["seed"] = seed
    extra_body = {}
    if provider:
        extra_body["provider"] = {"order": [provider], "allow_fallbacks": False, "require_parameters": True}
    if reasoning_effort:
        extra_body["reasoning"] = {"effort": reasoning_effort}
    if extra_body:
        kwargs["extra_body"] = extra_body
    try:
        resp = client.chat.completions.create(**kwargs)
        if identity is not None:
            _record_served_identity(identity, resp)
        text = resp.choices[0].message.content or ""
        if prompt_profile == "original":
            last = next((line.strip() for line in reversed(text.splitlines()) if line.strip()), "")
            last = re.sub(r"^(?:[-*•]|[0-9]+\.)[ \t]+", "", last, count=1)
            outer_period = last.endswith(".")
            if outer_period:
                last = last[:-1].rstrip()
            emphasis = re.fullmatch(r"(\*\*|\*)(.+)\1", last)
            if emphasis:
                last = emphasis[2].strip()
            if not outer_period and last.endswith("."):
                last = last[:-1].rstrip()
            match = re.fullmatch(r"최종 점수:\s*10점 만점에\s*(0|[1-9]|10)점", last)
            return (int(match[1]), text, None, text) if match else (
                None, text, "missing_final_score_line" if "최종 점수:" not in text else "invalid_final_score_line", text)
        m = re.search(r'\{[^{}]*"score"[^{}]*\}', text, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(0))
                score = data.get("score")
                if not valid_score(score):
                    return None, data.get("reason"), "score must be an integer from 0 through 10", text
                return score, data.get("reason"), None, text
            except json.JSONDecodeError as e:
                return None, None, f"json parse: {e}", text
        return None, None, "no JSON in judge response", text
    except Exception as e:
        return None, None, str(e), ""


# What the endpoint reported serving, collected across the run.  A judged score
# is only interpretable against the model that actually produced it.
class ServedIdentity:
    def __init__(self):
        self.values = {"model": set(), "system_fingerprint": set(), "provider": set()}


def _record_served_identity(identity: ServedIdentity, resp):
    for field in ("model", "system_fingerprint", "provider"):
        value = getattr(resp, field, None)
        if value:
            identity.values[field].add(str(value))


def served_identity_snapshot(identity: ServedIdentity):
    return {field: sorted(values) for field, values in identity.values.items() if values}


def _detect_column(cols, name):
    """Exact, case-insensitive column lookup; fuzzy substring matching is unsafe."""
    matches = [column for column in cols if str(column).casefold() == name.casefold()]
    return matches[0] if len(matches) == 1 else None


def resolve_columns(cols, question=None, criteria=None, response=None):
    """Resolve KOFFVQA columns and reject missing or duplicate role binding."""
    resolved = {
        "question": question or _detect_column(cols, "question"),
        "criteria": criteria or _detect_column(cols, "answer"),
        "response": response or _detect_column(cols, "prediction"),
    }
    missing = [role for role, column in resolved.items() if column not in cols]
    if missing:
        raise ValueError(f"컬럼 감지 실패 ({', '.join(missing)}). 실제 컬럼: {cols}")
    if len(set(resolved.values())) != len(resolved):
        raise ValueError(f"동일 컬럼을 여러 역할에 결합할 수 없음: {resolved}")
    return resolved["question"], resolved["criteria"], resolved["response"]


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _parse_args():
    """Parse args."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--predfile", required=True, help="KOFFVQA generate.py 결과 .xlsx")
    ap.add_argument("--target-model", required=True, help="평가 대상 모델명 (결과 폴더 명명용)")
    ap.add_argument("--judge-model", required=True, help="judge 로 사용할 OpenAI-compat 모델명")
    ap.add_argument("--judge-provider", default=None)
    ap.add_argument("--judge-reasoning-effort", choices=("", "none", "low", "medium", "high"), default=None)
    ap.add_argument("--judge-temperature-mode", choices=("", "omit"), default="")
    ap.add_argument("--judge-prompt-profile", choices=("", "original"), default="")
    ap.add_argument("--rejudge-purpose", choices=("", "migration"), default="")
    ap.add_argument("--judge-base-url", required=True, help="judge API base_url")
    ap.add_argument("--judge-api-key", default=None, help="judge API key (환경변수 옵션보다 우선)")
    ap.add_argument("--judge-api-key-env", default=None,
                    help="judge 키 환경변수 이름 (미설정·빈 값이면 오류; 두 옵션 생략 시 기존 OPENAI_API_KEY fallback)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--seed", type=int, default=None, help="judge seed")
    ap.add_argument("--judge-max-tokens", type=int, default=argparse.SUPPRESS, help="judge 응답 max_tokens (default 1024 — 근거 포함)")
    ap.add_argument("--question-column", default=None, help="질문 컬럼 override (default: question)")
    ap.add_argument("--criteria-column", "--answer-column", dest="criteria_column", default=None,
                    help="채점 기준 컬럼 override (default: answer)")
    ap.add_argument("--response-column", "--prediction-column", dest="response_column", default=None,
                    help="모델 응답 컬럼 override (default: prediction)")
    args = ap.parse_args()
    args.judge_max_tokens_requested = getattr(args, "judge_max_tokens", None)
    if args.judge_max_tokens_requested is None:
        args.judge_max_tokens = 1024
    if not args.judge_model.strip():
        ap.error("--judge-model must not be empty")
    if args.judge_max_tokens <= 0:
        ap.error("--judge-max-tokens must be a positive integer")
    args.judge_provider = getattr(args, "judge_provider", None) or None
    args.judge_reasoning_effort = getattr(args, "judge_reasoning_effort", None) or None
    args.judge_temperature_mode = getattr(args, "judge_temperature_mode", "")
    args.judge_prompt_profile = getattr(args, "judge_prompt_profile", "")
    args.rejudge_purpose = getattr(args, "rejudge_purpose", "")
    return args


def _resolve_judge_api_key(args):
    """Prefer the explicit key; an explicitly named environment variable must exist."""
    if args.judge_api_key is not None:
        return args.judge_api_key
    name = getattr(args, "judge_api_key_env", None)
    if name is None:
        return None
    key = os.environ.get(name)
    if not key:
        raise ValueError(f"--judge-api-key-env {name!r}: 환경변수가 없거나 빈 값입니다")
    return key


def _load_predictions(args):
    """Load the workbook and validate column bindings."""
    df = pd.read_excel(args.predfile)
    cols = df.columns.tolist()
    print(f"[koffvqa_judge] loaded {args.predfile}: {len(df)} rows / cols: {cols}")

    try:
        q_col, crit_col, resp_col = resolve_columns(
            cols,
            question=args.question_column,
            criteria=args.criteria_column,
            response=args.response_column,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"[koffvqa_judge] columns: q={q_col} criteria={crit_col} response={resp_col}")

    if args.limit:
        df = df.head(args.limit)
    return df, q_col, crit_col, resp_col


def _prepare_output(args, get_base_dir, get_timestamp, get_results_dir):
    """Prepare output."""
    base_dir = get_base_dir(__file__)
    ts = get_timestamp()
    out_dir = get_results_dir(
        base_dir, args.target_model, ts, "koffvqa_api_judge",
        category="vision", track="multimodal",
    )

    print(f"[koffvqa_judge] judge={args.judge_model}")
    print(f"[koffvqa_judge] target={args.target_model}")
    print(f"[koffvqa_judge] out={out_dir}")
    return out_dir


def _judge_rows(args, df, q_col, crit_col, resp_col, client):
    """Judge workbook rows and collect served identity."""
    identity = ServedIdentity()
    results = []
    scores = []
    for i, row in df.iterrows():
        q = str(row[q_col]) if pd.notna(row[q_col]) else ""
        crit = row[crit_col] if pd.notna(row[crit_col]) else ""
        resp = str(row[resp_col]) if pd.notna(row[resp_col]) else ""

        score, reason, err, raw_judge = judge_one(
            client, args.judge_model, q, resp, crit,
            seed=args.seed, max_tokens=args.judge_max_tokens, identity=identity,
            provider=args.judge_provider, reasoning_effort=args.judge_reasoning_effort,
            temperature_mode=args.judge_temperature_mode,
            prompt_profile=args.judge_prompt_profile,
        )
        if score is not None:
            scores.append(score)

        results.append({
            "idx": int(i),
            "dataset_item_id": str(row["index"]) if "index" in df.columns and pd.notna(row["index"]) else str(i),
            "question": q,
            "response": resp,
            "criteria": crit if isinstance(crit, str) else str(crit),
            "score": score,
            "reason": reason,
            "raw_judge_output": raw_judge,
            "error": err,
        })

        if (i + 1) % 25 == 0:
            avg = sum(scores) / len(scores) if scores else 0.0
            print(f"[koffvqa_judge] {i+1}/{len(df)} scored={len(scores)} avg={avg:.2f}")
    return results, scores, identity


def _build_summary(args, results, scores, identity, build_run_config):
    """Build summary."""
    summary = {
        "benchmark": "KOFFVQA (API judge)",
        "judge_model": args.judge_model,
        "judge_request": {
            "model": args.judge_model,
            "provider": args.judge_provider,
            "reasoning_effort": args.judge_reasoning_effort,
            "max_tokens_requested": args.judge_max_tokens_requested,
            "max_tokens_effective": args.judge_max_tokens,
            "temperature": None if args.judge_temperature_mode == "omit" else 0.0,
            **({"temperature_mode": "omit"} if args.judge_temperature_mode == "omit" else {}),
            "seed": args.seed,
        },
        "judge_prompt_version": "koffvqa-original-v1" if args.judge_prompt_profile == "original" else JUDGE_PROMPT_VERSION,
        "judge_prompt_template_sha256": _prompt_template_hash(args.judge_prompt_profile),
        "judge_base_url": args.judge_base_url,
        "judge_served_identity": served_identity_snapshot(identity),
        "target_model": args.target_model,
        "predfile": args.predfile,
        "prediction_sha256": file_sha256(args.predfile),
        "total": len(results),
        "scored": len(scores),
        "avg_score": sum(scores) / len(scores) if scores else None,
        "max_possible_score": 10,
        "run_config": build_run_config(
            benchmark="KOFFVQA-API-judge",
            model=args.target_model,
            base_url=args.judge_base_url,
            temperature=None if args.judge_temperature_mode == "omit" else 0.0,
            seed=args.seed,
            max_tokens=args.judge_max_tokens,
            judge_model=args.judge_model,
            judge_prompt_version="koffvqa-original-v1" if args.judge_prompt_profile == "original" else JUDGE_PROMPT_VERSION,
            eval_script_path=__file__,
            extra={
                "predfile": args.predfile,
                "limit": args.limit,
            },
        ),
    }
    # The external judge does not apply the target model's SERVING_* constraints.
    config = summary["run_config"]
    if args.judge_prompt_profile:
        summary["judge_prompt_profile"] = args.judge_prompt_profile
        config["judge"]["prompt_profile"] = args.judge_prompt_profile
        config["judge"]["prompt_template_sha256"] = summary["judge_prompt_template_sha256"]
    if args.rejudge_purpose:
        summary["rejudge_purpose"] = args.rejudge_purpose
        config["extra"]["rejudge_purpose"] = args.rejudge_purpose
    decoding = {"temperature": None if args.judge_temperature_mode == "omit" else 0.0,
                "max_tokens": args.judge_max_tokens, "seed": args.seed}
    if args.judge_temperature_mode == "omit":
        decoding["temperature_mode"] = "omit"
        config["decoding_requested"] = dict(decoding)
    if "decoding" in config and config["decoding"] != decoding:
        config["decoding"] = decoding
    if "serving_constraints" in config:
        config["serving_constraints"] = {"unsupported_sampling_params": [], "max_output_tokens": None,
                                         "force_skip_special_tokens": None, "removed_parameters": [],
                                         "skip_special_tokens": None}
    return summary


def _save_results(out_dir, results, summary, save_json):
    """Write judge artifacts and print the final score."""
    save_json(out_dir / "results.json", results)
    save_json(out_dir / "summary.json", summary)

    print(f"\n[koffvqa_judge] avg score = {summary['avg_score']}")
    print(f"[koffvqa_judge] saved → {out_dir}")


def main():
    """Coordinate delayed imports, workbook loading, judging and storage."""
    args = _parse_args()
    try:
        judge_api_key = _resolve_judge_api_key(args)
    except ValueError as exc:
        print(f"[koffvqa_judge] {exc}", file=sys.stderr)
        return 2
    # Delay runner dependencies so pure column/score validation stays importable.
    from shared.multimodal.benches.common import (  # pylint: disable=import-outside-toplevel
        get_base_dir, get_timestamp, get_results_dir,
        save_json, build_run_config, make_client,
    )
    df, q_col, crit_col, resp_col = _load_predictions(args)
    out_dir = _prepare_output(args, get_base_dir, get_timestamp, get_results_dir)
    summary_path, config_path = out_dir / "summary.json", out_dir / "run_config.json"
    if summary_path.exists() or config_path.exists() or (out_dir / "results.json").exists():
        try:
            stored = json.loads((summary_path if summary_path.exists() else config_path).read_text(encoding="utf-8"))
            stored_config = stored.get("run_config") if summary_path.exists() else stored
            if stored_config is None and config_path.exists():
                stored_config = json.loads(config_path.read_text(encoding="utf-8"))
            stored_config = stored_config or {}
            stored_judge = stored_config.get("judge") or {}
            old_profile = stored.get("judge_prompt_profile", stored_judge.get("prompt_profile", ""))
            old_purpose = stored.get("rejudge_purpose", (stored_config.get("extra") or {}).get("rejudge_purpose", ""))
            old_version = stored.get("judge_prompt_version", stored_judge.get("prompt_version"))
            old_hash = stored.get("judge_prompt_template_sha256", stored_judge.get("prompt_template_sha256"))
            version = "koffvqa-original-v1" if args.judge_prompt_profile == "original" else JUDGE_PROMPT_VERSION
            if (old_profile != args.judge_prompt_profile or old_purpose != args.rejudge_purpose
                    or (old_version is not None and old_version != version)
                    or (old_hash is not None and old_hash != _prompt_template_hash(args.judge_prompt_profile))):
                print("[koffvqa_judge] 지시문/재판정 목적 불일치 — 재판정 저장 위치를 나눠라", file=sys.stderr)
                return 2
            request = stored.get("judge_request")
            if "judge_request" in stored:
                old = (request["model"], request["provider"] or None, request["reasoning_effort"] or None,
                       request["max_tokens_effective"], request["temperature"], request["seed"])
                mode = request.get("temperature_mode")
            else:
                config = stored.get("run_config") if summary_path.exists() else stored
                if config is None and config_path.exists():
                    config = json.loads(config_path.read_text(encoding="utf-8"))
                decoding = config["decoding"]
                model = stored.get("judge_model") or (config.get("judge") or {}).get("model")
                old = (model, None, None, decoding["max_tokens"], decoding["temperature"], decoding["seed"])
                mode = decoding.get("temperature_mode")
            current = (args.judge_model, args.judge_provider, args.judge_reasoning_effort,
                       args.judge_max_tokens, None if args.judge_temperature_mode == "omit" else 0.0, args.seed)
            if mode:
                old += (mode,)
            if args.judge_temperature_mode == "omit":
                current += ("omit",)
            if old != current:
                print("[koffvqa_judge] 판정기 프로파일 불일치 — 재판정 저장 위치를 나눠라", file=sys.stderr)
                return 2
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            print(f"[koffvqa_judge] 기존 판정 기록 확인 실패 ({type(exc).__name__}) — 쓰지 않는다", file=sys.stderr)
            return 2
    client = make_client(args.judge_base_url, judge_api_key)
    results, scores, identity = _judge_rows(args, df, q_col, crit_col, resp_col, client)
    summary = _build_summary(args, results, scores, identity, build_run_config)
    _save_results(out_dir, results, summary, save_json)
    return completion_rc(results, summary)


if __name__ == "__main__":
    raise SystemExit(main())
