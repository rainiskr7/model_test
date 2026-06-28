"""Track B-3 — Structured Output (포맷 준수).

이미지 → JSON / 표 변환 정확도 측정.
- 표 이미지 → JSON 변환 (~30건 권장)
- 영수증/인보이스 → 구조화 추출 (~30건 권장)
- 차트 → 데이터 포인트 추출 (~20건 권장)

데이터: data/structured_output/manifest.json + images/

Manifest 항목 형식:
{
  "id": "table_001",
  "category": "table" | "receipt" | "chart",
  "image": "images/table_001.png",  // manifest.json 기준 상대경로
  "prompt": "이 표를 JSON 객체 배열로 변환하세요. 컬럼명을 키로 사용하고...",
  "expected": {
    "type": "object" | "array",          // 최상위 JSON 타입 기대값
    "required_fields": ["이름", "나이", "합계"],  // 객체일 경우 키, 배열이면 첫 항목의 키
    "min_items": 3,                       // 배열이면 최소 항목 수 (선택)
    "value_checks": [                     // 선택: 특정 필드의 정확 값 검증
      {"path": "$[0].이름", "value": "홍길동"},
      {"path": "$.total", "value": 5000}
    ]
  }
}

메트릭:
- json_parse_rate: 응답을 JSON 으로 파싱 가능한 비율
- schema_pass_rate: 파싱 + required_fields 모두 존재 비율
- value_match_rate: value_checks 평균 일치율
"""

import json
import re
from pathlib import Path

try:
    from PIL import Image
except ImportError as e:
    raise SystemExit("pillow 패키지 미설치 — `uv pip install pillow`") from e

from common import (
    standard_argparser, make_client, chat_with_image,
    get_base_dir, get_timestamp, get_results_dir, save_json,
    safe_model_name, build_run_config, normalize_text, normalize_number,
)


def extract_json(text: str):
    """응답 텍스트에서 JSON 추출 시도. (success, parsed) 반환."""
    if not text:
        return False, None
    s = text.strip()
    # 코드 펜스 제거
    s = re.sub(r"^```(?:json|JSON)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    # 직접 파싱
    try:
        return True, json.loads(s)
    except json.JSONDecodeError:
        pass
    # 객체/배열 패턴 추출 시도
    for pat in (r'\{[\s\S]*\}', r'\[[\s\S]*\]'):
        m = re.search(pat, s)
        if m:
            try:
                return True, json.loads(m.group(0))
            except json.JSONDecodeError:
                continue
    return False, None


def get_first_object(parsed):
    """JSON에서 첫 객체 dict 추출 (배열이면 첫 항목, 객체면 그대로)."""
    if isinstance(parsed, dict):
        return parsed
    if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
        return parsed[0]
    return None


def check_schema(parsed, expected: dict) -> dict:
    """필수 필드 존재 검증."""
    result = {"required_fields_present": False, "missing_fields": [], "type_match": False}
    if parsed is None:
        return result

    expected_type = expected.get("type", "object")
    if expected_type == "array":
        result["type_match"] = isinstance(parsed, list)
        if expected.get("min_items") and isinstance(parsed, list):
            result["min_items_ok"] = len(parsed) >= expected["min_items"]
    else:
        result["type_match"] = isinstance(parsed, dict)

    obj = get_first_object(parsed)
    required = expected.get("required_fields", [])
    if obj is not None and required:
        missing = [f for f in required if f not in obj]
        result["missing_fields"] = missing
        result["required_fields_present"] = len(missing) == 0
    elif not required:
        result["required_fields_present"] = True
    return result


def _resolve_path(parsed, path: str):
    """단순 JSONPath ($, $[0], $.key, $[0].key) 평가."""
    if not path.startswith("$"):
        return None
    cur = parsed
    rest = path[1:]
    # tokenize: .key 또는 [N]
    tokens = re.findall(r'\.([^.\[\]]+)|\[(\d+)\]', rest)
    for key, idx in tokens:
        if key:
            if not isinstance(cur, dict) or key not in cur:
                return None
            cur = cur[key]
        elif idx:
            i = int(idx)
            if not isinstance(cur, list) or i >= len(cur):
                return None
            cur = cur[i]
    return cur


def _match_value(actual, expected, mode: str, tolerance: float) -> bool:
    """Single value match per mode.

    mode:
      - 'exact'         : NFKC normalize + 공백/문장부호 정리 후 lower-case 비교 (str)
      - 'numeric_close' : abs(actual-expected) <= tolerance * |expected|  (default tolerance=0.05 = ±5%)
      - 'substring'     : normalize 후 expected ⊂ actual
      - 'regex'         : actual 가 expected (정규식) 매칭
      - 'list_set'      : 배열 순서·중복 무시 비교 (리스트 to set, 원소는 normalize)
    """
    if mode == "exact":
        if actual == expected:
            return True
        if isinstance(actual, str) and isinstance(expected, str):
            return normalize_text(actual) == normalize_text(expected)
        return False

    if mode == "numeric_close":
        # 단위·쉼표·통화 기호 정리 후 float 변환
        a = normalize_number(actual)
        e = normalize_number(expected)
        if a is None or e is None:
            return False
        if e == 0:
            return abs(a) <= tolerance
        return abs(a - e) / abs(e) <= tolerance

    if mode == "substring":
        if not isinstance(actual, str) or not isinstance(expected, str):
            return False
        return normalize_text(expected) in normalize_text(actual)

    if mode == "regex":
        import re as _re
        if not isinstance(actual, str):
            return False
        try:
            return bool(_re.search(str(expected), actual))
        except _re.error:
            return False

    if mode == "list_set":
        # 배열을 set 으로 변환 후 비교 (순서·중복 무시)
        if not isinstance(actual, list) or not isinstance(expected, list):
            return False
        def _norm_elem(x):
            if isinstance(x, str):
                return normalize_text(x)
            return x
        try:
            return set(map(_norm_elem, actual)) == set(map(_norm_elem, expected))
        except TypeError:
            return False

    return False


def check_values(parsed, value_checks: list) -> dict:
    """value_checks 평균 일치율 (mode 별 매칭 지원).

    각 check 항목은 다음 필드 가짐:
      - path:      JSONPath ($, $[0], $.key, $[0].key)
      - value:     기대값
      - match:     'exact' (default) | 'numeric_close' | 'substring' | 'regex'
      - tolerance: numeric_close 일 때 상대오차 (default 0.05 = ±5%)
    """
    if not value_checks:
        return {"checked": 0, "matched": 0, "match_rate": None, "details": []}
    matched = 0
    details = []
    for chk in value_checks:
        path = chk["path"]
        expected = chk["value"]
        mode = chk.get("match", "exact")
        tol = chk.get("tolerance", 0.05)
        actual = _resolve_path(parsed, path)
        ok = _match_value(actual, expected, mode, tol)
        if ok:
            matched += 1
        details.append({"path": path, "expected": expected, "mode": mode, "actual": actual, "matched": ok})
    return {
        "checked": len(value_checks),
        "matched": matched,
        "match_rate": matched / len(value_checks),
        "details": details,
    }


def main():
    parser = standard_argparser()
    parser.add_argument(
        "--manifest", type=str, default=None,
        help="Manifest JSON 경로 (default: <multimodal>/data/structured_output/manifest.json)",
    )
    args = parser.parse_args()

    bench_root = Path(__file__).resolve().parent.parent  # multimodal/
    manifest_path = Path(args.manifest) if args.manifest \
        else bench_root / "data" / "structured_output" / "manifest.json"

    if not manifest_path.exists():
        raise SystemExit(
            f"Manifest 미존재: {manifest_path}\n"
            "샘플 manifest.json 형식은 b3_structured_output.py docstring 참조."
        )

    items = json.loads(manifest_path.read_text(encoding="utf-8"))
    if args.limit:
        items = items[:args.limit]

    base_dir = get_base_dir(__file__)
    ts = get_timestamp(base_dir)
    out_dir = get_results_dir(
        base_dir, args.model, ts, "b3_structured_output",
        category="vision", track="customB",
    )

    print(f"[b3] model={args.model}")
    print(f"[b3] manifest={manifest_path} ({len(items)} items)")
    print(f"[b3] out={out_dir}")

    client = make_client(args.base_url, args.api_key)

    results = []
    parse_ok = 0
    schema_ok = 0
    value_match_total = 0.0
    value_match_count = 0
    by_category: dict[str, dict[str, int]] = {}

    for i, item in enumerate(items):
        img_path = (manifest_path.parent / item["image"]).resolve()
        if not img_path.exists():
            print(f"[b3] WARN: 이미지 없음 {img_path}")
            continue

        try:
            img = Image.open(img_path)
            response = chat_with_image(
                client, args.model, item["prompt"], img,
                max_tokens=args.max_tokens, temperature=args.temperature,
                seed=args.seed, timeout=args.timeout,
                retry_max=args.retry_max, retry_backoff=args.retry_backoff,
            )
            err = None
        except Exception as e:
            response = ""
            err = str(e)

        parsed_ok, parsed = extract_json(response)
        if parsed_ok:
            parse_ok += 1

        expected = item.get("expected", {})
        schema = check_schema(parsed, expected)
        if schema["required_fields_present"] and schema.get("type_match", False):
            schema_ok += 1

        value_check = check_values(parsed, expected.get("value_checks", []))
        if value_check["match_rate"] is not None:
            value_match_total += value_check["match_rate"]
            value_match_count += 1

        cat = item.get("category", "unknown")
        bc = by_category.setdefault(cat, {"total": 0, "parse_ok": 0, "schema_ok": 0})
        bc["total"] += 1
        if parsed_ok:
            bc["parse_ok"] += 1
        if schema["required_fields_present"] and schema.get("type_match", False):
            bc["schema_ok"] += 1

        results.append({
            "id": item["id"],
            "category": cat,
            "response": response,
            "parsed": parsed,
            "parse_ok": parsed_ok,
            "schema_check": schema,
            "value_check": value_check,
            "error": err,
        })

        print(f"[b3] {i+1}/{len(items)} {cat} parse={parsed_ok} schema={schema['required_fields_present']}")

    n = len(results)
    summary = {
        "benchmark": "B-3 Structured Output",
        "model": args.model,
        "total": n,
        "json_parse_rate": (parse_ok / n) if n else 0.0,
        "schema_pass_rate": (schema_ok / n) if n else 0.0,
        "value_match_rate": (value_match_total / value_match_count) if value_match_count else None,
        "by_category": {
            cat: {
                "total": stats["total"],
                "parse_rate": stats["parse_ok"] / stats["total"] if stats["total"] else 0.0,
                "schema_pass_rate": stats["schema_ok"] / stats["total"] if stats["total"] else 0.0,
            }
            for cat, stats in by_category.items()
        },
        "run_config": build_run_config(
            benchmark="B-3 Structured Output",
            model=args.model,
            base_url=args.base_url,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            seed=args.seed,
            timeout=args.timeout,
            retry_max=args.retry_max,
            retry_backoff=args.retry_backoff,
            eval_script_path=__file__,
            extra={
                "manifest": str(manifest_path),
                "manifest_size": len(items),
                "limit": args.limit,
            },
        ),
    }

    save_json(out_dir / "results.json", results)
    save_json(out_dir / "summary.json", summary)

    print(f"\n[b3] FINAL parse={summary['json_parse_rate']:.3f} "
          f"schema={summary['schema_pass_rate']:.3f} "
          f"value={summary['value_match_rate']}")


if __name__ == "__main__":
    main()
