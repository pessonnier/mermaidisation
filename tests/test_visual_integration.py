"""Test complet avec vrai Chromium et serveur vision simulé (aucun LLM distant)."""
import base64
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from bpmn_mermaid.refinement import refine
from bpmn_mermaid.renderer import BrowserRenderer

ROOT = Path(__file__).parents[1]


@unittest.skipUnless(os.getenv("BPMN_RUN_VISUAL_TESTS") == "1", "Activer BPMN_RUN_VISUAL_TESTS=1 avec Playwright/Chromium installés")
class VisualIntegrationTests(unittest.TestCase):
    def test_real_render_http_comparisons_correction_and_convergence(self):
        expected = json.loads((ROOT / "examples/demande/reference.json").read_text())
        initial = deepcopy(expected)
        initial["nodes"][1]["label"] = "Libellé erroné"
        source = (ROOT / "examples/demande/source.png").read_bytes()
        issue = {"category": "label", "description": "Libellé de tâche incorrect", "evidence": "La source indique Déposer la demande"}
        replies = [initial,
                   {"status": "needs_changes", "issues": [issue], "direction": "LR", "proposed_model": expected},
                   {"verdict": "candidate", "semantic_regression": False, "rationale": "Libellé rétabli", "issues": []},
                   {"status": "equivalent", "issues": [], "proposed_model": None, "direction": "LR"},
                   {"status": "equivalent", "issues": [], "proposed_model": None, "direction": "LR"}]
        calls = []
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                calls.append(payload)
                self.send_response(200); self.end_headers()
                self.wfile.write(json.dumps({"message": {"content": json.dumps(replies[len(calls)-1])}}).encode())
            def log_message(self, *args): pass
        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            with tempfile.TemporaryDirectory() as folder:
                result = refine(source, folder, rounds=3, renderer=BrowserRenderer(),
                                provider="ollama", model="test-vision", endpoint=f"http://127.0.0.1:{server.server_port}")
                self.assertEqual(result["model"], expected)
                self.assertEqual(result["report"]["status"], "visually_consistent")
                self.assertEqual(result["report"]["comparisons"], 4)
                self.assertEqual([len(c["messages"][0]["images"]) for c in calls], [1, 2, 3, 2, 2])
                for c in calls:
                    self.assertEqual(base64.b64decode(c["messages"][0]["images"][0]), source)
                self.assertNotEqual(calls[2]["messages"][0]["images"][1], calls[2]["messages"][0]["images"][2])
                for name in ("diagram.png", "diagram.svg", "diagram.html", "diagram.mmd", "model.json", "refinement.json"):
                    self.assertTrue((Path(folder) / name).stat().st_size > 0)
        finally:
            server.shutdown(); server.server_close(); thread.join()
