"""무엇: T0 공개 지문 · 입력: 실제 참조 모듈/로컬 checkpoint · 출력: 해시/버전만 · 계약 §8-7 T-h."""

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import sys

from jeveval.io.hashes import code_sha256, sha256_file
from jeveval.io.run_files import read_json, write_json


def initialize(directory, bundle, root):
    cfg = bundle.metadata["config"]
    record = dict(schema="t0_fingerprint/1", inputs_sha256=bundle.sha256,
                  fixture_sha256=bundle.metadata["fixture_sha256"],
                  config_sha256=bundle.metadata["config_sha256"], code_sha256=code_sha256(root),
                  server={k: cfg["serving"][k] for k in ("engine_version", "image_digest")},
                  reference=None)
    record["server"]["served_name"] = cfg["served_name"]
    write_json(Path(directory) / "fingerprint.json", record)


def reference_fingerprint(runtime, checkpoint, device):
    modules = {getattr(m, "__name__", f"module_{i}"): m for i, m in enumerate(
        (runtime.module, runtime.answer_module, runtime.server)) if m is not None}
    modules.update({name: m for name, m in sys.modules.items() if name == "autojev" or name.startswith("autojev.")})
    files = {}
    for name, module in sorted(modules.items()):
        path = getattr(module, "__file__", None)
        if path is None or not Path(path).is_file():
            raise ValueError("loaded reference module file unavailable")
        files[name] = dict(file=Path(path).name, sha256=sha256_file(path))
    packages = {}
    for name in ("torch", "transformers", "autojev"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    checkpoint = Path(checkpoint).resolve()
    weights = {p.relative_to(checkpoint).as_posix(): sha256_file(p)
               for p in sorted(checkpoint.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}
    model = getattr(runtime.model, "model", runtime.model)
    dtype = getattr(model, "dtype", None)
    parameters = getattr(model, "parameters", None)
    if parameters is not None:
        first = next(iter(parameters()), None)
        dtype = getattr(first, "dtype", dtype)
        device = getattr(first, "device", device)
    return dict(modules=files, packages=packages, dtype=None if dtype is None else str(dtype),
                device=str(device), checkpoint_files=weights)


def add_reference(directory, bundle, runtime, checkpoint, device):
    path = Path(directory) / "fingerprint.json"
    record = read_json(path)
    if record["inputs_sha256"] != bundle.sha256:
        raise ValueError("fingerprint inputs mismatch")
    record["reference"] = reference_fingerprint(runtime, checkpoint, device)
    write_json(path, record)
