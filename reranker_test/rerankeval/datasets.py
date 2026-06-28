"""데이터셋 실재성 검증 + 로딩 — 계획안 8절 게이트.

검증: 각 태스크가 MTEB registry 에 존재하는가 + 성격(reranking/retrieval)이 config 와 맞는가.
로딩: retrieval 태스크의 (corpus, queries, qrels) 추출(2-stage rerank 입력).
"""

from __future__ import annotations

from dataclasses import dataclass

from evalcommon import get_task as _get_task, task_languages as _languages

from .config import all_task_specs, TaskSpec


@dataclass
class VerifyResult:
    name: str
    expected_kind: str
    in_registry: bool
    registry_type: str | None
    kind_ok: bool
    languages: list[str]
    error: str | None


def _registry_kind(task) -> str | None:
    meta = getattr(task, "metadata", None)
    t = getattr(meta, "type", None)
    return str(t).lower() if t else None


def verify_task(spec: TaskSpec) -> VerifyResult:
    try:
        task = _get_task(spec.name)
    except Exception as exc:
        return VerifyResult(spec.name, spec.kind, False, None, False, [], str(exc))
    rtype = _registry_kind(task)
    # reranking 기대인데 registry 가 retrieval 이면(또는 반대) 변환 경로 필요 → 표시
    kind_ok = rtype is not None and spec.kind in rtype
    return VerifyResult(spec.name, spec.kind, True, rtype, kind_ok, _languages(task), None)


def verify_all() -> list[VerifyResult]:
    return [verify_task(s) for s in all_task_specs()]


def print_report(results: list[VerifyResult]) -> bool:
    width = max(len(r.name) for r in results) + 2
    print("\n=== 데이터셋 실재성/성격 검증 (계획안 8절) ===")
    print(f"{'TASK'.ljust(width)} {'EXPECT':<10} {'REGISTRY':<10} {'TYPE':<12} {'KIND':<6} LANGS/ERR")
    print("-" * (width + 60))
    all_ok = True
    for r in results:
        reg = "OK" if r.in_registry else "MISSING"
        kind = "OK" if r.kind_ok else "DIFF"
        if not r.in_registry:
            all_ok = False
        tail = ",".join(r.languages[:6]) if r.in_registry else (r.error or "")
        if r.in_registry and not r.kind_ok:
            tail = f"{tail}  (registry={r.registry_type}, 기대={r.expected_kind} → 변환경로 확인)"
        print(f"{r.name.ljust(width)} {r.expected_kind:<10} {reg:<10} "
              f"{str(r.registry_type):<12} {kind:<6} {tail}")
    print("-" * (width + 60))
    print("결과:", "전부 실재 ✅" if all_ok else "❌ MISSING 존재 — config 수정 후 재검증")
    print("주: KIND=DIFF 는 오류가 아니라 'retrieval→rerank 변환 필요' 신호일 수 있음(계획안 3-2).")
    return all_ok


# --------------------------------------------------------------------------- #
# retrieval 태스크 로딩 → (corpus, queries, qrels)
# --------------------------------------------------------------------------- #
def load_retrieval_data(spec: TaskSpec, split: str | None = None) -> dict:
    """mteb retrieval 태스크에서 한 split 의 corpus/queries/qrels 를 표준 형태로 추출.

    반환: {"split", "corpus": {doc_id: text}, "queries": {qid: text},
           "qrels": {qid: {doc_id: gain}}}
    """
    from .config import SETTINGS
    task = _get_task(spec.name)
    task.load_data()

    def pick_split(mapping):
        if split and split in mapping:
            return split
        for s in ("test", "dev", "validation", "train"):
            if s in mapping:
                return s
        return next(iter(mapping))

    # split 은 relevant_docs(항상 split-keyed)에서 고른다.
    # corpus 는 split-keyed 일 수도, 전역(doc_id-keyed)일 수도 있어 키 존재 시에만 인덱싱.
    # (codex 검토 #7: 일부 mteb retrieval 로더는 corpus 가 전역이라 split 으로 인덱싱하면 깨짐.)
    chosen_split = pick_split(task.relevant_docs)
    qrels_split = task.relevant_docs[chosen_split]
    queries_split = task.queries[chosen_split] if chosen_split in task.queries else task.queries
    corpus_all = task.corpus
    corpus_split = corpus_all[chosen_split] if chosen_split in corpus_all else corpus_all

    # subset 키가 있으면(예: AutoRAG 금융, MIRACL ko) spec.subset 으로 선택
    corpus_split, queries_split, qrels_split = _maybe_subset(
        spec, corpus_split, queries_split, qrels_split)

    corpus = {did: _doc_text(v) for did, v in corpus_split.items()}
    queries = {qid: (v if isinstance(v, str) else _doc_text(v)) for qid, v in queries_split.items()}
    qrels = {qid: {d: float(g) for d, g in rels.items()} for qid, rels in qrels_split.items()}

    if SETTINGS.query_limit:
        keep = list(queries)[: SETTINGS.query_limit]
        queries = {q: queries[q] for q in keep}
        qrels = {q: qrels.get(q, {}) for q in keep}
    return {"split": chosen_split, "corpus": corpus, "queries": queries, "qrels": qrels}


def _maybe_subset(spec, corpus, queries, qrels):
    """spec.subset 이 있고 데이터가 {subset: {...}} 로 한 겹 더 싸여 있으면 풀어준다."""
    if spec.subset and isinstance(corpus, dict) and spec.subset in corpus \
            and isinstance(corpus[spec.subset], dict):
        return corpus[spec.subset], queries[spec.subset], qrels[spec.subset]
    return corpus, queries, qrels


def _doc_text(v) -> str:
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        title = v.get("title", "")
        text = v.get("text", "")
        return (title + "\n" + text).strip() if title else text
    return str(v)
