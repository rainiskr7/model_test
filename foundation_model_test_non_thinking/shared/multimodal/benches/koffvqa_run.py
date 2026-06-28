"""KOFFVQA 자체 runner — OpenAI-compat API 사용.

KOFFVQA 의 generate.py 는 모델명 hardcoded 라 외부 모델 거부.
본 runner 는 KOFFVQA 데이터셋만 활용, 응답 생성은 OpenAI-compat API 로 직접 호출.

데이터: data/KOFFVQA/data/KOFFVQA.tsv (없으면 HF 에서 자동 다운로드)
컬럼: index, image (base64), question, answer (rubric), category, l2-category

출력:
- results/<model>/<ts>/vision/multimodal/koffvqa/responses.xlsx (KOFFVQA evaluate.py 호환)
- results/<model>/<ts>/vision/multimodal/koffvqa/results.json (raw)
- results/<model>/<ts>/vision/multimodal/koffvqa/summary.json (메타)

Judge 단계는 별도:
- (a) KOFFVQA 의 evaluate.py: cd data/KOFFVQA && python evaluate.py --predfile <responses.xlsx>
- (b) 우리 koffvqa_api_judge.py: 외부 OpenAI-compat judge
"""

import base64
import io
import json
from pathlib import Path

try:
    import pandas as pd
    from PIL import Image
    import requests
except ImportError as e:
    raise SystemExit("의존성 미설치 — `pip install pandas pillow requests openpyxl`") from e

from common import (
    standard_argparser, make_client, chat_with_image,
    get_base_dir, get_timestamp, get_results_dir, save_json,
    safe_model_name, build_run_config,
)


KOFFVQA_TSV_URL = "https://huggingface.co/datasets/maum-ai/KOFFVQA_Data/resolve/main/data/KOFFVQA.tsv"


def download_tsv(target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"[koffvqa] downloading tsv → {target}")
    resp = requests.get(KOFFVQA_TSV_URL, timeout=120)
    resp.raise_for_status()
    target.write_bytes(resp.content)


def img_decode(encoded: str) -> Image.Image:
    """KOFFVQA 의 base64 image 디코딩."""
    with io.BytesIO(base64.b64decode(encoded)) as buf:
        img = Image.open(buf)
        img.load()
    return img


def main():
    parser = standard_argparser()
    parser.add_argument(
        "--data", type=str, default=None,
        help="KOFFVQA tsv 경로 (default: <BASE>/data/KOFFVQA/data/KOFFVQA.tsv)",
    )
    parser.add_argument(
        "--no-resume", action="store_true",
        help="기존 out_dir/results.json 무시하고 처음부터 (기본: 유효분 재사용 + 에러/누락만 재시도)",
    )
    args = parser.parse_args()

    base_dir = get_base_dir(__file__)
    ts = get_timestamp(base_dir)
    out_dir = get_results_dir(base_dir, args.model, ts, "koffvqa")

    print(f"[koffvqa] model={args.model}")
    print(f"[koffvqa] base={base_dir}")
    print(f"[koffvqa] out={out_dir}")

    # 1) 데이터 로드 (없으면 다운로드)
    tsv_path = Path(args.data) if args.data else base_dir / "data" / "KOFFVQA" / "data" / "KOFFVQA.tsv"
    if not tsv_path.exists():
        download_tsv(tsv_path)
    bench = pd.read_csv(tsv_path, sep="\t")
    print(f"[koffvqa] loaded {len(bench)} samples, columns={list(bench.columns)}")

    if args.limit:
        bench = bench.head(args.limit)

    client = make_client(args.base_url, args.api_key)

    # Resume: 같은 out_dir 의 기존 results.json 에서 유효(에러 없음 + 비어있지 않은 prediction)
    # 항목은 재사용하고, 에러/누락 항목만 다시 호출한다. (kreta infer_gpt.py 와 동일한 정책)
    # out_dir 는 EVAL_TIMESTAMP 로 스코프되므로, 새 타임스탬프면 빈 dict → 전량 신규 실행.
    # --no-resume 로 끄면 항상 처음부터.
    done = {}
    results_path = out_dir / "results.json"
    if not args.no_resume and results_path.exists():
        try:
            prev = json.loads(results_path.read_text(encoding="utf-8"))
            for r in prev:
                pred = r.get("prediction")
                if r.get("error") is None and isinstance(pred, str) and pred.strip() != "":
                    done[str(r.get("index"))] = r
        except Exception as e:
            print(f"[koffvqa] 기존 results.json 읽기 실패 → 처음부터: {e}")
            done = {}
        print(f"[koffvqa] resume: {len(done)}건 재사용, 나머지 {len(bench) - len(done)}건 재시도")

    results = []
    predictions = []
    retried = 0
    for i, row in bench.iterrows():
        idx = str(row["index"])
        if idx in done:
            r = done[idx]
            results.append(r)
            predictions.append(r.get("prediction", ""))
            continue

        question = str(row["question"]) if pd.notna(row["question"]) else ""
        encoded = row["image"]
        try:
            img = img_decode(encoded)
            response = chat_with_image(
                client, args.model, question, img,
                max_tokens=args.max_tokens, temperature=args.temperature,
                seed=args.seed, timeout=args.timeout,
                retry_max=args.retry_max, retry_backoff=args.retry_backoff,
            )
            err = None
        except Exception as e:
            response = ""
            err = str(e)

        predictions.append(response)
        results.append({
            "index": idx,
            "category": str(row.get("category", "")),
            "l2_category": str(row.get("l2-category", "")),
            "question": question,
            "rubric": str(row.get("answer", "")),
            "prediction": response,
            "error": err,
        })

        retried += 1
        if retried % 25 == 0:
            print(f"[koffvqa] 재시도/신규 {retried}건 처리")

    # 2) KOFFVQA evaluate.py 호환 xlsx 저장 (image 컬럼 제거 + prediction 추가)
    out_df = bench.drop(columns=["image"]).copy()
    out_df["prediction"] = predictions
    xlsx_path = out_dir / f"{safe_model_name(args.model)}_gen.xlsx"
    out_df.to_excel(xlsx_path, index=False, engine="openpyxl")
    print(f"[koffvqa] saved xlsx → {xlsx_path}")

    # 3) raw results.json + summary.json
    save_json(out_dir / "results.json", results)

    summary = {
        "benchmark": "KOFFVQA (response generation)",
        "model": args.model,
        "total": len(results),
        "successful": sum(1 for r in results if not r.get("error")),
        "failed": sum(1 for r in results if r.get("error")),
        "predictions_xlsx": str(xlsx_path),
        "judge_step": "별도 — koffvqa_api_judge.py 또는 KOFFVQA evaluate.py 로 채점 필요",
        "run_config": build_run_config(
            benchmark="KOFFVQA-response-gen",
            model=args.model,
            base_url=args.base_url,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            seed=args.seed,
            timeout=args.timeout,
            retry_max=args.retry_max,
            retry_backoff=args.retry_backoff,
            dataset_id="maum-ai/KOFFVQA_Data",
            repo_dir=base_dir / "data" / "KOFFVQA",
            eval_script_path=__file__,
            extra={"limit": args.limit, "tsv_path": str(tsv_path)},
        ),
    }
    save_json(out_dir / "summary.json", summary)

    print(f"\n[koffvqa] FINAL {summary['successful']}/{summary['total']} 응답 생성 완료")
    print(f"[koffvqa] judge 채점 필요: koffvqa_api_judge.py --predfile {xlsx_path}")


if __name__ == "__main__":
    main()
