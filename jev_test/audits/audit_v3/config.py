"""Offline audit inputs and preregistered constants."""

from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRATCH = HERE.parent
KOSGD_DIR = SCRATCH / "data_kosgd"
ENGLISH_DIR = SCRATCH / "data_sgd_en"
SCHEMA_PATH = KOSGD_DIR / "extended_schema.json"
SELECTION_PATH = SCRATCH / "kosgd_audit/audit_result.json"
PLAN_PATH = Path("/Users/rainis/Desktop/workspace/source/model_test/jev_test/JEV_TEST_PLAN.md")
TOKENIZER_PATHS = {
    "clef": SCRATCH / "tokenizers/clef/tokenizer.json",
    "pplx": SCRATCH / "tokenizers/pplx_v1_1/tokenizer.json",
    "qwen38": Path("/Users/rainis/Desktop/workplace/models/Qwen_Qwen3.8_27B/tokenizer.json"),
}
OUT = HERE / "out"
TOKEN_LIMIT = 8192
TIMING_THRESHOLD = 0.95
SAMPLE_COUNT = 3000
SEED = 20261012
VARIANTS = ("full", "actions_only")
ALLOWED_ACTS = frozenset({
    "INFORM", "REQUEST", "AFFIRM", "NEGATE", "REQUEST_ALTS", "SELECT",
    "GOODBYE", "THANK_YOU", "INFORM_INTENT", "AFFIRM_INTENT", "NEGATE_INTENT",
})

# SPEC-AMBIGUOUS: R6 permits INCONCLUSIVE, but §7 lists only PASS|FAIL and
# does not select a primary variant when no rule FAILs and R6 is INCONCLUSIVE.
# Preserve INCONCLUSIVE; leave primary_variant null and return nonzero in
# that unresolved case. Never manufacture a FAIL or choose an evaluation arm.
# SPEC-AMBIGUOUS: §4 forbids sorting/padding R5-invalid bundles, while R7
# requires a two-item bundle for every full request. No invalid bundle is
# fabricated: its key is withheld, with raw IDs and the reason retained;
# the ordinary R7 key check detects the missing required value.
# SPEC-AMBIGUOUS: copy/distribution/version statistics have no specified
# handling for unavailable intent bundles. Preserve the requested denominator
# and report INCONCLUSIVE, never silently drop or impute those observations.
# SPEC-AMBIGUOUS: R6 does not define which frame to use if an adjacent USER
# has multiple frames for the same service with conflicting active_intents.
# Report the affected neighbor statistic INCONCLUSIVE; same-turn R6 is intact.
SPEC_AMBIGUITIES = [
    {"id": "A1", "topic": "R6 INCONCLUSIVE without another FAIL: primary selection undefined", "triggered": False},
    {"id": "A2", "topic": "R5-invalid full bundle representation unspecified", "triggered": False},
    {"id": "A3", "topic": "Statistics with unavailable intent bundles unspecified", "triggered": False},
    {"id": "A4", "topic": "Conflicting same-service frames in a neighboring USER", "triggered": False},
]
