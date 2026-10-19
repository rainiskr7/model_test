import pytest

from tools.output_baseline.inputs import copy_roots, load_inputs


def test_fixed_list_and_dependencies(tmp_path):
    listing = tmp_path / "inputs.txt"
    listing.write_text("# reason\nagent results/a\ntaubench results/t\n"
                       "functionchat results/f\nmultimodal results/m/koffvqa_api_judge\n")
    entries = load_inputs(listing)
    assert len(entries) == 4
    assert copy_roots(entries) == ["configs/model_identity.json", "results/a", "results/f",
                                  "results/m/koffvqa", "results/m/koffvqa_api_judge", "results/t"]


@pytest.mark.parametrize("line", ["agent /results/a", "agent results/../data", "bad results/a",
                                  "agent results/a\nagent results/a"])
def test_reject_invalid_selection(tmp_path, line):
    path = tmp_path / "inputs.txt"
    path.write_text(line)
    with pytest.raises(ValueError):
        load_inputs(path)

