"""데이터셋 실재성 검증 — 계획안 8절(실행 전 클리어)의 1순위 게이트.

계획안은 KlueMrcDomainClustering, KorFin-STS/QA/Domain Clustering, FinParaSTS 등
다수 태스크가 MTEB/HF에 미존재한다고 추정한다. 평가 전 코드로 일괄 확정한다.

검증 항목:
  1) config 에 적힌 각 태스크가 MTEB registry 에 실재하는가
  2) (선택, --load) 실제 데이터 로드가 되는가 (split/HF 접근 확인)
  3) registry 의 한국어 태스크 전체 목록 덤프 (실재명 확인용)
"""

from __future__ import annotations

from dataclasses import dataclass

from evalcommon import get_task as _get_task, task_languages as _task_languages

from .config import all_task_specs, REPR_TASKS, TaskSpec


@dataclass
class VerifyResult:
    name: str
    kind: str
    in_registry: bool
    resolved_name: str | None  # registry 가 인식한 정식 이름
    languages: list[str]
    loadable: bool | None  # --load 시에만 채움
    error: str | None


def verify_task(spec: TaskSpec, *, load: bool) -> VerifyResult:
    try:
        task = _get_task(spec.name)
    except Exception as exc:
        return VerifyResult(spec.name, spec.kind, False, None, [], None, str(exc))

    resolved = getattr(getattr(task, "metadata", None), "name", spec.name)
    langs = _task_languages(task)

    loadable: bool | None = None
    err: str | None = None
    if load:
        try:
            task.load_data()
            loadable = True
        except Exception as exc:
            loadable = False
            err = str(exc)

    return VerifyResult(spec.name, spec.kind, True, resolved, langs, loadable, err)


def verify_all(*, load: bool = False) -> list[VerifyResult]:
    # all_task_specs + REPR_TASKS(중복 제거) — repr 의 AutoRAGRetrieval/subset 도 게이트에 포함.
    specs = list(all_task_specs())
    seen = {s.name for s in specs}
    for s in REPR_TASKS:
        if s.name not in seen:
            specs.append(s)
            seen.add(s.name)
    return [verify_task(s, load=load) for s in specs]


def list_korean_tasks() -> list[str]:
    """registry 의 한국어 태스크 실재명 목록(계획안 3-A 주석: 실행 전 일괄 확정)."""
    import mteb

    try:
        tasks = mteb.get_tasks(languages=["kor"])
    except Exception as exc:
        print(f"[datasets] get_tasks(languages=['kor']) 실패: {exc}")
        return []
    names = []
    for t in tasks:
        meta = getattr(t, "metadata", None)
        names.append(getattr(meta, "name", str(t)))
    return sorted(set(names))


def print_report(results: list[VerifyResult]) -> bool:
    """사람이 읽는 검증 표 출력. 모든 태스크 실재 시 True."""
    width = max(len(r.name) for r in results) + 2
    print("\n=== 데이터셋 실재성 검증 (계획안 8절) ===")
    print(f"{'TASK'.ljust(width)} {'KIND':<16} {'REGISTRY':<10} {'LOAD':<8} LANGS / ERROR")
    print("-" * (width + 60))
    all_ok = True
    for r in results:
        reg = "OK" if r.in_registry else "MISSING"
        if not r.in_registry:
            all_ok = False
        load = "-" if r.loadable is None else ("OK" if r.loadable else "FAIL")
        if r.loadable is False:
            all_ok = False
        tail = ",".join(r.languages[:6]) if r.in_registry else (r.error or "")
        if r.error and r.in_registry:
            tail = f"{tail}  ! {r.error}"
        print(f"{r.name.ljust(width)} {r.kind:<16} {reg:<10} {load:<8} {tail}")
    print("-" * (width + 60))
    print("결과:", "전부 실재 ✅" if all_ok else "❌ MISSING/FAIL 존재 — config 수정 후 재검증 필요")
    return all_ok
