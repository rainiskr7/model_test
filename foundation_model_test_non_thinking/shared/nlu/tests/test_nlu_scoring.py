"""응답 형식 계약과 항목별 채점 회귀 테스트.

여기서 지키는 성질은 두 가지다.
- 계약 미준수(`invalid`)와 오답(`fail`)이 절대 같은 칸에 들어가지 않는다.
- 이 트랙은 점수를 만들지 않는다. 만들려는 시도가 들어오면 테스트가 깨진다.
"""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


NLU_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(NLU_DIR / "scoring"))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


contract_mod = load_module("nlu_contract_under_test", NLU_DIR / "scoring" / "contract.py")
scorer = load_module("nlu_score_run_under_test", NLU_DIR / "scoring" / "score_run.py")
CONTRACT = contract_mod.load_contract()
KEY = contract_mod.load_answer_key()


class ContractAndKeyAgree(unittest.TestCase):
    def test_every_contract_item_has_a_key_and_the_key_is_a_legal_label(self):
        items = {i["id"]: i for p in CONTRACT["prompts"].values() for i in p["items"]}
        self.assertEqual(set(items), set(KEY["items"]))
        for item_id, entry in KEY["items"].items():
            self.assertIn(entry["expected"], items[item_id]["labels"], item_id)

    def test_every_key_entry_states_why(self):
        # 라벨링은 판단이다. 근거를 적지 않으면 나중에 검토할 수 없다.
        for item_id, entry in KEY["items"].items():
            self.assertTrue(entry.get("rationale", "").strip(), item_id)

    def test_the_prompt_bodies_are_not_modified_by_the_contract(self):
        # 본문을 고치면 이미 커밋된 30개 산출물과 비교할 수 없게 된다.
        rendered = contract_mod.render(CONTRACT, "carwash")
        body = (NLU_DIR / "prompt" / "carwash.yaml").read_text(encoding="utf-8")
        self.assertNotIn(body.strip()[:20], rendered)
        self.assertTrue(rendered.startswith(CONTRACT["instruction_header"]))


class AnswerBlockParsing(unittest.TestCase):
    def parse(self, text):
        return contract_mod.parse_answers(text, CONTRACT)

    def test_a_plain_block_is_read(self):
        self.assertEqual(
            self.parse("설명설명\n[ANSWER]\ncarwash_choice: drive\n[/ANSWER]"),
            {"carwash_choice": "drive"},
        )

    def test_the_last_block_wins_when_the_model_echoes_the_template(self):
        # 모델이 계약 문구를 되풀이한 뒤 실제 답을 적는 일이 있다. 첫 블록을 집으면
        # 라벨 목록 자체를 답으로 읽는다.
        text = (
            "요청하신 형식은 다음과 같습니다.\n"
            "[ANSWER]\ncarwash_choice: walk | drive | depends\n[/ANSWER]\n"
            "제 답변입니다.\n"
            "[ANSWER]\ncarwash_choice: drive\n[/ANSWER]"
        )
        self.assertEqual(self.parse(text), {"carwash_choice": "drive"})

    def test_a_label_list_is_never_taken_as_an_answer(self):
        self.assertEqual(self.parse("[ANSWER]\ncarwash_choice: walk | drive\n[/ANSWER]"), {})

    def test_markdown_decoration_and_trailing_comments_are_stripped(self):
        text = "[ANSWER]\n**carwash_choice**: `drive`.    # 걸어갈지\n[/ANSWER]"
        self.assertEqual(self.parse(text), {"carwash_choice": "drive"})

    def test_a_missing_block_yields_nothing_rather_than_a_guess(self):
        self.assertEqual(self.parse("운전해서 가시는 것이 맞습니다."), {})


class ItemScoring(unittest.TestCase):
    ITEM = {"id": "carwash_choice", "labels": ["walk", "drive", "depends"]}

    def test_correct_label_passes(self):
        self.assertEqual(
            scorer.score_item(self.ITEM, {"carwash_choice": "drive"}, "drive")["status"], "pass"
        )

    def test_wrong_label_fails(self):
        self.assertEqual(
            scorer.score_item(self.ITEM, {"carwash_choice": "walk"}, "drive")["status"], "fail"
        )

    def test_a_missing_item_is_invalid_not_wrong(self):
        # 형식을 못 지킨 것과 틀린 것을 한 칸에 넣으면 다른 것을 재게 된다.
        result = scorer.score_item(self.ITEM, {}, "drive")
        self.assertEqual(result["status"], "invalid")
        self.assertNotEqual(result["status"], "fail")

    def test_an_unlisted_label_is_invalid_not_wrong(self):
        result = scorer.score_item(self.ITEM, {"carwash_choice": "자전거"}, "drive")
        self.assertEqual(result["status"], "invalid")
        self.assertIn("자전거", result["reason"])

    def test_case_and_whitespace_do_not_decide_the_verdict(self):
        self.assertEqual(
            scorer.score_item(self.ITEM, {"carwash_choice": "  Drive "}, "drive")["status"], "pass"
        )


class RunGating(unittest.TestCase):
    def _run(self, tmp, manifest, responses):
        run = Path(tmp) / "results" / "m_x" / "20260101_000000" / "language" / "nlu"
        run.mkdir(parents=True)
        if manifest is not None:
            (run / "run.json").write_text(json.dumps(manifest), encoding="utf-8")
        for stem, response in responses.items():
            (run / f"{stem}.json").write_text(
                json.dumps({"response": response}), encoding="utf-8"
            )
        return run

    def _complete_manifest(self, **over):
        manifest = {
            "status": "complete",
            "requested_model": "m/x",
            "answer_contract": {"version": CONTRACT["version"]},
        }
        manifest.update(over)
        return manifest

    def test_a_contractless_legacy_run_is_not_scored(self):
        # 계약 전후를 섞으면 둘 다 못 믿는다.
        with tempfile.TemporaryDirectory() as tmp:
            run = self._run(tmp, None, {"carwash": "운전하세요"})
            result = scorer.score_run(run)
            self.assertFalse(result["scorable"])
            self.assertTrue(any("run.json" in b for b in result["blockers"]))

    def test_a_partial_run_is_not_scored(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = self._run(tmp, self._complete_manifest(status="partial"), {})
            result = scorer.score_run(run)
            self.assertFalse(result["scorable"])
            self.assertTrue(any("완결" in b for b in result["blockers"]))

    def test_a_different_contract_version_is_not_scored(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self._complete_manifest(answer_contract={"version": 999})
            run = self._run(tmp, manifest, {})
            result = scorer.score_run(run)
            self.assertFalse(result["scorable"])
            self.assertTrue(any("계약 버전" in b for b in result["blockers"]))

    def test_a_complete_contracted_run_is_scored_item_by_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = self._run(tmp, self._complete_manifest(), {
                "carwash": "[ANSWER]\ncarwash_choice: drive\n[/ANSWER]",
                "jjajangmyeon": (
                    "[ANSWER]\nmother_reason: sacrifice\nspeaker_gender: male\n"
                    "speaker_gender_basis: stated\npalbochae: unlikely\n[/ANSWER]"
                ),
            })
            result = scorer.score_run(run)
            self.assertTrue(result["scorable"], result["blockers"])
            by_id = {e["item_id"]: e for e in result["items"]}
            self.assertEqual(by_id["carwash_choice"]["status"], "pass")
            # 가사에 성별이 명시되어 있지 않다. stated 는 텍스트에 없는 것을 있다고 한 것.
            self.assertEqual(by_id["speaker_gender_basis"]["status"], "fail")
            self.assertEqual(result["counts"], {"pass": 4, "fail": 1, "invalid": 0})

    def test_a_missing_response_file_blocks_scoring_it_is_not_a_format_failure(self):
        # 산출물이 없는 것은 계약 미준수가 아니다. invalid 로 세면 준수율이
        # 모델의 형식 실패처럼 떨어지고, 없는 파일이 오답으로 둔갑한다.
        with tempfile.TemporaryDirectory() as tmp:
            run = self._run(tmp, self._complete_manifest(), {
                "carwash": "[ANSWER]\ncarwash_choice: drive\n[/ANSWER]",
            })
            result = scorer.score_run(run)
            self.assertFalse(result["scorable"])
            self.assertTrue(
                any("jjajangmyeon" in b and "산출물이 없다" in b for b in result["blockers"]),
                result["blockers"],
            )
            self.assertEqual(result["counts"]["invalid"], 0, "미준수로 세면 안 된다")


class NoScoreIsManufactured(unittest.TestCase):
    def test_the_scorer_emits_no_average_or_rank(self):
        # 이 트랙의 유일한 결론이다. 항목 5개는 스칼라 점수를 지탱하지 못한다.
        source = (NLU_DIR / "scoring" / "score_run.py").read_text(encoding="utf-8")
        for forbidden in ("mean(", "/ len(", "rank", "percent"):
            self.assertNotIn(forbidden, source, f"점수를 만들고 있다: {forbidden}")

    def test_the_constant_strategy_baseline_is_reported(self):
        # 항목이 적으면 상수 전략이 놀랄 만큼 잘 나온다. 그 수를 옆에 두지 않으면
        # 통과 개수가 실력으로 읽힌다.
        baseline = scorer.constant_baseline()
        self.assertEqual(baseline["total_items"], 5)
        self.assertEqual(baseline["best_constant_passes"], 1)

    def test_an_item_every_model_answers_the_same_is_flagged_as_non_discriminating(self):
        runs = [
            {"scorable": True, "model": "m1", "items": [
                {"item_id": "a", "status": "pass", "answer": "drive"},
                {"item_id": "b", "status": "pass", "answer": "male"},
            ]},
            {"scorable": True, "model": "m2", "items": [
                {"item_id": "a", "status": "fail", "answer": "walk"},
                {"item_id": "b", "status": "pass", "answer": "male"},
            ]},
        ]
        disc = scorer.discrimination(runs)
        self.assertTrue(disc["a"]["discriminating"])
        self.assertFalse(disc["b"]["discriminating"])

    def _run(self, model, **answers):
        return {"scorable": True, "model": model, "items": [
            {"item_id": k, "status": "pass", "answer": v} for k, v in answers.items()
        ]}

    def test_one_model_cannot_establish_that_an_item_fails_to_discriminate(self):
        # 모델이 하나면 "모두 같은 답" 은 참이지만 아무 뜻도 없다. 비교 대상이
        # 없다는 사실을 '변별 못 함' 이라는 결론으로 위장하면 안 된다.
        one = [self._run("m1", a="drive")]
        self.assertFalse(scorer.discrimination(one)["a"]["assessable"])
        two = one + [self._run("m2", a="walk")]
        self.assertTrue(scorer.discrimination(two)["a"]["assessable"])

    def test_repeated_runs_of_one_model_are_not_read_as_failure_to_discriminate(self):
        # 같은 모델을 5번 돌리면 답이 같은 게 당연하다. 그것을 '변별 못 함' 으로
        # 보고하면 반복 실행이 항목의 결함으로 둔갑한다 — 실측에서 이렇게 나왔다.
        runs = [self._run("m1", a="walk") for _ in range(5)]
        info = scorer.discrimination(runs)["a"]
        self.assertFalse(info["assessable"])
        self.assertEqual(info["models"], 1)

    def test_stability_compares_item_answers_not_pass_counts(self):
        # 통과 수가 같아도 다른 항목을 맞힌 것이면 같은 측정이 아니다.
        same = [self._run("m1", a="drive", b="male"), self._run("m1", a="drive", b="male")]
        self.assertEqual(scorer.stability(same)["m1"]["status"], "IDENTICAL")
        flipped = [
            {"scorable": True, "model": "m1", "items": [
                {"item_id": "a", "status": "pass", "answer": "drive"},
                {"item_id": "b", "status": "fail", "answer": "female"}]},
            {"scorable": True, "model": "m1", "items": [
                {"item_id": "a", "status": "fail", "answer": "walk"},
                {"item_id": "b", "status": "pass", "answer": "male"}]},
        ]
        report = scorer.stability(flipped)["m1"]
        # 두 런 모두 통과 1개다. 건수만 보면 완벽한 재현으로 읽힌다.
        self.assertEqual(report["status"], "DIVERGED")
        self.assertEqual(sorted(report["unstable_items"]), ["a", "b"])

    def test_a_single_run_of_a_model_is_unverified_not_identical(self):
        self.assertEqual(scorer.stability([self._run("m1", a="drive")])["m1"]["status"], "UNVERIFIED")

    def test_the_predicate_never_claims_determinism_only_its_absence(self):
        # temperature=0 을 보냈다고 결정론이 보장되지 않는다 — 배치 구성, MoE
        # 라우팅, 부동소수점 비결합성. 그래서 필드 이름이 "제거됐는가" 여야 하고
        # "제어됐는가" 여서는 안 된다.
        source = (NLU_DIR / "scoring" / "score_run.py").read_text(encoding="utf-8")
        self.assertNotIn("decoding_controlled", source, "결정론을 주장하는 이름이 남아 있다")
        self.assertIn("sampling_controls_removed", source)

    def test_instability_is_attributed_to_the_backend_when_control_is_gone(self):
        # diffusion 백엔드는 temperature 를 거부한다 — 같은 요청에 다른 답이 나오는
        # 것이 정상이다. 실측: 요청 바이트가 동일한 5런에서 한 항목이 세 갈래로
        # 갈렸다. 이 구분이 없으면 구조적 흔들림이 모델 결함으로 읽힌다.
        runs = [
            {"scorable": True, "model": "d", "sampling_controls_removed": True,
             "removed_sampling_params": ["temperature"],
             "items": [{"item_id": "a", "status": "fail", "answer": "walk"}]},
            {"scorable": True, "model": "d", "sampling_controls_removed": True,
             "removed_sampling_params": ["temperature"],
             "items": [{"item_id": "a", "status": "pass", "answer": "drive"}]},
        ]
        info = scorer.stability(runs)["d"]
        self.assertEqual(info["status"], "DIVERGED")
        self.assertTrue(info["sampling_controls_removed"])
        self.assertIn("temperature", info["removed_sampling_params"])

    def test_a_controlled_backend_is_not_excused_for_instability(self):
        runs = [
            {"scorable": True, "model": "q", "sampling_controls_removed": False,
             "items": [{"item_id": "a", "status": "fail", "answer": "walk"}]},
            {"scorable": True, "model": "q", "sampling_controls_removed": False,
             "items": [{"item_id": "a", "status": "pass", "answer": "drive"}]},
        ]
        info = scorer.stability(runs)["q"]
        self.assertEqual(info["status"], "DIVERGED")
        self.assertFalse(info["sampling_controls_removed"])

    def test_compliance_is_counted_apart_from_correctness(self):
        # 계약을 못 지킨 것과 틀린 것을 합치면 계약 문구의 문제가 모델의 오답으로
        # 보고된다.
        runs = [{"scorable": True, "model": "m1", "counts": {"pass": 1, "fail": 1, "invalid": 3},
                 "items": [{"item_id": str(i), "status": "invalid", "answer": None} for i in range(5)]}]
        comp = scorer.compliance(runs)
        self.assertEqual(comp["items"], 5)
        self.assertEqual(comp["invalid"], 3)
        self.assertEqual(comp["honored"], 2)

    def test_format_failure_is_not_counted_as_a_different_answer(self):
        # invalid 를 답의 한 종류로 세면, 모두가 같은 답을 낸 항목이 '변별함' 으로
        # 둔갑한다. 실제로 E2E 에서 이렇게 잘못 나왔다.
        runs = [
            {"scorable": True, "model": "m1", "items": [
                {"item_id": "b", "status": "pass", "answer": "male"}]},
            {"scorable": True, "model": "m2", "items": [
                {"item_id": "b", "status": "invalid", "answer": None}]},
        ]
        disc = scorer.discrimination(runs)
        self.assertFalse(disc["b"]["discriminating"])
        self.assertEqual(disc["b"]["distinct_answers"], ["male"])
        self.assertEqual(disc["b"]["invalid_runs"], 1)


if __name__ == "__main__":
    unittest.main()
