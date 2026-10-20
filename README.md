# Image BPMN → Mermaid

Transcription assistée d’images BPMN avec **lignes d’eau (couloirs / swimlanes)** en diagrammes Mermaid modifiables. Reconnaissance par un modèle vision exécuté via Ollama, validation d’un JSON intermédiaire et génération déterministe.

## Démarrage rapide

```bash
git clone https://github.com/pessonnier/mermaidisation.git
cd mermaidisation
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell : .venv\Scripts\Activate.ps1
pip install -e '.[ui]'
streamlit run app.py --server.address 127.0.0.1
```

Python 3.11+ requis. Dans l’interface, choisir **ollama** ou **openai**, charger une image, cliquer sur **Reconnaître le diagramme**, corriger le JSON si nécessaire puis télécharger **la page HTML autonome**. Ouvrir le fichier téléchargé par double-clic pour afficher le diagramme.

### Ollama — local

Installer [Ollama](https://ollama.com/download), puis :

```bash
ollama pull qwen3-vl:8b
# Si Ollama n’est pas déjà lancé : ollama serve
bpmn-mermaid processus.png --provider ollama --model qwen3-vl:8b -o output --html
```

URL par défaut : `http://localhost:11434`. Choisir un modèle avec vision adapté à la mémoire disponible. [Documentation Ollama Vision](https://docs.ollama.com/capabilities/vision).

### OpenAI — API

```bash
# Linux / macOS, dans le terminal qui lance l’application :
export OPENAI_API_KEY="votre-cle-api"
# Windows PowerShell : $env:OPENAI_API_KEY="votre-cle-api"
bpmn-mermaid processus.png --provider openai --model gpt-4.1 -o output --html
```

Dans l’interface, on peut aussi saisir la clé dans le champ masqué. Le modèle est librement configurable et doit accepter les images et la sortie JSON. `gpt-4.1` est la valeur initiale, pas une sélection automatique du dernier modèle. L’API est facturée séparément d’un abonnement ChatGPT. L’image est envoyée au serveur configuré. La clé ne figure jamais dans le JSON ou le HTML exporté.

Variables facultatives : `OPENAI_MODEL`, `OPENAI_BASE_URL` (défaut `https://api.openai.com/v1`), `OLLAMA_MODEL`, `OLLAMA_BASE_URL`. Les options `--model` et `--endpoint` priment sur les variables. Pour un point d’accès compatible OpenAI, renseigner une URL de base comprenant `/v1` si nécessaire; l’application ajoute `/chat/completions`. HTTPS est requis hors localhost pour transmettre une clé.

Le fichier `.env.example` donne les noms des variables; il **n’est pas chargé automatiquement**. Exporter les variables ou configurer l’environnement de lancement. Ne jamais ajouter une clé au dépôt.

Référence : [OpenAI — images et vision](https://developers.openai.com/api/docs/guides/images-vision). L’intégration utilise Chat Completions avec une image encodée en base64 et demande un objet JSON.

### Test immédiat sans modèle ni clé

```bash
bpmn-mermaid examples/model.json --from-json -o output --html
# Linux : xdg-open output/diagram.html
# Windows PowerShell : Start-Process output/diagram.html
# macOS : open output/diagram.html
```

Le fichier [examples/generated/diagram.html](examples/generated/diagram.html) est aussi fourni : le télécharger puis l’ouvrir localement. GitHub affiche son code, pas son rendu.

Le HTML contient **Mermaid JS, le code du diagramme et le modèle JSON**. Aucun CDN, serveur ou appel API n’est nécessaire à son ouverture. Le code Mermaid peut être modifié dans la page, puis réaffiché et exporté en SVG ou `.mmd`. **Enregistrer cette page** produit un nouveau HTML autonome avec le code modifié. Le JSON conserve la transcription d’origine et n’est pas recalculé depuis le code Mermaid.

Sorties CLI : `model.json`, `diagram.mmd`, `review.txt`, et `diagram.html` avec `--html`. Les fichiers de même nom sont remplacés. Pour reprendre un JSON corrigé sans relancer de reconnaissance :

```bash
bpmn-mermaid output/model.json --from-json -o output --html --direction TB
```

## Correspondances et limites

| BPMN | Mermaid |
|---|---|
| Pool / participant | Sous-graphe englobant |
| Couloir / ligne d’eau | Sous-graphe du pool |
| Tâche | Rectangle |
| Début / événement / fin | Cercle, contour épais pour la fin |
| Passerelle exclusive / parallèle / inclusive | Losange avec X / + / O |
| Sous-processus | Rectangle à double bord, contenu atomique |
| Donnée | Cylindre (approximation) |
| Annotation | Rectangle |
| Flux de séquence | Flèche continue |
| Flux de message | Flèche pointillée |
| Association | Lien pointillé sans flèche |

La disposition et les coordonnées originales ne sont pas conservées. Mermaid ne garantit pas l’alignement des couloirs; les liens entre sous-graphes influencent leur orientation. Voir la [documentation Mermaid](https://mermaid.js.org/syntax/flowchart.html).

Il ne s’agit pas d’un modèle BPMN 2.0 exécutable. Les événements attachés ou spécialisés, les flux par défaut et certains sous-types de tâches ne sont pas représentés fidèlement. La reconnaissance peut omettre ou inventer des éléments : **relecture humaine indispensable**. Les scores déclarés par le modèle ne sont pas calibrés.

## Modèle intermédiaire

Voir [examples/model.json](examples/model.json), avec deux couloirs, une décision et une boucle.

- `pools`: `id`, `label`.
- `lanes`: `id`, `label`, `pool` (identifiant du pool).
- `nodes`: `id`, `label`, `lane` (identifiant ou null), `kind`, `confidence` facultatif.
- `edges`: `source`, `target`, `kind`, `label` et `confidence` facultatifs.
- `warnings`: liste facultative d’ambiguïtés.

Les types admis sont définis dans `core.py`. Les identifiants doivent être uniques; les références de pools, de couloirs et de flèches sont vérifiées. La validation structurelle ne prouve pas la fidélité à l’image ou la validité métier du processus.

## Confidentialité

Avec Ollama et son URL par défaut, l’image est transmise au serveur local. Avec OpenAI ou une URL distante, le serveur indiqué reçoit l’image. Le choix du fournisseur est explicite. Télécharger les modèles et dépendances en amont pour une utilisation déconnectée.

Les réponses du modèle et le contenu de l’image ne sont jamais exécutés. Les identifiants Mermaid sont régénérés et les libellés échappés. L’interface est prévue pour un poste local; une exposition réseau nécessite une authentification, TLS et des limites de ressources adaptées.

## Développement et validation

```bash
python -m unittest discover -s tests -v
```

Les tests vérifient le modèle, les références, les boucles, les types de liens et d’éléments, l’échappement, la CLI et le protocole Ollama via un serveur simulé. GitHub Actions exécute la suite sur Python 3.11 à 3.13.

Les échanges Ollama et OpenAI sont testés avec un serveur HTTP simulé. Aucun essai avec un modèle vision réel ni appel OpenAI facturé n’a été réalisé dans l’environnement de création. Les tests ne mesurent pas la qualité de reconnaissance. Pour l’évaluer, utiliser un corpus d’images et de JSON relus, en mesurant séparément les libellés, les rattachements aux couloirs et les couples source/cible.

- `bpmn_mermaid/vision.py`: adaptateurs Ollama / OpenAI et prompt.
- `bpmn_mermaid/html_export.py`: génération HTML autonome.
- `bpmn_mermaid/assets/`: moteur Mermaid et gabarit embarqués.
- `bpmn_mermaid/core.py`: validation, avertissements et export Mermaid.
- `bpmn_mermaid/cli.py`: interface de commande.
- `app.py`: interface Streamlit.

Un autre fournisseur vision peut être ajouté en produisant le même JSON avant d’appeler `validate` et `render`.

## Moteur JavaScript embarqué

Mermaid **11.12.0**, distribution UMD complète (`dist/mermaid.min.js`), est conservé dans le paquet Python. Cela évite tout téléchargement à l’export ou à l’ouverture du HTML. Licence MIT dans `bpmn_mermaid/assets/MERMAID-LICENSE`; les notices des dépendances de la distribution sont conservées dans le bundle. Sources : [distribution officielle](https://www.npmjs.com/package/mermaid/v/11.12.0) et [projet Mermaid](https://github.com/mermaid-js/mermaid).

Le moteur est volontairement figé pour rendre les exports reproductibles. Pour le mettre à jour : remplacer le bundle et sa licence par ceux d’une version identifiée, mettre à jour le numéro indiqué dans le gabarit, puis vérifier la page hors connexion.
