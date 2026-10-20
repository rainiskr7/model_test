"""무엇: 누출 조각·escape·충돌·병합 시험. 입력: 합성 문자열. 출력: 위치만 있는 일치."""

import json

import pytest

from audits.publish_check.decode import views
from audits.publish_check.sources import Document, normalized
from audits.publish_check.windows import WindowIndex


TEXT = "가나다라마바사아자차카타파하거너더러머버"


def index(text=TEXT, **kwargs):
    return WindowIndex([Document(normalized(text), [("synthetic-id", "text")])], **kwargs)


def test_full_match_merges_and_l_minus_one_is_absent():
    value = index()
    matches = value.matches("prefix" + TEXT + "suffix")
    assert matches == [dict(source_ids=[dict(id="synthetic-id", field="text")],
                            source_start=0, blob_start=6, length=len(TEXT))]
    assert value.matches(TEXT[:11]) == []
    assert TEXT not in json.dumps(matches, ensure_ascii=False)


def test_whitespace_nfc_and_json_escapes():
    source = "가 나\n다라마바사아자차카타파하거너더러머버"
    blob = json.dumps({"nested": [source]}, ensure_ascii=True).encode()
    decoded = list(views(blob, ["escaped.json"]))
    assert any(index().matches(text) for _, _, text in decoded)
    assert all("일치 텍스트" not in hit for _, _, text in decoded for hit in index().matches(text))
    assert list(views(json.dumps(source).encode() + b"\n", ["escaped.jsonl"]))[-1][2] == normalized(source)
    assert index().matches(normalized("가 나\t다라마바사아자차카타파하거너더러머버"))


def test_forced_hash_collision_requires_exact_text():
    value = index(hash_fn=lambda text: 0)
    assert value.matches("전혀다른합성문장열두글자이상있습니다") == []
    assert value.matches(TEXT)


@pytest.mark.parametrize("payload,path", [(b"\xff", "binary.bin"), (b"abc\x00def", "binary.bin"),
                                         (b"{broken", "invalid.json"), (b'{}\n{broken', "invalid.jsonl")])
def test_unsupported_decode_raises(payload, path):
    with pytest.raises((ValueError, UnicodeDecodeError)):
        list(views(payload, [path]))


def test_candidate_limit_does_not_claim_clean():
    with pytest.raises(ValueError, match="candidate limit"):
        index(hash_fn=lambda text: 0).matches(TEXT, max_candidates=1)
