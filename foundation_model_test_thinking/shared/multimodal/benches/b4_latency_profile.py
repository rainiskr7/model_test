"""Track B-4 — Latency profiling.

조건별 응답 지연시간 비교 (이미지 유무·해상도·다중이미지 영향):
- A: text-only
- B: 256px 단일 이미지 + 텍스트
- C: 1024px 단일 이미지 + 텍스트
- D: multi-image (3장 512px) + 텍스트

조건당 reps 회 반복 (default 50). 메트릭:
- TTFT (Time to First Token) — 스트리밍 첫 chunk 도달 시간
- total — 응답 종료까지 총 시간
- completion_tokens (heuristic: chunk 수 또는 text length)
- tokens_per_sec (≈ completion / total)
- 각 메트릭 P50 / P95 / P99 / mean

이미지는 합성 솔리드 컬러 (latency 측정 목적이라 컨텐츠 무관).
"""

import argparse
import time

try:
    from PIL import Image
except ImportError as e:
    raise SystemExit("pillow 패키지 미설치 — `uv pip install pillow`") from e

from common import (
    safe_model_name, get_base_dir, get_timestamp, get_results_dir,
    save_json, image_to_data_url, make_client, build_run_config,
    add_thinking_sampling_args,
)


DEFAULT_PROMPT = """다음 한국어 문단을 한 문장으로 요약해 주세요.

인공지능 기술이 빠르게 발전하면서 다양한 분야에서 활용되고 있습니다.
의료, 금융, 교육, 제조업 등 거의 모든 산업에서 AI가 도입되고 있으며,
이는 효율성을 크게 향상시키고 있습니다."""


def make_solid_image(size: int, color=(128, 128, 128)) -> Image.Image:
    return Image.new("RGB", (size, size), color)


def make_messages(prompt: str, images: list) -> list:
    content = [{"type": "text", "text": prompt}]
    for img in images:
        content.append({"type": "image_url", "image_url": {"url": image_to_data_url(img)}})
    return [{"role": "user", "content": content}]


def time_chat_stream(client, model, messages, max_tokens, temperature,
                     top_p=None, top_k=None, seed=None, timeout=None):
    """Stream-based timing: TTFT + total + completion_tokens (서버 usage 우선) + text length.

    vLLM/OpenAI-compat 서버는 stream=True 시 default 로 usage 미반환.
    `stream_options.include_usage=True` 로 마지막 chunk 에 usage 강제 포함 →
    `tokens_per_sec` 정확도 ↑ (chunk count 휴리스틱 회피).

    thinking 모델 대응: 추론 토큰은 delta.reasoning_content 로 따로 스트리밍될 수 있다.
    - ttft       : 종류 불문 *첫 토큰* 까지 (추론 시작이 곧 첫 토큰).
    - ttft_answer: 최종 답(content) *첫 토큰* 까지 (= 추론 종료 후) — thinking 지연 가시화.
    - reasoning_len: 추론 텍스트 길이 (0 이면 비-thinking 또는 인라인).
    """
    t0 = time.perf_counter()
    kwargs = {
        "model": model, "messages": messages,
        "max_tokens": max_tokens, "temperature": temperature,
        "stream": True,
        "stream_options": {"include_usage": True},  # 마지막 chunk 에 usage 포함 강제
    }
    if top_p is not None:
        kwargs["top_p"] = top_p
    if top_k is not None and top_k > 0:
        kwargs["extra_body"] = {"top_k": top_k}
    if seed is not None:
        kwargs["seed"] = seed
    if timeout is not None:
        kwargs["timeout"] = timeout
    stream = client.chat.completions.create(**kwargs)
    ttft = None
    ttft_answer = None
    chunks = 0
    text = ""
    reasoning_text = ""
    usage_completion = None
    for chunk in stream:
        # usage 는 chunk.usage 에 있을 수도, choices=[] 인 trailing chunk 에 있을 수도
        if hasattr(chunk, "usage") and chunk.usage:
            ct = getattr(chunk.usage, "completion_tokens", None)
            if ct is not None:
                usage_completion = ct
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        rdelta = getattr(delta, "reasoning_content", None)
        cdelta = delta.content
        if (cdelta or rdelta) and ttft is None:
            ttft = time.perf_counter() - t0
        if rdelta:
            reasoning_text += rdelta
        if cdelta:
            if ttft_answer is None:
                ttft_answer = time.perf_counter() - t0
            text += cdelta
            chunks += 1
    total = time.perf_counter() - t0
    return {
        "ttft": ttft,
        "ttft_answer": ttft_answer,
        "total": total,
        "chunks": chunks,
        "text_len": len(text),
        "reasoning_len": len(reasoning_text),
        "completion_tokens": usage_completion,
    }


def percentiles(values: list) -> dict:
    vs = [v for v in values if v is not None]
    if not vs:
        return {"p50": None, "p95": None, "p99": None, "mean": None, "n": 0}
    sv = sorted(vs)
    n = len(sv)

    def pct(p: float) -> float:
        if n == 1:
            return sv[0]
        idx = (p / 100.0) * (n - 1)
        lo = int(idx)
        hi = min(lo + 1, n - 1)
        frac = idx - lo
        return sv[lo] * (1 - frac) + sv[hi] * frac

    return {
        "p50": pct(50), "p95": pct(95), "p99": pct(99),
        "mean": sum(sv) / n, "n": n,
    }


def run_condition(client, model, name: str, messages, reps: int, max_tokens: int, temperature: float,
                  top_p=None, top_k=None, seed=None, timeout=None):
    print(f"\n[b4] === {name} ({reps} reps) ===")
    runs = []
    for i in range(reps):
        try:
            r = time_chat_stream(client, model, messages, max_tokens, temperature,
                                 top_p=top_p, top_k=top_k, seed=seed, timeout=timeout)
            r["error"] = None
        except Exception as e:
            r = {"ttft": None, "ttft_answer": None, "total": None, "chunks": 0,
                 "text_len": 0, "reasoning_len": 0, "completion_tokens": None, "error": str(e)}
        runs.append(r)
        if (i + 1) % 10 == 0:
            ok = [x for x in runs if x.get("ttft") is not None]
            if ok:
                ttft_avg = sum(x["ttft"] for x in ok) / len(ok)
                total_avg = sum(x["total"] for x in ok) / len(ok)
                print(f"[b4] {i+1}/{reps} TTFT~{ttft_avg:.3f}s total~{total_avg:.3f}s ok={len(ok)}")

    # tokens/sec: prefer usage.completion_tokens, fallback to chunks
    def tok_per_sec(r):
        ct = r.get("completion_tokens") or r.get("chunks")
        if not ct or not r.get("total"):
            return None
        return ct / r["total"]

    summary = {
        "condition": name,
        "reps": reps,
        "successful": sum(1 for r in runs if r.get("ttft") is not None),
        "failed": sum(1 for r in runs if r.get("error")),
        "ttft": percentiles([r.get("ttft") for r in runs]),
        "ttft_answer": percentiles([r.get("ttft_answer") for r in runs]),
        "total": percentiles([r.get("total") for r in runs]),
        "reasoning_len": percentiles([r.get("reasoning_len") for r in runs]),
        "completion_tokens": percentiles([r.get("completion_tokens") or r.get("chunks") for r in runs]),
        "tokens_per_sec": percentiles([tok_per_sec(r) for r in runs]),
    }
    return summary, runs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", default="http://172.16.1.81:18090/v1")
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--reps", type=int, default=50, help="조건당 반복 횟수")
    # thinking sampling 인자(공통 정의 — common.add_thinking_sampling_args).
    # latency 프로파일이라 max_tokens fallback 만 작게(1024). 나머지는 standard 와 동일.
    add_thinking_sampling_args(parser, max_tokens_fallback="1024")
    parser.add_argument("--prompt", type=str, default=DEFAULT_PROMPT)
    parser.add_argument("--skip-multi-image", action="store_true")
    args = parser.parse_args()

    base_dir = get_base_dir(__file__)
    ts = get_timestamp(base_dir)
    out_dir = get_results_dir(
        base_dir, args.model, ts, "b4_latency_profile",
        category="vision", track="customB",
    )
    print(f"[b4] model={args.model}")
    print(f"[b4] base={base_dir}")
    print(f"[b4] out={out_dir}")

    client = make_client(args.base_url, args.api_key)

    img_256 = make_solid_image(256)
    img_1024 = make_solid_image(1024)
    img_512_a = make_solid_image(512, (200, 100, 100))
    img_512_b = make_solid_image(512, (100, 200, 100))
    img_512_c = make_solid_image(512, (100, 100, 200))

    conditions = [
        ("text_only", make_messages(args.prompt, [])),
        ("image_256px", make_messages(args.prompt, [img_256])),
        ("image_1024px", make_messages(args.prompt, [img_1024])),
    ]
    if not args.skip_multi_image:
        conditions.append((
            "multi_image_3x512px",
            make_messages(args.prompt, [img_512_a, img_512_b, img_512_c]),
        ))

    summaries = []
    runs_by_condition = {}
    for name, messages in conditions:
        s, r = run_condition(
            client, args.model, name, messages,
            args.reps, args.max_tokens, args.temperature,
            top_p=args.top_p, top_k=args.top_k,
            seed=args.seed, timeout=args.timeout,
        )
        summaries.append(s)
        runs_by_condition[name] = r

    final = {
        "benchmark": "B-4 Latency Profile",
        "model": args.model,
        "conditions": summaries,
        "run_config": build_run_config(
            benchmark="B-4 Latency Profile",
            model=args.model,
            base_url=args.base_url,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            top_p=args.top_p,
            top_k=args.top_k,
            seed=args.seed,
            timeout=args.timeout,
            eval_script_path=__file__,
            extra={
                "reps_per_condition": args.reps,
                "prompt": args.prompt,
                "skip_multi_image": args.skip_multi_image,
            },
        ),
    }

    save_json(out_dir / "summary.json", final)
    save_json(out_dir / "runs.json", runs_by_condition)

    print(f"\n[b4] FINAL")
    for s in summaries:
        ttft = s["ttft"]
        total = s["total"]
        tps = s["tokens_per_sec"]
        print(f"  {s['condition']}: ok={s['successful']}/{s['reps']}")
        if ttft.get('p50') is None:
            print(f"    (모든 호출 실패 — runs.json error 확인)")
            continue
        print(f"    TTFT  P50={ttft['p50']:.3f}s P95={ttft['p95']:.3f}s P99={ttft['p99']:.3f}s")
        print(f"    Total P50={total['p50']:.3f}s P95={total['p95']:.3f}s P99={total['p99']:.3f}s")
        if tps.get('p50'):
            print(f"    Tok/s P50={tps['p50']:.1f} P95={tps['p95']:.1f}")


if __name__ == "__main__":
    main()
