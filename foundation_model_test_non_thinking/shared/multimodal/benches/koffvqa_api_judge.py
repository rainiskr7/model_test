"""KOFFVQA API judge — 외부 OpenAI-compat 모델로 KOFFVQA 응답 채점.

KOFFVQA 의 generate.py 결과 .xlsx 를 입력으로 받아서, 지정한 API judge 모델
(OpenAI/Anthropic/사내 큰 모델 등) 로 Rubric 채점한다.

KOFFVQA 기본 judge (google/gemma-2-9b-it 로컬) 의 단일 모델 편향 완화 + 로컬 GPU 부담 제거.
2-judge 교차 비교 시 본 모듈 결과를 보조 점수로 활용 가능.

판정 prompt 버전: JUDGE_PROMPT_VERSION (점수 anchor + 근거 강제 형식).
prompt 변경 시 버전 문자열 갱신 → run_config 에 기록되어 추적 가능.

Usage:
  python koffvqa_api_judge.py \\
    --predfile /path/to/KOFFVQA/result/<dir>/*_gen.xlsx \\
    --target-model "Qwen/Qwen3.5-35B-A3B" \\
    --judge-model openai/gpt-4o-mini \\
    --judge-base-url https://api.openai.com/v1 \\
    --judge-api-key sk-xxx
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Optional

try:
    import pandas as pd
except ImportError as e:
    raise SystemExit("pandas 미설치 — `uv pip install pandas openpyxl`") from e

JUDGE_PROMPT_VERSION = "v3-anchored-with-examples"

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


def valid_score(score) -> bool:
    return not isinstance(score, bool) and isinstance(score, int) and 0 <= score <= 10


def judge_one(client, judge_model: str, question: str, response: str, criteria,
              seed: Optional[int] = None, max_tokens: int = 1024) -> tuple:
    crit_str = criteria if isinstance(criteria, str) else json.dumps(criteria, ensure_ascii=False, indent=2)
    prompt = JUDGE_PROMPT.format(question=question, criteria=crit_str, response=response)
    kwargs = {
        "model": judge_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": max_tokens,
    }
    if seed is not None:
        kwargs["seed"] = seed
    try:
        resp = client.chat.completions.create(**kwargs)
        text = resp.choices[0].message.content or ""
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


def main():
    # Runner helpers use direct-script imports internally.  Delay loading so
    # pure column/score validation remains importable without runner deps.
    benches_dir = str(Path(__file__).resolve().parent)
    if benches_dir not in sys.path:
        sys.path.insert(0, benches_dir)
    from common import (  # pylint: disable=import-outside-toplevel
        get_base_dir, get_timestamp, get_results_dir,
        save_json, build_run_config, make_client,
    )

    ap = argparse.ArgumentParser()
    ap.add_argument("--predfile", required=True, help="KOFFVQA generate.py 결과 .xlsx")
    ap.add_argument("--target-model", required=True, help="평가 대상 모델명 (결과 폴더 명명용)")
    ap.add_argument("--judge-model", required=True, help="judge 로 사용할 OpenAI-compat 모델명")
    ap.add_argument("--judge-base-url", required=True, help="judge API base_url")
    ap.add_argument("--judge-api-key", default=None, help="judge API key (없으면 OPENAI_API_KEY env)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--seed", type=int, default=None, help="judge seed")
    ap.add_argument("--judge-max-tokens", type=int, default=1024, help="judge 응답 max_tokens (default 1024 — 근거 포함)")
    ap.add_argument("--question-column", default=None, help="질문 컬럼 override (default: question)")
    ap.add_argument("--criteria-column", "--answer-column", dest="criteria_column", default=None,
                    help="채점 기준 컬럼 override (default: answer)")
    ap.add_argument("--response-column", "--prediction-column", dest="response_column", default=None,
                    help="모델 응답 컬럼 override (default: prediction)")
    args = ap.parse_args()

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

    client = make_client(args.judge_base_url, args.judge_api_key)

    base_dir = get_base_dir(__file__)
    ts = get_timestamp()
    out_dir = get_results_dir(
        base_dir, args.target_model, ts, "koffvqa_api_judge",
        category="vision", track="multimodal",
    )

    print(f"[koffvqa_judge] judge={args.judge_model}")
    print(f"[koffvqa_judge] target={args.target_model}")
    print(f"[koffvqa_judge] out={out_dir}")

    results = []
    scores = []
    for i, row in df.iterrows():
        q = str(row[q_col]) if pd.notna(row[q_col]) else ""
        crit = row[crit_col] if pd.notna(row[crit_col]) else ""
        resp = str(row[resp_col]) if pd.notna(row[resp_col]) else ""

        score, reason, err, raw_judge = judge_one(
            client, args.judge_model, q, resp, crit,
            seed=args.seed, max_tokens=args.judge_max_tokens,
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

    summary = {
        "benchmark": "KOFFVQA (API judge)",
        "judge_model": args.judge_model,
        "judge_prompt_version": JUDGE_PROMPT_VERSION,
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
            temperature=0.0,
            seed=args.seed,
            max_tokens=args.judge_max_tokens,
            judge_model=args.judge_model,
            judge_prompt_version=JUDGE_PROMPT_VERSION,
            eval_script_path=__file__,
            extra={
                "predfile": args.predfile,
                "limit": args.limit,
            },
        ),
    }

    save_json(out_dir / "results.json", results)
    save_json(out_dir / "summary.json", summary)

    print(f"\n[koffvqa_judge] avg score = {summary['avg_score']}")
    print(f"[koffvqa_judge] saved → {out_dir}")


if __name__ == "__main__":
    main()
