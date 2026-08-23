"""Multimodal result publication gate.

The package only reads original benchmark artifacts.  Derived publication
records are written below each benchmark directory's ``_derived`` directory.
"""

from .classify import classify, classify_record
from .adapters import summarize_records
from .derive import (
    derive_all,
    derive_source,
    derived_sidecar_path,
    existing_native_sidecar,
    native_sidecar_from_records,
    native_sidecar_from_source,
    preflight_kreta_source,
    rejected_sidecar_from_source,
    write_sidecar,
)
from .schema import PublishStatus, RecordClass, dataset_item_digest, protocol_fingerprint

__all__ = [
    "PublishStatus",
    "RecordClass",
    "classify",
    "classify_record",
    "dataset_item_digest",
    "derive_all",
    "derive_source",
    "derived_sidecar_path",
    "existing_native_sidecar",
    "native_sidecar_from_records",
    "native_sidecar_from_source",
    "preflight_kreta_source",
    "rejected_sidecar_from_source",
    "protocol_fingerprint",
    "summarize_records",
    "write_sidecar",
]
