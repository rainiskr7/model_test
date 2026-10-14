"""무엇: CLI 합성 파일/전송 도우미 · 입력: tmp_path · 출력: 실제 로더 입력 · 계약 §9."""

import json
from pathlib import Path
import shutil

import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from jeveval.io.hashes import sha256_file
from jeveval.io.splits import write_split_plan
from jeveval.run import cli, cmd_run
from jeveval.run.layout import run_dir
from jeveval.types import AttemptResult, LengthInfo, SplitPlan
from tests.run.t0_support import add_external

REPO = Path(__file__).resolve().parents[2]


def put_yaml(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, allow_unicode=True))


class Harness:
    def __init__(self, root, set_name="klue_mrc_answerable", variant="default", kind="systemone"):
        self.root, self.set, self.variant, self.sent = root, set_name, variant, []
        root.mkdir(parents=True, exist_ok=True)
        add_external(root)
        shutil.copytree(REPO / "configs/tasks", root / "configs/tasks")
        self.markers = json.loads((REPO / "tests/fixtures/canary/input.json").read_text())["markers"]
        rules = self._write_source(root, set_name)
        self._write_split(root, set_name, rules)
        self._write_model(root, kind)

    def _write_source(self, root, set_name):
        marker = self.markers
        data = root / "dataset" / set_name
        data.mkdir(parents=True)
        if set_name == "klue_mrc_answerable":
            rows = [dict(guid=str(i), context=f"{marker['group']} {i}", question=marker["state"],
                         source="synthetic", is_impossible=False,
                         answers={"text": [marker["gold"]], "answer_start": [0]}) for i in (1, 2)]
            source = data / "rows.parquet"
            pq.write_table(pa.Table.from_pylist(rows), source)
            rules = {"source": {"file": source.relative_to(root).as_posix()}}
        elif set_name == "fc_call_decision":
            rows = [dict(serial_num=i, input_messages=[dict(role="system", content=marker["state"]),
                    dict(role="user", content=f"{marker['group']} {min(i, 2)}")],
                    input_tools=[dict(function=dict(name=f"tool{min(i, 2)}", description="tool"))],
                    type_of_output="slot", ground_truth={"text": marker["gold"]}) for i in (1, 2, 3)]
            source = data / "rows.jsonl"
            source.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
            rules = {"source": {"file": source.relative_to(root).as_posix()}}
        else:
            rows = [dict(dialogue_id=str(i), services=[], turns=[dict(speaker="USER",
                    utterance=marker["state"], frames=[])]) for i in (1, 2)]
            source = data / "dialogues.json"
            source.write_text(json.dumps(rows))
            rules = {"source": {"dir": data.relative_to(root).as_posix(), "dialogues_glob": "*.json"}}
        (data / "SHA256SUMS").write_text(sha256_file(source) + f"  {source.name}\n")
        return rules

    def _write_split(self, root, set_name, rules):
        groups, representatives = {}, {}
        for i in (1, 2):
            item = "0" if set_name == "kosgd" else str(i)
            groups[str(i)] = [item]
            representatives[str(i)] = f"{set_name}:{i}:{item}"
        extra = []
        if set_name == "fc_call_decision":
            groups["2"].append("3")
            extra = [f"{set_name}:2:3"]
        self.plan = SplitPlan(set_name, 1, {}, {}, groups, representatives, ["1"], ["2"], [], extra, {})
        write_split_plan(self.plan, root / f"configs/splits/{set_name}.json")
        put_yaml(root / "configs/splits/rules.yaml", {"sets": {set_name: rules}})
        put_yaml(root / "configs/datasets.yaml", {"sets": [{"id": set_name,
                 "map": {"primary_variant": "full"} if set_name == "kosgd" else {}}]})

    def _write_model(self, root, kind):
        tokenizer = root / "tokenizer"
        tokenizer.mkdir()
        (tokenizer / "tokens.json").write_text("{}")
        encoder = root / "jeveval/run/encoders/hf_chat_template.py"
        encoder.parent.mkdir(parents=True)
        encoder.write_bytes((REPO / "jeveval/run/encoders/hf_chat_template.py").read_bytes())
        cfg = yaml.safe_load((REPO / "configs/models/clef.yaml").read_text())
        cfg.update(id="synthetic", kind=kind, served_name="fake", base_url="http://127.0.0.1:1",
                   auth_env="JEV_TEST_KEY", question_scoring="separate",
                   limit={"tokens": 1000, "overflow": "reject"},
                   encoder={"rule": "hf_chat_template_no_think"},
                   tokenizer={"path": "tokenizer", "files_sha256": {
                       "tokens.json": sha256_file(tokenizer / "tokens.json")}})
        if kind == "b1":
            labels = yaml.safe_load((root / "configs/tasks/b1.yaml").read_text())["labels"]
            cfg["b1"] = {"label_token_ids": dict(zip(labels, range(len(labels))))}
        put_yaml(root / "configs/models/synthetic.yaml", cfg)
        self.kind = kind

    @property
    def directory(self):
        return run_dir(self.root / "results", "synthetic", "r1", self.set, self.variant)

    @property
    def args(self):
        name = f"kosgd_{self.variant}" if self.set == "kosgd" else self.set
        return dict(root=self.root, model="configs/models/synthetic.yaml",
                    task=f"configs/tasks/{name}.yaml", run_id="r1")

    def measure(self, plan):
        return LengthInfo(12, 7, 1000, 5)

    def post(self, url, body, timeout, headers=None):
        self.sent.append((url, body, headers))
        request = json.loads(body)
        if self.kind == "b1":
            labels = yaml.safe_load((self.root / "configs/tasks/b1.yaml").read_text())["labels"]
            raw = {"choices": [{"logprobs": {"content": [{"top_logprobs": [
                {"token": labels[i], "logprob": -.1 - i} for i in range(len(request["allowed_token_ids"]))]}]}}],
                "usage": {"prompt_tokens": 12}}
        else:
            answers = {}
            for qid, question in request["questions"].items():
                if question["type"] == "noul":
                    answers[qid] = {"type": "noul", "noul": .9}
                else:
                    options = question["criteria"]
                    choice = "slot" if "slot" in options else next(iter(options))
                    answers[qid] = dict(type="choice", choice=choice, confidence=1.0,
                        probabilities={key: float(key == choice) for key in options})
            raw = {"answers": answers, "usage": {"input_tokens": 12}}
        return AttemptResult("2026-10-14T00:00:00.000Z", "2026-10-14T00:00:00.001Z",
                             1., 200, None, None, json.dumps(raw))

    def run(self, stage, **kwargs):
        return cmd_run.run(**self.args, stage=stage, measurer=self, post=self.post, **kwargs)

    def command(self, name):
        return cli.main([name, "--run-dir", str(self.directory)])

    def finish(self):
        self.run("dev")
        assert self.command("threshold") == 0
        self.run("test")
        if self.set == "fc_call_decision":
            self.run("extra")
        assert self.command("score") == 0
        assert self.command("certify") == 0


def output_files(directory):
    return {p.relative_to(directory).as_posix(): p.read_bytes()
            for p in directory.rglob("*") if p.is_file()}
