"""무엇: systemone 요청 구성·검사 · 입력: 모델·렌더·질문 · 출력: 요청/바이트/오류 · 계약 §2."""

from copy import deepcopy
import hashlib
import json
import re

from jeveval.types import BoundQuestion, Rendered, Request


def build_request(model: str, rendered: Rendered, questions: list[BoundQuestion]) -> Request:
    """질문과 선택지의 삽입 순서를 보존하고 중복 질문을 덮어쓰지 않는다."""
    bound = {}
    for question in questions:
        if question.id in bound:
            raise ValueError(f"duplicate question ID: {question.id}")
        if question.type == "score":
            raise NotImplementedError("score is out of scope")
        criteria = question.options if question.type == "choice" else question.criteria
        bound[question.id] = dict(type=question.type, instructions=question.instructions,
                                  criteria=deepcopy(criteria))
    return Request(model, rendered.state, bound)


def request_bytes(request: Request) -> bytes:
    """§2-1 봉투 순서와 UTF-8 인코딩을 고정한다."""
    return json.dumps(request.to_dict(), ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def request_sha256(request: Request) -> str:
    return hashlib.sha256(request_bytes(request)).hexdigest()


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _criteria_errors(criteria, kind, path):
    if not isinstance(criteria, dict):
        return [f"{path}: expected object"]
    errors = []
    if kind == "noul" and set(criteria) != {"true", "false"}:
        errors.append(f"{path}: expected true and false")
    if kind == "choice" and not 1 <= len(criteria) <= 255:
        errors.append(f"{path}: expected 1–255 options")
    if any(not _text(key) or not _text(value) for key, value in criteria.items()):
        errors.append(f"{path}: IDs and descriptions must be nonempty strings")
    folded = [key.casefold() for key in criteria if isinstance(key, str)]
    if kind == "choice" and len(set(folded)) != len(folded):
        errors.append(f"{path}: casefold collision")
    return errors


def check_request(request: Request, served_name: str) -> list[str]:
    """봉투 구조는 Request가 보장하며, 전송 전 필드의 도메인 오류를 모은다."""
    errors = []
    for name in ("model", "state"):
        if not _text(getattr(request, name)):
            errors.append(f"{name}: expected nonempty string")
    if request.model != served_name:
        errors.append("model: does not match served_name")
    if not isinstance(request.questions, dict) or not request.questions:
        return errors + ["questions: expected nonempty object"]
    for qid, question in request.questions.items():
        path = f"questions.{qid}"
        if not isinstance(qid, str) or not re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*", qid):
            errors.append(f"{path}: expected ASCII snake_case")
        if not isinstance(question, dict):
            errors.append(f"{path}: expected object")
            continue
        kind = question.get("type")
        if kind == "score":
            raise NotImplementedError("score is out of scope")
        if kind not in ("noul", "choice"):
            errors.append(f"{path}.type: expected noul or choice")
        if not _text(question.get("instructions")):
            errors.append(f"{path}.instructions: expected nonempty string")
        errors.extend(_criteria_errors(question.get("criteria"), kind, path + ".criteria"))
    return errors
