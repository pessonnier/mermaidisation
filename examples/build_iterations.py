"""Démonstration reproductible : vrais rendus Chromium, décisions SCRIPTÉES sans LLM.

Depuis la racine : python -m examples.build_iterations
Les défauts initiaux sont injectés volontairement, pas reconnus dans une image.
"""
from copy import deepcopy
import json
import difflib
from pathlib import Path
import shutil
import tempfile
from bpmn_mermaid.refinement import refine
from bpmn_mermaid.renderer import BrowserRenderer

ROOT = Path(__file__).resolve().parent


def scenarios(name):
    expected = json.loads((ROOT / name / "reference.json").read_text(encoding="utf-8"))
    initial = deepcopy(expected)
    if name == "demande":
        for node in initial["nodes"]:
            if node["id"] == "completer":
                node["lane"] = "gestion"
        initial["edges"] = [e for e in initial["edges"] if (e["source"], e["target"]) != ("completer", "complet")]
        first = deepcopy(initial)
        for node in first["nodes"]:
            if node["id"] == "completer":
                node["lane"] = "demandeur"
        issues = [
            {"category": "lane", "description": "Compléter le dossier est dans le mauvais couloir",
             "evidence": "L’image source place cette tâche dans le couloir Demandeur"},
            {"category": "edge", "description": "La boucle de complément est absente",
             "evidence": "Dans la source une flèche relie Compléter le dossier à Dossier complet ?"}]
    else:
        for node in initial["nodes"]:
            if node["id"] in {"split", "join"}:
                node["kind"] = "exclusive"
        initial["edges"] = [e for e in initial["edges"] if (e["source"], e["target"]) != ("budget", "join")]
        first = deepcopy(initial)
        for node in first["nodes"]:
            if node["id"] in {"split", "join"}:
                node["kind"] = "parallel"
        issues = [
            {"category": "gateway", "description": "Les passerelles sont des alternatives au lieu de traitements parallèles",
             "evidence": "La source montre un + dans les deux losanges, et non un X"},
            {"category": "edge", "description": "La branche budgétaire ne rejoint pas la synchronisation",
             "evidence": "Une flèche de la source part de Vérifier le budget et entre dans la passerelle de jonction"}]
    reviews = []
    for index, candidate in enumerate((first, expected)):
        reviews.append({"status": "needs_changes", "issues": issues[index:], "direction": "LR", "proposed_model": candidate})
        reviews.append({"verdict": "candidate", "semantic_regression": False,
                        "rationale": "Décision scriptée : " + issues[index]["evidence"], "issues": issues[index+1:]})
    reviews += [{"status": "equivalent", "issues": [], "direction": "LR", "proposed_model": None} for _ in range(2)]
    return initial, first, expected, reviews, issues


def main():
    for name in ("demande", "validation-parallele"):
        initial, first, expected, replies, issues = scenarios(name)
        calls = []
        def scripted_comparator(images, prompt, **connection):
            index = len(calls)
            expected_count = [2, 3, 2, 3, 2, 2][index]
            if len(images) != expected_count:
                raise AssertionError("Ordre des étapes de comparaison incorrect")
            calls.append({"comparison": index + 1, "image_count": len(images),
                          "origin": "scripted_fixture_no_vision_model"})
            return deepcopy(replies[index])
        with tempfile.TemporaryDirectory() as temporary:
            result = refine((ROOT / name / "source.png").read_bytes(), temporary,
                            initial_model=initial, rounds=4, renderer=BrowserRenderer(),
                            client=scripted_comparator, provider="ollama", model="SCRIPTED-DEMO-NO-LLM")
            assert result["model"] == expected
            assert [entry["outcome"] for entry in result["report"]["history"]] == [
                "accepted", "accepted", "unchanged_equivalent", "unchanged_equivalent"]
            destination = ROOT / "iterations" / name
            destination.mkdir(parents=True, exist_ok=True)
            stages = [("initial", "initial"), ("candidate-01", "candidate-01"),
                      ("candidate-02", "candidate-02")]
            for folder, label in stages:
                target = destination / label
                target.mkdir(exist_ok=True)
                for filename in ("model.json", "diagram.mmd", "diagram.png", "diagram.svg"):
                    shutil.copyfile(result["run"] / folder / filename, target / filename)
            for number, (before, after) in enumerate((("initial", "candidate-01"), ("candidate-01", "candidate-02")), 1):
                old = (destination / before / "diagram.mmd").read_text(encoding="utf-8").splitlines()
                new = (destination / after / "diagram.mmd").read_text(encoding="utf-8").splitlines()
                delta = "\n".join(difflib.unified_diff(old, new, fromfile=before + "/diagram.mmd", tofile=after + "/diagram.mmd")) + "\n"
                (destination / f"changes-{number:02}.mmd.diff").write_text(delta, encoding="utf-8")
            # Seules les pièces légères sont versionnées; les HTML restent générables.
            for path in result["run"].iterdir():
                if path.is_file() and path.suffix in {".json", ".diff"}:
                    shutil.copyfile(path, destination / path.name)
            report_path = destination / "report.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["execution_mode"] = "scripted_fixture_no_vision_model"
            report["status_scope"] = "Convergence du scénario scripté uniquement, pas validation par un LLM réel"
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            provenance = {"mode": "scripted_fixture_no_vision_model", "initial_errors": "injected_manually",
                          "rendering": "real_bundled_mermaid_in_offline_chromium", "rounds": 4,
                          "comparisons": calls, "corrections": issues,
                          "disclaimer": "Ne mesure pas les performances de reconnaissance ou d’autocorrection d’un LLM."}
            (destination / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"{name}: deux corrections, deux confirmations, six comparaisons scriptées; rendus réels enregistrés.")


if __name__ == "__main__":
    main()
