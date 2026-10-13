"""무엇: fixture 형식·독립 수치 검사 · 입력: 합성 JSON · 출력: 검증 · 계약 §9."""

import hashlib
import json
import math
from pathlib import Path

import pytest
from scipy.stats import beta

from jeveval.types import RiskCell


ROOT = Path(__file__).parent
JSON_FILES = sorted(ROOT.rglob("*.json"))
FOLDERS = {"render", "responses", "scoring", "splits", "resume", "length", "temperature", "b1",
           "answers", "expand", "records", "seal", "canary"}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object,
                      parse_constant=reject_nonfinite)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        assert key not in result, f"duplicate fixture key: {key}"
        result[key] = value
    return result


def reject_nonfinite(value):
    raise ValueError(f"non-JSON constant: {value}")


@pytest.mark.parametrize("path", JSON_FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_fixture_is_json_object(path):
    assert isinstance(read(path), dict)


def test_each_folder_has_readme_and_data():
    assert {p.name for p in ROOT.iterdir() if p.is_dir() and p.name != "__pycache__"} == FOLDERS
    for folder in FOLDERS:
        path = ROOT / folder
        assert len((path / "README.md").read_text(encoding="utf-8").splitlines()) == 1
        assert list(path.glob("*.json"))


@pytest.mark.parametrize("path", sorted((ROOT / "render").glob("*.json")), ids=lambda p: p.stem)
def test_render_bytes_and_hash(path):
    fixture = read(path)
    source, expected = fixture["input"], fixture["expected"]
    raw = expected["request_utf8"]
    assert hashlib.sha256(raw.encode("utf-8")).hexdigest() == expected["request_sha256"]
    body = json.loads(raw)
    assert list(body) == ["model", "state", "questions"]
    assert body["state"] == expected["state"]
    assert body["questions"] == source["questions"]
    assert body["model"] == source["model"]
    assert raw == json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    if source["state_spec"]["kind"] == "json_string":
        state = {key: source["state"][key] for key in source["state_spec"]["keys"]}
        assert expected["state"] == json.dumps(state, ensure_ascii=False, separators=(",", ":"))
    else:
        assert expected["state"] == source["state"]


def test_response_cases_cover_reason_codes_and_raw_duplicates():
    fixtures = [read(p) for p in (ROOT / "responses").glob("*.json")]
    assert {f["expected"]["reason"] for f in fixtures} == {
        None, "bad_body", "qid_mismatch", "type_mismatch", "noul_value",
        "choice_keys", "choice_values", "choice_pick",
    }
    for fixture in fixtures:
        assert isinstance(fixture["response_raw"], str)
        assert fixture["expected"]["valid"] == (fixture["expected"]["reason"] is None)
    for name in ("invalid_duplicate_key", "invalid_nested_duplicate_key"):
        raw = read(ROOT / "responses" / (name + ".json"))["response_raw"]
        with pytest.raises(AssertionError, match="duplicate fixture key"):
            json.loads(raw, object_pairs_hook=unique_object)


def cp_upper(k, n):
    if n == 0:
        return None
    return 1.0 if k == n else float(beta.ppf(.95, k + 1, n - k))


def test_risk_cp_bounds_and_minimum_sample_sizes():
    fixture = read(ROOT / "scoring/risk_cases.json")
    assert {(row["k"], row["n"]) for row in fixture["upper_bounds"]} >= {
        (6, 600), (0, 150), (1, 150), (0, 252), (0, 86),
    }
    for row in fixture["upper_bounds"]:
        expected = cp_upper(row["k"], row["n"])
        if expected is None:
            assert row["U"] is None
        else:
            assert row["U"] == pytest.approx(expected, abs=1e-9, rel=0)
    assert [row["n"] for row in fixture["n_min"]] == [299, 149, 59]
    for row in fixture["n_min"]:
        assert cp_upper(0, row["n"]) <= float(row["tau"]) < cp_upper(0, row["n"] - 1)


def test_risk_statuses_flags_and_flip():
    cases = read(ROOT / "scoring/risk_cases.json")["cases"]
    assert {c["expected"]["status"] for c in cases} == {"MEETS", "FAILS", "UNDERPOWERED", "NO_THRESHOLD"}
    for case in cases:
        result, tau = case["expected"], float(case["tau"])
        assert RiskCell.from_dict(result).to_dict() == result
        assert result["tau"] == case["tau"]
        test = result["test"]
        n, k, groups = test["n_accepted"], test["k_errors"], test["n_groups"]
        minimum = math.ceil(math.log(.05) / math.log1p(-tau))
        assert result["insufficient_by_design"] == (groups < minimum)
        if result["t_star"] is None:
            assert result["status"] == "NO_THRESHOLD"
            assert n is k is test["U"] is test["b_flip"] is None
            assert test["coverage"] == {"num": 0, "den": test["n_denom"]}
            continue
        u = cp_upper(k, n)
        assert test["U"] is None if u is None else abs(test["U"] - u) < 1e-9
        status = "UNDERPOWERED" if n < minimum else "MEETS" if u <= tau else "FAILS"
        assert result["status"] == status
        assert test["coverage"] == {"num": n, "den": test["n_denom"]}
        if status == "MEETS":
            b = test["b_flip"]
            assert cp_upper(k + b - 1, n) <= tau < cp_upper(k + b, n)
        else:
            assert test["b_flip"] is None


def test_temperature_single_application_and_mutations():
    fixture = read(ROOT / "temperature/pplx_path.json")
    temperature = fixture["temperature"]
    assert temperature == 1.00874
    distinguished = {0: False, 2: False}
    for case in fixture["cases"]:
        for applications, key in [(0, "zero_applications"), (1, "expected"), (2, "two_applications")]:
            scaled = [z / temperature ** applications for z in case["logits"]]
            weights = [math.exp(z - max(scaled)) for z in scaled]
            result = [weight / sum(weights) for weight in weights]
            assert case[key] == pytest.approx(result, abs=1e-12, rel=0)
            if applications != 1:
                distinguished[applications] |= any(abs(a-b) > fixture["comparison_atol"]
                                                   for a, b in zip(case[key], case["expected"]))
    assert all(distinguished.values())


def test_render_target_exact_prefix():
    for path in (ROOT / "render").glob("*.json"):
        fixture = read(path)
        source, expected = fixture["input"], fixture["expected"]
        spec = source["state_spec"]
        if spec["kind"] == "plain_text":
            prefix = source["state"]
        else:
            parts = []
            for key in spec["keys"]:
                value = source["state"][key]
                encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
                if key == spec["target_key"] and isinstance(value, list):
                    assert value
                    encoded = encoded[:-1]
                parts.append(json.dumps(key) + ":" + encoded)
                if key == spec["target_key"]:
                    break
            prefix = "{" + ",".join(parts)
        assert expected["target_end_char"] == len(prefix)
        assert expected["state"][:len(prefix)] == prefix


def test_functionchat_single_tool_source():
    source = read(ROOT / "render/functionchat.json")["input"]
    options = {t["function"]["name"]: t["function"]["description"]
               for t in source["state"]["input_tools"]}
    options["NONE"] = source["none_description"]
    assert source["questions"]["tool_pick"]["criteria"] == options


def test_canary_input_contains_each_marker():
    fixture = read(ROOT / "canary/input.json")
    text = json.dumps(fixture["input"], ensure_ascii=False)
    assert len(set(fixture["markers"].values())) == len(fixture["markers"])
    assert all(marker in text for marker in fixture["markers"].values())
