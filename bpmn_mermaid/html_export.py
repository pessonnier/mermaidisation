"""Page HTML autonome: moteur Mermaid, source et JSON, sans réseau ni clé API."""
import json
import re
from importlib.resources import files
from .core import render, review


def script_json(value):
    return json.dumps(value, ensure_ascii=True).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def export_html(model, direction="LR"):
    payload = script_json({"model": model, "mermaid": render(model, direction), "warnings": review(model)})
    assets = files("bpmn_mermaid").joinpath("assets")
    vendor = assets.joinpath("mermaid.min.js").read_text(encoding="utf-8")
    license_text = assets.joinpath("MERMAID-LICENSE").read_text(encoding="utf-8")
    vendor = re.sub(r"</script", r"<\\/script", vendor, flags=re.IGNORECASE)
    template = assets.joinpath("viewer.html").read_text(encoding="utf-8")
    # Single substitution pass: user data must never be processed as template tokens.
    values = {"VENDOR": vendor, "PAYLOAD": payload, "LICENSE": license_text.replace("--", "—")}
    return re.sub(r"@@(VENDOR|PAYLOAD|LICENSE)@@", lambda m: values[m[1]], template)
