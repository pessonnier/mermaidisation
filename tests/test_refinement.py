"""Tests de décisions de la boucle; les images/avis simulés n'évaluent pas un LLM."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from bpmn_mermaid.core import render, validate
from bpmn_mermaid.refinement import refine

MODEL = json.loads((Path(__file__).parents[1] / "examples/model.json").read_text())
PNG = b'\x89PNG\r\n\x1a\nfixture'
ISSUE = {"category": "label", "description": "Libellé incorrect", "evidence": "La tâche de la source dit Déposer"}


def assessment(status="equivalent", candidate=None, direction="LR"):
    return {"status": status, "issues": [] if status == "equivalent" else [deepcopy(ISSUE)],
            "proposed_model": candidate, "direction": direction}


def judgment(verdict="candidate", regression=False):
    return {"verdict": verdict, "semantic_regression": regression, "rationale": "Libellé conforme à la source", "issues": []}


class FakeRenderer:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def __call__(self, model, direction, folder):
        self.calls.append((deepcopy(model), direction))
        if self.fail and len(self.calls) > 1:
            raise ValueError("Erreur du rendu candidate")
        folder.mkdir(parents=True, exist_ok=True)
        for name, data in {"model.json": json.dumps(model), "diagram.mmd": render(model, direction),
                           "diagram.html": "<html>fixture</html>", "diagram.svg": "<svg/>"}.items():
            (folder / name).write_text(data)
        (folder / "diagram.png").write_bytes(PNG)
        return PNG


class RefinementTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.renderer = FakeRenderer()
        self.calls = []

    def run_loop(self, replies, **kwargs):
        iterator = iter(replies)
        def client(images, prompt, **connection):
            self.calls.append((images, prompt))
            item = next(iterator)
            if isinstance(item, Exception):
                raise item
            return deepcopy(item)
        return refine(PNG, self.folder.name, initial_model=MODEL, renderer=self.renderer,
                      client=client, rounds=kwargs.pop("rounds", 2), **kwargs)

    def candidate(self):
        candidate = deepcopy(MODEL)
        candidate["nodes"][1]["label"] = "Déposer la demande corrigée"
        return candidate

    def test_two_comparisons_before_convergence(self):
        result = self.run_loop([assessment(), assessment()])
        self.assertEqual(result["report"]["status"], "visually_consistent")
        self.assertEqual(len(self.calls), 2)
        self.assertTrue(all(len(images) == 2 for images, _ in self.calls))

    def test_accept_render_then_three_image_judge_and_final_review(self):
        candidate = self.candidate()
        result = self.run_loop([assessment("needs_changes", candidate), judgment(), assessment(), assessment()])
        self.assertEqual(result["model"], candidate)
        self.assertEqual([len(images) for images, _ in self.calls], [2, 3, 2, 2])
        self.assertEqual(result["report"]["status"], "review_required")
        self.assertTrue((result["run"] / "changes-01.diff").exists())
        self.assertEqual(json.loads((Path(self.folder.name)/"model.json").read_text()), candidate)

    def test_reject_regression_even_if_verdict_candidate(self):
        result = self.run_loop([assessment("needs_changes", self.candidate()), judgment(regression=True), assessment(), assessment()])
        self.assertEqual(result["model"], MODEL)
        self.assertEqual(result["report"]["history"][0]["outcome"], "rejected_kept_current")

    def test_uncertain_judgment_keeps_original(self):
        result = self.run_loop([assessment("needs_changes", self.candidate()), judgment("uncertain"), assessment(), assessment()])
        self.assertEqual(result["model"], MODEL)

    def test_invalid_candidate_references_kept_and_traced(self):
        candidate = self.candidate();candidate["edges"][0]["target"] = ["invalid"]
        result = self.run_loop([assessment("needs_changes", candidate), assessment(), assessment()])
        self.assertEqual(result["model"], MODEL)
        self.assertEqual(result["report"]["history"][0]["outcome"], "error_kept_current")
        self.assertEqual(len(self.renderer.calls), 1)

    def test_render_failure_keeps_original(self):
        self.renderer.fail = True
        result = self.run_loop([assessment("needs_changes", self.candidate()), assessment(), assessment()])
        self.assertEqual(result["model"], MODEL)
        self.assertIn("Erreur du rendu", result["report"]["history"][0]["error"])

    def test_api_failure_does_not_lose_last_valid(self):
        result = self.run_loop([ValueError("serveur indisponible"), assessment(), ValueError("délai")])
        self.assertEqual(result["model"], MODEL)
        self.assertEqual(result["report"]["status"], "review_required")
        self.assertIn("final_error", result["report"])

    def test_same_model_proposal_not_rendered_again(self):
        result = self.run_loop([assessment("needs_changes", MODEL), assessment(), assessment()])
        self.assertEqual(len(self.renderer.calls), 1)
        self.assertEqual(result["report"]["history"][0]["outcome"], "repeated_candidate_kept_current")

    def test_cycle_back_to_previous_version_is_blocked(self):
        result = self.run_loop([assessment("needs_changes", self.candidate()), judgment(),
                                assessment("needs_changes", MODEL), assessment()])
        self.assertEqual(result["model"], self.candidate())
        self.assertEqual(result["report"]["history"][1]["outcome"], "repeated_candidate_kept_current")

    def test_layout_only_proposal(self):
        result = self.run_loop([assessment("needs_changes", MODEL, "TB"), judgment(), assessment(), assessment()])
        self.assertEqual(result["direction"], "TB")
        self.assertEqual(self.renderer.calls[-1][1], "TB")

    def test_malformed_reviews_require_human_review(self):
        result = self.run_loop([{"status": "equivalent", "issues": [ISSUE]}, assessment("uncertain"), assessment("uncertain")])
        self.assertEqual(result["report"]["status"], "review_required")

    def test_budget_and_directories_are_bounded_and_unique(self):
        first = self.run_loop([assessment("uncertain")] * 3)
        second = self.run_loop([assessment("uncertain")] * 3)
        self.assertNotEqual(first["run"], second["run"])
        self.assertLessEqual(first["report"]["comparisons"], 5)
        for rounds in (0, 1, 9, True):
            with self.assertRaises(ValueError): self.run_loop([], rounds=rounds)

    def test_no_key_in_trace(self):
        result = self.run_loop([assessment(), assessment()], api_key="test-secret-never-written")
        for path in Path(self.folder.name).rglob("*.json"):
            self.assertNotIn("test-secret-never-written", path.read_text())
        self.assertEqual(result["report"]["comparisons"], 2)

    def test_cli_requires_source_for_json_refinement(self):
        from bpmn_mermaid.cli import main
        with patch("sys.argv", ["cmd", "examples/model.json", "--from-json", "--refine", "-o", self.folder.name]):
            self.assertEqual(main(), 1)
