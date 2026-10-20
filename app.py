"""streamlit run app.py --server.address 127.0.0.1"""
import json
import os
import streamlit as st
from bpmn_mermaid.core import render, review
from bpmn_mermaid.html_export import export_html
from bpmn_mermaid.vision import DEFAULTS, extract

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
direction = st.sidebar.selectbox("Sens du diagramme", ["LR", "TB"])
image = st.file_uploader("Image BPMN", type=["png", "jpg", "jpeg", "webp"])
if image:
    st.image(image, caption="Image source")
    if st.button("Reconnaître le diagramme", type="primary"):
        try:
            with st.spinner("Lecture par le modèle vision…"):
                result = extract(image.getvalue(), model=model, endpoint=endpoint, provider=provider, api_key=api_key)
            st.session_state["editor"] = json.dumps(result, ensure_ascii=False, indent=2)
        except ValueError as exc:
            st.error(str(exc))
source = st.file_uploader("Ou reprendre un JSON corrigé", type=["json"])
if source and st.button("Charger le JSON"):
    try:
        st.session_state["editor"] = source.getvalue().decode("utf-8")
    except UnicodeDecodeError:
        st.error("Un fichier UTF-8 est requis")
st.text_area("Modèle intermédiaire à vérifier et corriger", key="editor", height=400)
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
