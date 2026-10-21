import argparse
import json
import sys
from pathlib import Path
from .core import render, review
from .vision import extract_file
from .html_export import export_html
from .refinement import refine


def main():
    parser = argparse.ArgumentParser(description="Image BPMN / JSON corrigé vers Mermaid")
    parser.add_argument("source", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True, help="Dossier de sortie")
    parser.add_argument("--provider", choices=["ollama", "openai"], default="ollama")
    parser.add_argument("--model", help="Nom du modèle vision (ou variable *_MODEL)")
    parser.add_argument("--endpoint", help="URL de base du fournisseur (ou variable *_BASE_URL)")
    parser.add_argument("--html", action="store_true", help="Produire diagram.html, autonome et hors connexion")
    parser.add_argument("--direction", choices=["LR", "TB"], default="LR")
    parser.add_argument("--from-json", action="store_true", help="Régénérer sans appel au modèle")
    parser.add_argument("--refine", action="store_true", help="Comparer et corriger plusieurs rendus avec l’image source")
    parser.add_argument("--rounds", type=int, default=3, help="Nombre maximal de tours de correction visuelle (2 à 8)")
    parser.add_argument("--reference-image", type=Path, help="Image source obligatoire avec --from-json --refine")
    args = parser.parse_args()
    try:
        if args.reference_image and not (args.from_json and args.refine):
            raise ValueError("--reference-image s’utilise avec --from-json --refine")
        if args.refine:
            if args.from_json and not args.reference_image:
                raise ValueError("--from-json --refine exige --reference-image pour comparer à l’original")
            source_image = args.reference_image if args.from_json else args.source
            if source_image.stat().st_size > 20 * 1024 * 1024:
                raise ValueError("Image supérieure à 20 Mio")
            initial = json.loads(args.source.read_text(encoding="utf-8")) if args.from_json else None
            result = refine(source_image.read_bytes(), args.output, rounds=args.rounds, direction=args.direction,
                            initial_model=initial, provider=args.provider, model=args.model, endpoint=args.endpoint,
                            progress=lambda message: print(message, flush=True))
            print(f"Export dans {args.output}; {result['report']['comparisons']} comparaisons; "
                  f"statut: {result['report']['status']}; détails dans refinement.json")
            return 0
        model = json.loads(args.source.read_text(encoding="utf-8")) if args.from_json else extract_file(
            args.source, model=args.model, endpoint=args.endpoint, provider=args.provider)
        mermaid, issues = render(model, args.direction), review(model)
        args.output.mkdir(parents=True, exist_ok=True)
        for name, content in {"model.json": json.dumps(model, ensure_ascii=False, indent=2),
                              "diagram.mmd": mermaid,
                              "review.txt": "\n".join(issues) + "\n"}.items():
            (args.output / name).write_text(content, encoding="utf-8")
        if args.html:
            (args.output / "diagram.html").write_text(export_html(model, args.direction), encoding="utf-8")
        print(f"Export dans {args.output}; relire review.txt et model.json")
    except (OSError, ValueError) as exc:
        print(f"Erreur: {exc}", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
