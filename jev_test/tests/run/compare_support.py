"""무엇: 두 합성 모델 실행 · 입력: tmp_path · 출력: 실제 완료 폴더 · 계약 ⑥b-2 R3·R8."""

from copy import copy
from dataclasses import replace
import json

import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from jeveval.io.hashes import sha256_file
from jeveval.io.splits import write_split_plan
from jeveval.run.layout import run_dir
from tests.run.cli_support import Harness, put_yaml


class ModelHarness(Harness):
    @property
    def args(self):
        return {**super().args, "model": f"configs/models/{self.model_name}.yaml"}

    @property
    def directory(self):
        return run_dir(self.root / "results", self.model_name, "r1", self.set, self.variant)

    def post(self, url, body, timeout, headers=None):
        result = super().post(url, body, timeout, headers)
        value = json.loads(result.response_raw)
        value["private_echo"] = json.loads(body)["state"]
        if self.model_name == "second":
            if self.fail and " 3" in json.loads(body)["state"]:
                return replace(result, http_status=400, response_raw=json.dumps(value))
            for answer in value["answers"].values():
                if answer["type"] == "noul":
                    answer["noul"] = .7
        return replace(result, response_raw=json.dumps(value))


def pair(root, monkeypatch, set_name="klue_mrc_answerable", fail=False):
    first = ModelHarness(root, set_name)
    first.model_name, first.fail = "synthetic", False
    second = copy(first)
    second.model_name, second.fail, second.sent = "second", fail, []
    cfg = yaml.safe_load((root / "configs/models/synthetic.yaml").read_text())
    cfg["id"], cfg["t0"]["status"] = "second", "passed"
    put_yaml(root / "configs/models/second.yaml", cfg)
    if fail:
        add_test_row(first)
        second.plan = first.plan
    monkeypatch.chdir(root)
    monkeypatch.setenv("JEV_TEST_KEY", "private-test-key")
    first.finish()
    second.finish()
    return first, second


def add_test_row(h):
    path = h.root / "dataset/klue_mrc_answerable/rows.parquet"
    rows = pq.read_table(path).to_pylist()
    rows.append({**rows[-1], "guid": "3", "context": h.markers["group"] + " 3"})
    pq.write_table(pa.Table.from_pylist(rows), path)
    (path.parent / "SHA256SUMS").write_text(sha256_file(path) + "  rows.parquet\n")
    h.plan = replace(h.plan, groups={**h.plan.groups, "3": ["3"]}, test=["2", "3"],
        representative={**h.plan.representative, "3": "klue_mrc_answerable:3:3"})
    write_split_plan(h.plan, h.root / "configs/splits/klue_mrc_answerable.json")
