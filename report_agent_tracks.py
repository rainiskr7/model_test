#!/usr/bin/env python3
"""functionchat / taubench 산출물에서 **발행 가능한 수치만** 보고한다.

이 도구가 존재하는 이유: AGENT_TRACK_CLOSEOUT.md 에 "인용 금지" 를 적어두는 것만으로는
부족하다. 문서는 무시할 수 있다 — 실제로 2026-08-23 에 게이트가 거부한
gemma telecom 0.4615 를 요약 파일만 보고 최종 수치로 여러 번 인용했다.

그래서 규칙을 코드로 옮긴다.

  - publish_status.publishable != true 인 런은 **점수를 출력하지 않는다.**
    REJECTED 로 표시하고 사유를 적는다.
  - 판정 축은 인간 검증 전까지 항상 PROVISIONAL 딱지를 붙인다.
  - 분자/분모를 함께 낸다. 반올림된 점수만으로는 표본 크기가 사라진다.
  - --strict 는 거부된 런이 하나라도 있으면 exit 1 한다 (CI 용).

측정값을 이 스크립트에 하드코딩하지 않는다. 전부 산출물에서 읽는다.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# 판정 축이 provisional 인 조건. 산출물의 judge.human_validation 이 이 값이면
# 아무리 점수가 좋아도 확정 수치로 내지 않는다.
UNVALIDATED = "not performed"


def load(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def fraction(num: Optional[int], den: Optional[int]) -> str:
    if not den:
        return "-"
    return f"{num}/{den} = {num/den:.4f}"


def collect(base: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for summary_path in sorted(base.glob("results/*/*/language/*/summary.json")):
        track = summary_path.parent.name
        # taubench 는 report_taubench_tracks.py 가 다룬다. 한 트랙을 두 스크립트가
        # 서로 다른 규칙으로 보고하면 반드시 어긋난다 — 전용 계층은 사용자
        # 시뮬레이터 프로토콜 고정 여부, 공식 split 커버리지, 코호트 분리를 보는데
        # 여기서는 그중 아무것도 보지 않는다. 실측: 사용자 시뮬레이터가 달라 0.475 와
        # 0.900 으로 갈리는 런들이 여기서는 한 표에 섞였다.
        if track != "functionchat":
            continue
        d = load(summary_path)
        if d is None:
            continue
        status = d.get("publish_status") or {}
        publishable = bool(status.get("publishable"))
        # 게이트 기록이 없다 = 채점기가 현재 계약으로 이 산출물을 받아들이지 못한다는 뜻이다
        # (재채점하면 실패한다). 발행 가능으로 볼 수 없다.
        if not status:
            publishable = False
        run = summary_path.parent.parent.parent
        row = {
            "model": run.parent.name,
            "run": run.name,
            "track": track,
            "publishable": publishable,
            "failures": status.get("failures") or [],
            "has_gate_record": bool(status),
        }
        if track == "functionchat":
            o = d.get("overall") or {}
            row["axes"] = [("exact", o.get("passed"), o.get("measured"), False)]
            judge = load(summary_path.parent / "judge.json")
            if judge:
                jo = judge.get("overall") or {}
                unvalidated = (judge.get("judge") or {}).get("human_validation") == UNVALIDATED
                row["axes"].append(("judged", jo.get("passed"), jo.get("judged"), unvalidated))
                row["judge_errors"] = jo.get("judge_errors")
                row["unstable"] = jo.get("unstable")
                # 판정 점수는 판정기가 만든 값이다. 어느 엔드포인트가 무엇을 서빙해
                # 어떤 루브릭으로 냈는지 산출물에 없으면, 그 점수는 재확인할 수 없다.
                judge_meta = judge.get("judge") or {}
                row["judge_provenance_missing"] = [
                    field
                    for field in ("endpoint", "served_identity", "rubric_sha256")
                    if not judge_meta.get(field)
                ]
        else:
            row["axes"] = []
            for domain, entry in sorted((d.get("by_domain") or {}).items()):
                if not isinstance(entry, dict) or entry.get("status") != "measured":
                    continue
                # provisional 을 False 로 하드코딩하지 않는다. 지금 tau2 는 전부
                # 프로그램 채점이라 False 가 맞지만, 나중에 판정기를 붙이면 판정
                # 조건부 결과가 "확정" 으로 찍힌다. 산출물이 판정 사용을 밝히면
                # 자동으로 provisional 이 되도록 둔다.
                judge_used = bool(entry.get("judge") or entry.get("nl_judge_model"))
                row["axes"].append(
                    (domain, entry.get("passed"), entry.get("measured"), judge_used)
                )
                row["runnable"] = entry.get("runnable_tasks")
        rows.append(row)
    return rows


def collect_claims(base: Path) -> Dict[str, Any]:
    """모델별 클레임 자격과 발행 가능한 우열 주장.

    1급 관측 대상은 스칼라 점수가 아니라 **항목별 통과 벡터**다. 실측: 어떤
    모델은 통과 건수가 5런 내내 553 으로 같아 표본표준편차가 0 이었는데 통과
    항목 10개가 뒤집혔다. 건수만 보면 완벽한 재현으로 읽힌다.
    """

    scoring_dir = base / "shared" / "functionchat" / "scoring"
    module_path = scoring_dir / "repro.py"
    if not module_path.exists():
        return {}
    spec = importlib.util.spec_from_file_location("functionchat_repro_claims", module_path)
    if spec is None or spec.loader is None:
        return {}
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(scoring_dir))
    sys.path.insert(0, str(base / "shared"))
    try:
        spec.loader.exec_module(module)
        from publish.claims import comparable, credential
    except Exception as exc:
        print(f"[report] 클레임 계층을 읽지 못했다: {type(exc).__name__}: {exc}", file=sys.stderr)
        return {}
    finally:
        for path in (str(scoring_dir), str(base / "shared")):
            try:
                sys.path.remove(path)
            except ValueError:
                pass

    grouped: Dict[Any, List[Dict[str, Any]]] = {}
    for run_dir in sorted(base.glob("results/*/*/language/functionchat")):
        loaded = module.load_run(run_dir)
        if loaded:
            grouped.setdefault(module.cohort_key(loaded), []).append(loaded)

    creds = {
        key: credential([{"run_id": r["session"], "items": r["items"]} for r in members])
        for key, members in sorted(grouped.items())
    }
    verified = [(key, cred) for key, cred in creds.items()
                if cred["claim_class"] == "repeatability_observed"]
    verdicts = []
    for i in range(len(verified)):
        for j in range(i + 1, len(verified)):
            (ka, ca), (kb, cb) = verified[i], verified[j]
            verdicts.append((ka[2], kb[2], comparable(ca, cb)))
    judge_credentials = []
    for run_dir in sorted(base.glob("results/*/*/language/functionchat")):
        judge = load(run_dir / "judge.json")
        if not judge:
            continue
        judge_credentials.append({
            "model": run_dir.parents[2].name,
            "run": run_dir.parents[1].name,
            "credential": module.judge_credential(judge.get("records") or []),
            "provisional": (judge.get("judge") or {}).get("human_validation") == UNVALIDATED,
        })
    return {
        "credentials": creds,
        "verdicts": verdicts,
        "judge_credentials": judge_credentials,
    }


def render_claims(claims: Dict[str, Any]) -> List[str]:
    if not claims:
        return []
    out = ["## 클레임 등급", ""]
    out.append(
        "**1회 실행 숫자는 순위표에 올리지 않는다.** 저장·표시·역사 인용은 되지만 "
        "우열 주장의 근거는 아니다. 반복 3회 이상이어야 반복성을 관측했다고 말한다."
    )
    out.append("")
    out.append("### exact-match 축")
    out.append("")
    for key, cred in claims["credentials"].items():
        model, version = key[2], key[0]
        if cred["claim_class"] != "repeatability_observed":
            out.append(f"- `{model}` (`{version}`) — `{cred['claim_class']}` (k={cred['k']}) · {cred['reason']}")
            continue
        lo, hi = cred["instability_envelope"]
        out.append(
            f"- `{model}` (`{version}`) — `{cred['claim_class']}` (k={cred['k']}) · "
            f"다수결 {cred['majority_passed']}/{cred['measured_items']} · "
            f"건수범위 {cred['count_range']} · 뒤집힘 {len(cred['unstable_items'])}건 · "
            f"불안정 예산 {lo}–{hi}"
        )
    out.append("")
    judge_credentials = claims.get("judge_credentials") or []
    if judge_credentials:
        out.append("### judge 축 — 런 내부 3표")
        out.append("")
        out.append(
            "판정 축은 exact-match 축과 합치지 않는다. 이 예산은 반복 실행 간 뒤집힘이 아니라, "
            "같은 런에서 항목별 3표가 갈린 수로 만든 판정기 내부 불안정이다."
        )
        out.append("")
        for entry in judge_credentials:
            cred = entry["credential"]
            lo, hi = cred["instability_envelope"]
            provisional = " · **PROVISIONAL — 판정기 기준, 인간 검증 없음**" if entry["provisional"] else ""
            out.append(
                f"- `{entry['model']}` / `{entry['run']}` — `{cred['claim_class']}` "
                f"(런 내부 3표, k={cred['k']}) · 다수결 {cred['majority_passed']}/{cred['measured_items']} · "
                f"표 갈림 {len(cred['unstable_items'])}건 · 불안정 예산 {lo}–{hi}{provisional}"
            )
        out.append("")
    out.append("### 발행 가능한 우열 주장")
    out.append("")
    if not claims["verdicts"]:
        out.append("- 반복 관측된 코호트가 2개 미만이라 비교할 대상이 없다.")
    for left, right, verdict in claims["verdicts"]:
        if verdict["comparable"]:
            winner = left if verdict["winner"] == "left" else right
            out.append(f"- `{winner}` 우세 — {verdict['reason']}")
        else:
            out.append(f"- `{left}` vs `{right}` — **발행 불가**: {verdict['reason']}")
    out.append("")
    out.append(
        "> 가설검정이 아니다. 신뢰구간도 p-value 도 아니다. **관측된 불안정으로 "
        "설명이 끝나는 우열 주장을 거절하는 규칙**일 뿐이며, 거절되지 않았다고 "
        "'유의하다'는 뜻이 아니고 거절됐다고 '두 모델이 같다'는 뜻도 아니다."
    )
    out.append("")
    return out


def collect_functionchat_reproducibility(base: Path) -> List[Dict[str, Any]]:
    """functionchat 반복 실행의 통과 항목 집합을 대조한다.

    이 저장소에는 반복 런이 이미 있었는데(gemma 3개, qwen 5개) 아무도 산포를 내지
    않았다. 대표 런 표만으로는 그 사실이 보이지 않는다 — 대표는 항상 커버리지가
    가장 넓은 런 하나이고, 반복은 다른 scoring_version 에 있다.
    """

    scoring_dir = base / "shared" / "functionchat" / "scoring"
    module_path = scoring_dir / "repro.py"
    if not module_path.exists():
        return []
    spec = importlib.util.spec_from_file_location("functionchat_repro", module_path)
    if spec is None or spec.loader is None:
        return []
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(scoring_dir))
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        # 재현성은 부가 정보다. 그것을 못 읽는다고 발행 가능한 수치 보고 전체를
        # 막으면, 도구를 쓰지 않고 summary.json 을 직접 읽는 경로로 되돌아간다 —
        # 이 스크립트가 존재하는 이유가 바로 그 경로를 막는 것이다.
        print(f"[report] 재현성 계층을 읽지 못했다: {type(exc).__name__}: {exc}", file=sys.stderr)
        return []
    finally:
        try:
            sys.path.remove(str(scoring_dir))
        except ValueError:
            pass
        # 임시로 올린 경로에서 끌어온 모듈을 남기면 나중의 평범한 import 를 가린다.
        for name in ("exact_match", "score_run"):
            loaded = sys.modules.get(name)
            if loaded is not None and getattr(loaded, "__file__", "").startswith(str(scoring_dir)):
                del sys.modules[name]
    runs = []
    for run_dir in sorted(base.glob("results/*/*/language/functionchat")):
        loaded = module.load_run(run_dir)
        if loaded:
            runs.append(loaded)
    return module.reproducibility_report(runs)


def render_markdown(
    rows: List[Dict[str, Any]],
    repro_report: Optional[List[Dict[str, Any]]] = None,
    claims: Optional[Dict[str, Any]] = None,
) -> str:
    """명령을 돌리지 않고도 읽을 수 있는 보고서를 만든다.

    수치는 전부 산출물에서 읽는다. 이 함수에 숫자를 적어 넣지 않는다 — 그렇게 하면
    산출물이 바뀌어도 보고서가 따라가지 않아 거짓이 된다.
    """
    published = [r for r in rows if r["publishable"]]
    rejected = [r for r in rows if not r["publishable"]]

    out: List[str] = []
    out.append("# agent 트랙 결과")
    out.append("")
    out.append(
        "이 파일은 `report_agent_tracks.py` 가 산출물에서 생성한다. "
        "손으로 고치지 말 것 — 다시 생성하면 덮어써진다."
    )
    out.append("")
    out.append(
        f"발행 가능한 **런** {len(published)}개 / 거부 {len(rejected)}개. "
        "아래 표는 축별 대표 런만 보여주므로 행 수는 이보다 적다. "
        "판단 기준은 [`AGENT_TRACK_CLOSEOUT.md`](AGENT_TRACK_CLOSEOUT.md)."
    )
    out.append("")

    # 트랙/모델별 대표 런을 고른다. **런 이름 문자열 정렬을 쓰면 안 된다** —
    # fcrep_c 가 fcfull 보다 뒤로 잡혀 최신 670항목 결과가 밀려난다 (실제로 발생).
    # 축이 더 많고(=커버리지가 넓고), 그다음 항목 수가 많은 런을 대표로 삼는다.
    # **축 단위로 고른다.** taubench 는 telecom/retail/airline 이 서로 다른 런이므로
    # "모델당 1런" 으로 접으면 두 도메인이 사라진다 (실제로 발생).
    # 같은 축에 여러 런이 있으면 분모가 큰 쪽(=커버리지가 넓은 쪽)을 대표로 삼는다.
    # **런 이름을 tie-break 로 쓰지 않는다.** 예전에는 (분모, 런 이름) 튜플을
    # 비교해서, 분모가 같으면 이름이 사전순으로 뒤인 런이 대표가 됐다. 이름은
    # 측정의 성질이 아니므로 어느 쪽이 뽑히든 근거가 없다. 실측: taubench
    # qwen/telecom 은 분모 40 인 런이 5개인데 점수가 0.900 과 0.475 로 갈렸고,
    # 어느 것이 대표가 되는지를 이름 정렬이 정하고 있었다.
    #
    # 분모가 같으면 자동 선정하지 않고 후보를 그대로 드러낸다 — 무엇을 골라야
    # 하는지는 사람이 안다(어느 런이 어떤 규약으로 돌았는지).
    best: Dict[tuple, tuple] = {}
    ambiguous: Dict[tuple, list] = {}
    for r in published:
        for name, num, den, provisional in r["axes"]:
            key = (r["track"], r["model"], name)
            cand = den or 0
            current = best.get(key)
            if current is None or cand > current[0]:
                best[key] = (cand, r, (name, num, den, provisional))
                ambiguous.pop(key, None)
            elif cand == current[0]:
                ambiguous.setdefault(key, [current[1]["run"]]).append(r["run"])

    out.append(
        "> taubench 는 이 보고서에 없다. 사용자 시뮬레이터 프로토콜 고정 여부와 공식 "
        "split 커버리지를 보는 전용 계층이 판정을 갖는다 — "
        "`foundation_model_test_non_thinking/TAUBENCH_TRACK_RESULTS.md` "
        "(`report_taubench_tracks.py` 가 생성)."
    )
    out.append("")
    out.append("## 발행 가능한 수치 (축별 대표 런)")
    out.append("")
    out.append("| 트랙 | 모델 | 런 | 축 | 결과 | 상태 |")
    out.append("|---|---|---|---|---|---|")
    for key in sorted(best):
        _, r, (name, num, den, provisional) = best[key]
        track, model, _ = key
        if key in ambiguous:
            runs = ", ".join(f"`{run}`" for run in sorted(ambiguous[key]))
            out.append(
                f"| {track} | {model} | — | {name} | 대표 선정 불가 | "
                f"분모 {den} 인 런이 여럿이다: {runs} |"
            )
            continue
        state = "PROVISIONAL — 판정기 기준, 인간 검증 없음" if provisional else "확정"
        if provisional and r.get("judge_provenance_missing"):
            state += f" · 프로비넌스 없음({', '.join(r['judge_provenance_missing'])})"
        out.append(
            f"| {track} | {model} | {r['run']} | {name} | "
            f"{fraction(num, den)} | {state} |"
        )
    out.append("")

    if rejected:
        out.append("## 발행 불가 — 점수를 인용하지 마십시오")
        out.append("")
        for r in sorted(rejected, key=lambda x: (x["track"], x["model"], x["run"])):
            reasons = r["failures"] or [
                "게이트 기록 없음 — 현재 채점 계약으로 재채점되지 않는 낡은 산출물"
            ]
            out.append(f"- **{r['model']} / {r['run']} / {r['track']}**")
            for reason in reasons:
                out.append(f"  - {reason}")
        out.append("")

    if repro_report:
        out.append("## 재현성 (반복 실행)")
        out.append("")
        out.append(
            "**건수가 같다고 같은 측정이 아니다.** 통과한 **항목 집합**을 대조한다 — "
            "실측으로 통과 건수가 5런 내내 동일한데 통과 항목이 10개 뒤집힌 사례가 있다."
        )
        out.append("")
        for check in repro_report:
            label = {
                "IDENTICAL": "**IDENTICAL** — 통과 항목 집합이 완전히 같다",
                "DIVERGED": "**DIVERGED**",
                "UNVERIFIED": "**UNVERIFIED**",
            }.get(str(check["status"]), str(check["status"]))
            runs = ", ".join(f"`{session}`" for session in check["runs"])
            out.append(
                f"- `{check['model']}` · `{check['scoring_version']}` — {label}"
            )
            out.append(f"  - 런 {len(check['runs'])}개: {runs}")
            if check.get("passed_counts"):
                out.append(
                    f"  - 통과 건수 {check['passed_counts']} (산포 {check['count_spread']}) · "
                    f"항상 통과 {check['stable_passed']}건"
                )
            if check.get("unstable_items"):
                out.append(f"  - 런마다 뒤집힌 항목 {len(check['unstable_items'])}건")
            if check.get("reason"):
                out.append(f"  - {check['reason']}")
            if check.get("sampling_controls_removed"):
                removed = ", ".join(check.get("removed_sampling_params") or []) or "일부"
                out.append(
                    f"  - 이 백엔드는 `{removed}` 를 거부해 **샘플링 제어 수단이 제거됐다**. "
                    "흔들림은 모델 결함이 아니라 구조적 성질이며, 이 모델의 "
                    "**단일 런 숫자는 측정이 아니다**."
                )
        out.append("")

    out.extend(render_claims(claims or {}))

    out.append("## 읽는 법")
    out.append("")
    out.append("- 분자/분모를 함께 본다. 반올림된 점수만으로는 표본 크기가 사라진다.")
    out.append("- **축을 합산하거나 평균하지 않는다.** 서로 다른 능력을 잰다.")
    out.append("- PROVISIONAL 은 인간 검증 전이다. 정답률이 아니라 판정기 기준 점수다.")
    out.append("- 거부된 런의 숫자는 존재하더라도 인용하지 않는다.")
    out.append(
        "- 재현성은 **대표 런과 다른 코호트**일 수 있다. 대표가 `UNVERIFIED` 인데 "
        "다른 scoring_version 이 `DIVERGED` 라면, 발행 중인 수치에는 재현 근거가 없다는 뜻이다."
    )
    return "\n".join(out) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", type=Path, default=Path("foundation_model_test_non_thinking"))
    ap.add_argument("--strict", action="store_true", help="거부된 런이 있으면 exit 1")
    ap.add_argument("--show-rejected", action="store_true", default=True)
    ap.add_argument(
        "--write-markdown",
        type=Path,
        help="명령 없이 읽을 수 있는 보고서를 이 경로에 쓴다",
    )
    args = ap.parse_args(argv)

    rows = collect(args.base)
    repro_report = collect_functionchat_reproducibility(args.base)
    claims = collect_claims(args.base)
    if not rows:
        print("산출물이 없습니다.", file=sys.stderr)
        return 2

    if args.write_markdown:
        args.write_markdown.write_text(render_markdown(rows, repro_report, claims), encoding="utf-8")
        print(f"  wrote {args.write_markdown}")

    published = [r for r in rows if r["publishable"]]
    rejected = [r for r in rows if not r["publishable"]]
    no_record = [r for r in rows if not r["has_gate_record"]]

    print("=" * 78)
    print("발행 가능 (publish_status.publishable == true)")
    print("=" * 78)
    for r in sorted(published, key=lambda x: (x["track"], x["model"], x["run"])):
        head = f"  [{r['track']}] {r['model']} / {r['run']}"
        print(head)
        for name, num, den, provisional in r["axes"]:
            tag = "  ** PROVISIONAL — 판정기 기준, 인간 검증 없음 **" if provisional else ""
            print(f"      {name:<12} {fraction(num, den)}{tag}")
        if r.get("judge_errors") is not None:
            print(f"      (판정 불가 {r['judge_errors']}, 불안정 {r.get('unstable')})")

    if rejected and args.show_rejected:
        print()
        print("=" * 78)
        print("발행 불가 — 점수를 인용하지 마십시오")
        print("=" * 78)
        for r in sorted(rejected, key=lambda x: (x["track"], x["model"], x["run"])):
            print(f"  [{r['track']}] {r['model']} / {r['run']}")
            reasons = r["failures"] or [
                "게이트 기록 없음 — 현재 채점 계약으로 재채점되지 않는 낡은 산출물"
            ]
            for f in reasons:
                print(f"      X {f}")

    if no_record:
        print()
        print("  ⚠️  게이트 기록이 없는 런 (재채점하세요):")
        for r in no_record:
            print(f"      {r['model']}/{r['run']}/{r['track']}")

    print()
    print(f"  발행 가능 {len(published)} / 거부 {len(rejected)} / 게이트 기록 없음 {len(no_record)}")
    print("  상세 판단 기준: AGENT_TRACK_CLOSEOUT.md")

    if args.strict and (rejected or no_record):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
