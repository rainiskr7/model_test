"""무엇: 격리 실행의 외부 코드/T0 증거 · 입력: 임시 root/설정 · 출력: 합성 파일 · 계약 §8-7."""

from hashlib import sha256
from pathlib import Path

from jeveval.t0.record import config_sha256
from jeveval.t0.request import canonical_bytes


def add_policy(root):
    """격리 실행도 저장소의 사전 선언 정책과 같은 바이트를 사용한다."""
    source = Path(__file__).resolve().parents[2] / "configs/policy.yaml"
    target = root / "configs/policy.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())
    return target


def add_external(root):
    """실제 외부 코드는 읽기만 하고 임시 model_test 구조 안에 같은 바이트를 둔다."""
    name = "reranker_test/evalcommon/schema.py"
    source = Path(__file__).resolve().parents[3] / name
    target = root.parent / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())
    return target


def passed_record(root, cfg, *, name="t0_record.json"):
    """설정 내용에 묶인 최소 PASS 기록을 만들고 설정 사본의 포인터를 채운다."""
    record = dict(status="PASS", config_sha256=config_sha256(cfg))
    payload = canonical_bytes(record)
    (root / name).write_bytes(payload)
    cfg["t0"] = dict(status="passed", record=dict(path=name, sha256=sha256(payload).hexdigest()))
    return root / name
