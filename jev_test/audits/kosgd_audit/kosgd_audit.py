#!/usr/bin/env python3
"""SPEC.md의 결정적 KoSGD 재구성 감사. 입력은 읽기 전용이다."""

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import random
import sys

# 외부 설치 패키지에도 바이트코드 파일을 쓰지 않는다.
sys.dont_write_bytecode = True
from tokenizers import Tokenizer


DATA_ROOT = Path(
    "/private/tmp/claude-501/-Users-rainis-Desktop-workspace-source-model-test/"
    "aa7fe33a-3991-4573-b7d5-6bce4ff44cd9/scratchpad"
)
DEFAULT_TOKENIZER = "/Users/rainis/Desktop/workplace/models/Qwen_Qwen3.8_27B/tokenizer.json"
SEED = 20261012
SAMPLE_SIZE = 3000
ACT_MAP = {
    "INFORM": "INFORM",
    "REQUEST": "REQUEST",
    "AFFIRM": "AFFIRM",
    "NEGATE": "NEGATE",
    "REQUEST_ALTS": "REQUEST_ALTS",
    "SELECT": "SELECT",
    "GOODBYE": "종료/감사",
    "THANK_YOU": "종료/감사",
}
ALLOWED = set(ACT_MAP)
RULES = [
    'R1 > 10% → "R1 FAIL: KoSGD 문항 재설계"',
    '(e) >8192 비율 > 5% → "R2 FAIL: 잘림/거부 비대칭 먼저 해소"',
    '(f) < 90% → "R3 FAIL: 영어 짝 비교 제외"',
    "각각 아니면 PASS",
]


def read_json(path):
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def load_dialogues(directory):
    files = sorted(directory.glob("dialogues_*.json"))
    if not files:
        raise ValueError(f"대화 파일이 없습니다: {directory}")
    dialogues = []
    seen = set()
    for path in files:
        items = read_json(path)
        if not isinstance(items, list):
            raise ValueError(f"대화 리스트가 아닙니다: {path}")
        for item in items:
            dialogue_id = item["dialogue_id"]
            if dialogue_id in seen:
                raise ValueError(f"중복 dialogue_id: {dialogue_id} ({path})")
            seen.add(dialogue_id)
            dialogues.append(item)
    return files, dialogues


def fraction(numerator, denominator):
    return {
        "numerator": numerator,
        "denominator": denominator,
        "ratio": numerator / denominator if denominator else None,
    }


def percentile(sorted_values, p):
    """최근접 순위법: 정렬값의 ceil(p * n)번째 값 (1부터 시작)."""
    if not sorted_values:
        return None
    return sorted_values[max(0, math.ceil(p * len(sorted_values)) - 1)]


def audit(args):
    ko_files, dialogues = load_dialogues(args.kosgd)
    en_files, english = load_dialogues(args.sgd_en)
    english_turn_counts = {d["dialogue_id"]: len(d["turns"]) for d in english}
    schema_path = args.kosgd / "extended_schema.json"
    schemas = read_json(schema_path)
    schema_by_service = {s["service_name"]: s for s in schemas}
    if len(schema_by_service) != len(schemas):
        raise ValueError("스키마에 중복 service_name이 있습니다")
    tokenizer = Tokenizer.from_file(str(args.tokenizer))
    tokenizer.no_truncation()
    tokenizer.no_padding()

    rng = random.Random(SEED)
    dialogues.sort(key=lambda d: d["dialogue_id"])
    sampled = sorted(rng.sample(dialogues, SAMPLE_SIZE), key=lambda d: d["dialogue_id"])
    counts = Counter()
    act_counts = Counter()
    outside_turn_counts = Counter()
    token_lengths = []
    skipped = []
    selected_turns = []
    for dialogue in sampled:
        dialogue_id = dialogue["dialogue_id"]
        # 영어 짝 비교는 USER 턴을 건너뛰더라도 표본 3000개 전체가 분모다.
        if dialogue_id in english_turn_counts:
            counts["matched_ids"] += 1
            if len(dialogue["turns"]) == english_turn_counts[dialogue_id]:
                counts["matched_turn_counts"] += 1
        user_indices = [
            i for i, turn in enumerate(dialogue["turns"]) if turn["speaker"] == "USER"
        ]
        if not user_indices:
            skipped.append(dialogue_id)
            continue
        turn_index = rng.choice(user_indices)
        turn = dialogue["turns"][turn_index]
        frames = turn["frames"]
        acts = [action["act"] for frame in frames for action in frame["actions"]]
        act_counts.update(acts)
        outside_acts = set(acts) - ALLOWED
        outside_turn_counts.update(outside_acts)
        mapped = {ACT_MAP[act] for act in acts if act in ALLOWED}
        multi_frame = len(frames) > 1
        empty_mapped = not mapped
        counts["multi_frame"] += multi_frame
        counts["none_intent"] += any(
            (frame.get("state") or {}).get("active_intent") == "NONE" for frame in frames
        )
        counts["missing_state"] += any(frame.get("state") is None for frame in frames)
        counts["outside_allowed"] += bool(outside_acts)
        counts["empty_mapped"] += empty_mapped
        counts["r1_union"] += multi_frame or bool(outside_acts) or empty_mapped

        text = json.dumps(
            [schema_by_service[service] for service in dialogue["services"]],
            ensure_ascii=False,
        ) + "\n" + "\n".join(
            f'{t["speaker"]}: {t["utterance"]}'
            for t in dialogue["turns"][:turn_index + 1]
        )
        length = len(tokenizer.encode(text).ids)
        token_lengths.append(length)
        selected_turns.append({"dialogue_id": dialogue_id, "turn_index": turn_index})

    denominator = len(token_lengths)
    metrics = {
        name: fraction(counts[name], denominator)
        for name in (
            "multi_frame", "none_intent", "missing_state", "outside_allowed",
            "empty_mapped", "r1_union",
        )
    }
    metrics["tokens_gt_8192"] = fraction(sum(n > 8192 for n in token_lengths), denominator)
    metrics["tokens_gt_16384"] = fraction(sum(n > 16384 for n in token_lengths), denominator)
    metrics["english_id_match"] = fraction(counts["matched_ids"], len(sampled))
    metrics["english_turn_count_match_given_id"] = fraction(
        counts["matched_turn_counts"], counts["matched_ids"]
    )
    sorted_lengths = sorted(token_lengths)
    verdicts = {
        "R1": ("R1 FAIL: KoSGD 문항 재설계" if counts["r1_union"] * 10 > denominator
               else "R1 PASS") if denominator else "R1 N/A: 고른 턴 없음",
        "R2": ("R2 FAIL: 잘림/거부 비대칭 먼저 해소"
               if metrics["tokens_gt_8192"]["numerator"] * 20 > denominator
               else "R2 PASS") if denominator else "R2 N/A: 고른 턴 없음",
        "R3": ("R3 FAIL: 영어 짝 비교 제외"
               if counts["matched_ids"] * 10 < len(sampled) * 9 else "R3 PASS"),
    }
    return {
        "inputs": {
            "kosgd": {"path": str(args.kosgd), "dialogue_file_count": len(ko_files),
                      "dialogue_count": len(dialogues), "schema_file_count": 1,
                      "schema_service_count": len(schemas)},
            "sgd_en": {"path": str(args.sgd_en), "dialogue_file_count": len(en_files),
                       "dialogue_count": len(english)},
            "tokenizer": {"path": str(args.tokenizer), "file_count": 1},
            "total_file_count": len(ko_files) + len(en_files) + 2,
        },
        "sampling": {"seed": SEED, "sampled_dialogues": len(sampled),
                     "selected_turn_count": denominator, "skipped_dialogue_count": len(skipped),
                     "skipped_dialogue_ids": skipped},
        "metrics": metrics,
        "act_frequencies": dict(sorted(act_counts.items())),
        "outside_act_frequencies": {
            act: act_counts[act] for act in sorted(outside_turn_counts)
        },
        "outside_act_turn_counts": {
            act: fraction(count, denominator) for act, count in sorted(outside_turn_counts.items())
        },
        "allowed_acts": sorted(ALLOWED),
        "act_mapping": ACT_MAP,
        "token_lengths": {"count": denominator, "percentile_method": "nearest_rank",
                          "p50": percentile(sorted_lengths, 0.50),
                          "p95": percentile(sorted_lengths, 0.95),
                          "max": max(sorted_lengths) if sorted_lengths else None},
        "rules": RULES,
        "verdicts": verdicts,
        "selected_turns": selected_turns,
    }


def format_fraction(value):
    ratio = value["ratio"]
    percent = f"{ratio:.4%}" if ratio is not None else "N/A"
    return f'{value["numerator"]}/{value["denominator"]} ({percent})'


def render_report(result):
    lines = ["KoSGD 재구성 감사"]
    for key in ("kosgd", "sgd_en"):
        item = result["inputs"][key]
        lines.append(f'{key}: {item["path"]} — 대화 파일 {item["dialogue_file_count"]}개, '
                     f'대화 {item["dialogue_count"]}개')
    lines.append(f'KoSGD 스키마: extended_schema.json 1개, '
                 f'{result["inputs"]["kosgd"]["schema_service_count"]}개 서비스')
    lines.append(f'토크나이저: {result["inputs"]["tokenizer"]["path"]} (1개 파일)')
    lines.append(f'읽은 입력 파일 합계: {result["inputs"]["total_file_count"]}')
    sample = result["sampling"]
    lines.append(f'표본: seed={sample["seed"]}, 대화 {sample["sampled_dialogues"]}, '
                 f'고른 턴 {sample["selected_turn_count"]}, 건너뛴 대화 {sample["skipped_dialogue_count"]}')
    lines.append(f'건너뛴 dialogue_id: {sample["skipped_dialogue_ids"]}')
    labels = {
        "multi_frame": "(a) 다중 frame",
        "none_intent": '(b) 어떤 frame의 active_intent == "NONE"',
        "missing_state": "(b) 어떤 frame의 state 없음",
        "outside_allowed": "(c) ALLOWED 밖 act가 있는 턴",
        "empty_mapped": "(d) 7항목 매핑 집합이 빈 턴",
        "tokens_gt_8192": "(e) 입력 토큰 >8192",
        "tokens_gt_16384": "(e) 입력 토큰 >16384",
        "english_id_match": "(f) 영어 test dialogue_id 일치",
        "english_turn_count_match_given_id": "(f) ID 일치 대화 중 턴 수 일치",
        "r1_union": "R1: (a) ∪ (c) ∪ (d)",
    }
    lines.append("\n지표 (분자/분모, 비율):")
    for key, label in labels.items():
        lines.append(f'  {label}: {format_fraction(result["metrics"][key])}')
    lengths = result["token_lengths"]
    lines.append(f'  (e) 토큰 p50={lengths["p50"]}, p95={lengths["p95"]}, '
                 f'max={lengths["max"]} (최근접 순위법, 절단/패딩 없음)')
    lines.append("\n전체 act 빈도표 (모든 frame의 action 발생 횟수):")
    for act, count in result["act_frequencies"].items():
        lines.append(f"  {act}: {count}")
    lines.append("\nALLOWED 밖 act별 발생 횟수 및 해당 act를 가진 턴 비율:")
    for act, value in result["outside_act_turn_counts"].items():
        lines.append(f'  {act}: 발생 {result["outside_act_frequencies"][act]}, '
                     f'턴 {format_fraction(value)}')
    if not result["outside_act_turn_counts"]:
        lines.append("  없음")
    lines.append("\n7항목 매핑: " + json.dumps(result["act_mapping"], ensure_ascii=False))
    lines.append("\n사전 고정 판정 기준:")
    lines.extend(result["rules"])
    lines.append("\n판정:")
    lines.extend(result["verdicts"].values())
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kosgd", type=Path, default=DATA_ROOT / "data_kosgd")
    parser.add_argument("--sgd-en", type=Path, default=DATA_ROOT / "data_sgd_en")
    parser.add_argument("--tokenizer", type=Path, default=Path(DEFAULT_TOKENIZER))
    result = audit(parser.parse_args())
    report = render_report(result)
    result["report_text"] = report
    output = Path(__file__).resolve().parent / "audit_result.json"
    with output.open("w", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(report)
    # 감사 FAIL 판정도 정상 실행이므로 종료코드 0을 유지한다.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
