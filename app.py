"""streamlit run app.py --server.address 127.0.0.1"""
import json
import io
from pathlib import Path
import tempfile
import zipfile
import os
import streamlit as st
from bpmn_mermaid.core import render, review
from bpmn_mermaid.html_export import export_html
from bpmn_mermaid.vision import DEFAULTS, extract
from bpmn_mermaid.refinement import refine

st.set_page_config(page_title="BPMN → Mermaid", layout="wide")
st.title("Image BPMN → Mermaid")
st.caption("Reconnaissance des couloirs et des flux, puis correction avant export.")
provider = st.sidebar.selectbox("Fournisseur", ["ollama", "openai"])
default_model, default_endpoint = DEFAULTS[provider]
endpoint = st.sidebar.text_input("URL de base", os.getenv(provider.upper() + "_BASE_URL", default_endpoint), key=f"url_{provider}")
model = st.sidebar.text_input("Modèle vision", os.getenv(provider.upper() + "_MODEL", default_model), key=f"model_{provider}")
api_key = None
if provider == "openai":
    api_key = st.sidebar.text_input("Clé API (ou variable OPENAI_API_KEY)", type="password") or None
    st.sidebar.info("L’image sera envoyée au serveur OpenAI configuré. Les appels API sont facturés séparément de ChatGPT.")
else:
    st.sidebar.info("L’image sera envoyée au serveur Ollama indiqué. Une adresse distante reçoit son contenu.")
if "visual_pending_direction" in st.session_state:
    st.session_state["direction"] = st.session_state.pop("visual_pending_direction")
direction = st.sidebar.selectbox("Sens du diagramme", ["LR", "TB"], key="direction")
visual = st.sidebar.checkbox("Comparer et corriger les rendus", value=False)
rounds = st.sidebar.number_input("Tours de correction maximum", min_value=2, max_value=8, value=3, disabled=not visual)
if visual:
    st.sidebar.caption("Requiert l’option Python [visual] et Chromium. Jusqu’à 2 × tours + 1 comparaisons vision, en plus de l’extraction. Chaque comparaison renvoie l’image source au fournisseur.")


def visual_conversion(data, initial=None):
    with tempfile.TemporaryDirectory() as folder:
        status = st.empty()
        result = refine(data, folder, rounds=int(rounds), direction=direction, initial_model=initial,
                        provider=provider, model=model, endpoint=endpoint, api_key=api_key,
                        progress=status.info)
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
            for path in Path(folder).rglob("*"):
                if path.is_file():
                    bundle.write(path, path.relative_to(folder))
        st.session_state["visual_archive"] = archive.getvalue()
        st.session_state["visual_report"] = result["report"]
        st.session_state["visual_png"] = (Path(folder) / "diagram.png").read_bytes()
        st.session_state["visual_direction"] = result["direction"]
        st.session_state["visual_pending_direction"] = result["direction"]
        return result["model"]


image = st.file_uploader("Image BPMN", type=["png", "jpg", "jpeg", "webp"])
if image:
    st.image(image, caption="Image source")
    if st.button("Reconnaître le diagramme", type="primary"):
        try:
            with st.spinner("Lecture par le modèle vision…"):
                if visual:
                    result = visual_conversion(image.getvalue())
                else:
                    for key in ("visual_archive", "visual_report", "visual_png", "visual_direction"):
                        st.session_state.pop(key, None)
                    result = extract(image.getvalue(), model=model, endpoint=endpoint, provider=provider, api_key=api_key)
            st.session_state["editor"] = json.dumps(result, ensure_ascii=False, indent=2)
            if visual:
                st.rerun()
        except ValueError as exc:
            st.error(str(exc))
source = st.file_uploader("Ou reprendre un JSON corrigé", type=["json"])
if source and st.button("Charger le JSON"):
    try:
        st.session_state["editor"] = source.getvalue().decode("utf-8")
    except UnicodeDecodeError:
        st.error("Un fichier UTF-8 est requis")
if image and visual and st.session_state.get("editor") and st.button("Affiner le JSON courant avec l’image source"):
    try:
        result = visual_conversion(image.getvalue(), json.loads(st.session_state["editor"]))
        st.session_state["editor"] = json.dumps(result, ensure_ascii=False, indent=2)
        st.rerun()
    except ValueError as exc:
        st.error(str(exc))
st.text_area("Modèle intermédiaire à vérifier et corriger", key="editor", height=400)
if st.session_state.get("visual_report"):
    st.image(st.session_state["visual_png"], caption="Dernier rendu retenu par la boucle visuelle (avant retouches manuelles)")
    st.info("Sens retenu par la boucle : " + st.session_state["visual_direction"] + ". Les exports ci-dessous utilisent le sens sélectionné dans la barre latérale.")
    with st.expander("Historique des comparaisons visuelles"):
        st.json(st.session_state["visual_report"])
    st.download_button("Télécharger tous les tours (ZIP)", st.session_state["visual_archive"], "comparaisons-visuelles.zip", mime="application/zip")
if st.session_state.get("editor"):
    try:
        result = json.loads(st.session_state["editor"])
        mermaid = render(result, direction)
        for warning in review(result):
            st.warning(warning)
        st.code(mermaid, language="mermaid")
        st.download_button("Télécharger Mermaid", mermaid, "diagram.mmd")
        st.download_button("Télécharger le modèle JSON", json.dumps(result, ensure_ascii=False, indent=2), "model.json")
        st.download_button("Télécharger la page HTML autonome", export_html(result, direction), "diagram.html", mime="text/html")
        st.caption("Ouvrez le HTML téléchargé par double-clic : aperçu graphique, code modifiable et exports, sans connexion.")
    except ValueError as exc:
        st.error(f"Modèle à corriger: {exc}")
