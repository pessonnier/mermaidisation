"""Modèle intermédiaire et génération déterministe, sans dépendance au LLM."""
import math

KINDS = {"task", "start", "end", "event", "exclusive", "parallel", "inclusive", "subprocess", "data", "annotation"}

def validate(model):
    if not isinstance(model, dict):
        raise ValueError("Le modèle doit être un objet JSON")
    def rows(key):
        value = model.get(key)
        if not isinstance(value, list) or any(not isinstance(x, dict) for x in value):
            raise ValueError(f"{key}: liste d'objets requise")
        return value
    pools, lanes, nodes, edges = (rows(k) for k in ("pools", "lanes", "nodes", "edges"))
    if not nodes:
        raise ValueError("Aucun élément reconnu")
    identifiers = set()
    for item in pools + lanes + nodes:
        ident = item.get("id")
        if not isinstance(ident, str) or not ident or ident in identifiers:
            raise ValueError(f"Identifiant vide ou dupliqué: {ident!r}")
        identifiers.add(ident)
        if not isinstance(item.get("label"), str):
            raise ValueError(f"Libellé requis pour {ident}")
    pool_ids = {x["id"] for x in pools}
    lane_ids = {x["id"] for x in lanes}
    node_ids = {x["id"] for x in nodes}
    for lane in lanes:
        if lane.get("pool") not in pool_ids:
            raise ValueError(f"Pool inconnu pour {lane['id']}")
    for node in nodes:
        if node.get("lane") is not None and node["lane"] not in lane_ids:
            raise ValueError(f"Couloir inconnu pour {node['id']}")
        if node.get("kind") not in KINDS:
            raise ValueError(f"Type inconnu pour {node['id']}")
    for item in nodes + edges:
        score = item.get("confidence", 1.0)
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError("confidence doit être comprise entre 0 et 1")
    for edge in edges:
        if edge.get("source") not in node_ids or edge.get("target") not in node_ids:
            raise ValueError("Une flèche référence un élément inconnu")
        if edge.get("kind") not in {"sequence", "message", "association"}:
            raise ValueError("Type de flèche inconnu")
        if not isinstance(edge.get("label", ""), str):
            raise ValueError("Libellé de flèche invalide")
    warnings = model.get("warnings", [])
    if not isinstance(warnings, list) or any(not isinstance(x, str) for x in warnings):
        raise ValueError("warnings doit être une liste de textes")
    return model


def quote(text):
    # Mermaid decimal entities; disallow raw HTML, quotes and syntax delimiters.
    return "".join(c if c.isalnum() or c in " .,;:!?_-/+='" else f"#{ord(c)};" for c in text)


def review(model):
    validate(model)
    issues = list(model.get("warnings", []))
    issues.append("Transcription automatique à relire; les scores sont déclarés par le modèle et non calibrés.")
    for i, item in enumerate(model["nodes"] + model["edges"]):
        if item.get("confidence", 1) < .8:
            issues.append(f"Confiance faible: {item.get('id', 'flèche ' + str(i))}")
    linked = {e[k] for e in model["edges"] for k in ("source", "target")}
    issues.extend(f"Élément isolé: {n['id']}" for n in model["nodes"] if n["id"] not in linked)
    return issues


def render(model, direction="LR"):
    validate(model)
    if direction not in {"LR", "TB"}:
        raise ValueError("Direction attendue: LR ou TB")
    names = {x["id"]: f"v{i}" for i, x in enumerate(model["pools"] + model["lanes"] + model["nodes"])}
    lines = [f"flowchart {direction}"]
    def node_line(n, indent):
        label, kind = quote(n["label"]), n["kind"]
        marker = {"exclusive": "X", "parallel": "+", "inclusive": "O"}.get(kind)
        if marker:
            label = marker + (": " + label if label else "")
        if kind in {"start", "end", "event"}:
            shape = f'(("{label}"))'
        elif marker:
            shape = '{"' + label + '"}'
        elif kind == "subprocess":
            shape = f'[["{label}"]]'
        elif kind == "data":
            shape = f'[("{label}")]'
        else:
            shape = f'["{label}"]'
        lines.append(indent + names[n["id"]] + shape)
        if kind == "end":
            lines.append(indent + f"style {names[n['id']]} stroke-width:4px")
    for pool in model["pools"]:
        lines.append(f'  subgraph {names[pool["id"]]}["{quote(pool["label"])}"]')
        for lane in model["lanes"]:
            if lane["pool"] != pool["id"]:
                continue
            lines.append(f'    subgraph {names[lane["id"]]}["{quote(lane["label"])}"]')
            for n in model["nodes"]:
                if n.get("lane") == lane["id"]:
                    node_line(n, "      ")
            lines.append("    end")
        lines.append("  end")
    for n in model["nodes"]:
        if n.get("lane") is None:
            node_line(n, "  ")
    for e in model["edges"]:
        arrow = {"sequence": "-->", "message": "-.->", "association": "-.-"}[e["kind"]]
        label = f'|"{quote(e.get("label", ""))}"|' if e.get("label") else ""
        lines.append(f"  {names[e['source']]} {arrow}{label} {names[e['target']]}")
    return "\n".join(lines) + "\n"
