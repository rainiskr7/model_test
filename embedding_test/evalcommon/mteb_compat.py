"""mteb API 버전차 흡수 shim. mteb 는 함수 내부 지연 임포트."""

from __future__ import annotations


def get_task(name: str):
    """이름으로 단일 mteb 태스크 객체 반환(없으면 예외). 버전별 API 차이 흡수."""
    import mteb
    if hasattr(mteb, "get_task"):
        return mteb.get_task(name)
    tasks = mteb.get_tasks(tasks=[name])
    if not tasks:
        raise KeyError(name)
    return tasks[0]


def task_languages(task) -> list[str]:
    """태스크 메타에서 언어 코드 목록 추출(dict/list 형태 모두 대응)."""
    meta = getattr(task, "metadata", None)
    langs = getattr(meta, "languages", None) or getattr(meta, "eval_langs", None) or []
    if isinstance(langs, dict):
        out: set[str] = set()
        for v in langs.values():
            out.update(v)
        return sorted(out)
    return list(langs)
