"""retrieval 태스크 로딩 + 정답보존 코퍼스 캡 — repr(dense/sparse/hybrid) 평가 입력.

rerankeval/datasets.load_retrieval_data 를 적응(split 우선순위 test>dev, subset 언랩,
corpus 전역/ split-keyed 처리, doc dict→title+text). repr 평가가 (corpus, queries, qrels)
를 표준 형태로 받게 한다.

코퍼스 캡(SETTINGS.corpus_sample_size)은 '정답보존형'이다: 보유 쿼리의 qrel 양성 문서는
모두 유지하고 남은 슬롯만 결정적 음성으로 채운다. 단순 doc_ids[:N] 캡은 정답을 코퍼스에서
지워 nDCG 의 IDCG 에 도달불가 양성이 포함돼 점수를 인위적으로 떨어뜨린다(codex 검토 D).
"""

from __future__ import annotations

from evalcommon import get_task as _get_task

from .config import TaskSpec


def load_retrieval_data(spec: TaskSpec, split: str | None = None) -> dict:
    """mteb retrieval 태스크 → {"split", "corpus": {id:text}, "queries": {qid:text},
    "qrels": {qid: {doc_id: gain}}}."""
    task = _get_task(spec.name)
    task.load_data()

    def pick_split(mapping):
        if split and split in mapping:
            return split
        for s in ("test", "dev", "validation", "train"):
            if s in mapping:
                return s
        return next(iter(mapping))

    chosen = pick_split(task.relevant_docs)
    qrels_split = task.relevant_docs[chosen]
    queries_split = task.queries[chosen] if chosen in task.queries else task.queries
    corpus_all = task.corpus
    corpus_split = corpus_all[chosen] if chosen in corpus_all else corpus_all

    corpus_split, queries_split, qrels_split = _maybe_subset(
        spec, corpus_split, queries_split, qrels_split)

    corpus = {did: _doc_text(v) for did, v in corpus_split.items()}
    queries = {qid: (v if isinstance(v, str) else _doc_text(v)) for qid, v in queries_split.items()}
    qrels = {qid: {d: float(g) for d, g in rels.items()} for qid, rels in qrels_split.items()}
    return {"split": chosen, "corpus": corpus, "queries": queries, "qrels": qrels}


def _maybe_subset(spec: TaskSpec, corpus, queries, qrels):
    """spec.subset 이 있으면 corpus/queries/qrels 각각 독립적으로 언랩.

    subset 이 지정됐는데 어디에서도 그 키를 찾지 못하면 hard-fail(엉뚱한 전체 데이터를
    조용히 평가하는 사고 방지, codex 검토 #3). 일부만 subset-keyed 인 경우도 각각 처리.
    """
    sub = getattr(spec, "subset", None)
    if not sub:
        return corpus, queries, qrels

    def is_keyed(d) -> bool:
        return isinstance(d, dict) and sub in d and isinstance(d[sub], dict)

    if not any(is_keyed(d) for d in (corpus, queries, qrels)):
        raise RuntimeError(
            f"[retrieval_data] subset '{sub}' 를 {spec.name} 에서 찾을 수 없음 "
            f"(corpus/queries/qrels 어디에도 '{sub}' 키 없음). config 또는 데이터 확인.")

    def unwrap(d):
        return d[sub] if is_keyed(d) else d

    return unwrap(corpus), unwrap(queries), unwrap(qrels)


def _doc_text(v) -> str:
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        title = v.get("title", "")
        text = v.get("text", "")
        return (title + "\n" + text).strip() if title else text
    return str(v)


def relevance_aware_cap(data: dict, cap: int | None) -> tuple[dict, dict, dict, dict]:
    """정답보존 코퍼스 캡. 반환: (corpus, queries, qrels, info).

    cap=None 이면 원본 그대로. cap<양성수면 cap 을 양성수로 올려 정답을 절대 버리지 않는다.
    채택 코퍼스 = 모든 qrel 양성 ∪ (결정적 음성으로 cap 까지 채움).
    """
    corpus, queries, qrels = data["corpus"], data["queries"], data["qrels"]
    if not cap or cap >= len(corpus):
        return corpus, queries, qrels, {"capped": False, "corpus_size": len(corpus)}

    positives = {d for rels in qrels.values() for d, g in rels.items() if g > 0 and d in corpus}
    effective_cap = max(cap, len(positives))
    # 결정적 음성 채움(정렬로 재현성)
    negatives = [d for d in sorted(corpus) if d not in positives]
    keep = set(positives)
    for d in negatives:
        if len(keep) >= effective_cap:
            break
        keep.add(d)
    capped_corpus = {d: corpus[d] for d in corpus if d in keep}
    info = {
        "capped": True, "corpus_size": len(capped_corpus),
        "requested_cap": cap, "effective_cap": effective_cap,
        "positives_kept": len(positives), "original_corpus": len(corpus),
    }
    return capped_corpus, queries, qrels, info
