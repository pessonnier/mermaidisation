"""Rendu du moteur Mermaid embarqué avec Chromium, sans accès réseau."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from .core import render


class BrowserRenderer:
    def _run(self, *args):
        try:
            result = subprocess.run([sys.executable, "-m", "bpmn_mermaid.render_worker", *map(str, args)],
                                    capture_output=True, text=True, timeout=60)
        except subprocess.TimeoutExpired as exc:
            raise ValueError("Le rendu Chromium a dépassé 60 secondes") from exc
        if result.returncode:
            raise ValueError("Rendu Mermaid impossible : " + (result.stderr or result.stdout)[-1500:])

    def check(self):
        if importlib.util.find_spec("playwright") is None:
            raise ValueError("Installer pip install -e '.[visual]' puis python -m playwright install chromium")
        self._run("--check")

    def __call__(self, model, direction, folder):
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "model.json").write_text(json.dumps(model, ensure_ascii=False, indent=2), encoding="utf-8")
        (folder / "diagram.mmd").write_text(render(model, direction), encoding="utf-8")
        self._run(folder, direction)
        return (folder / "diagram.png").read_bytes()
