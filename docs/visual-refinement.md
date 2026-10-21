# Corriger la conversion par comparaisons visuelles successives

Le mode `--refine` confronte plusieurs fois le rendu Mermaid à l’image BPMN d’origine. Il est disponible avec **Ollama ou OpenAI**, à condition de choisir un modèle vision capable de comparer plusieurs images dans une même requête.

## Installation

Depuis la racine du dépôt, dans l’environnement Python activé :

```bash
pip install -e '.[ui,visual]'
python -m playwright install chromium
```

Sur un Linux où les bibliothèques système du navigateur manquent :

```bash
python -m playwright install --with-deps chromium
```

Le téléchargement de Chromium se prépare en amont pour un poste déconnecté. Le rendu est ensuite local et hors connexion. Pour utiliser un exécutable Chromium déjà installé, définir `BPMN_CHROMIUM_EXECUTABLE` avec son chemin absolu.

## Commandes à copier

**Ollama** : démarrer le serveur et installer un modèle vision, puis :

```bash
ollama pull qwen3-vl:8b
bpmn-mermaid examples/demande/source.png --provider ollama --model qwen3-vl:8b --refine --rounds 3 -o output/demande-affinee
```

**OpenAI** : définir `OPENAI_API_KEY` dans le terminal, puis :

```bash
bpmn-mermaid examples/demande/source.png --provider openai --model gpt-4.1 --refine --rounds 3 -o output/demande-affinee-openai
```

**Reprendre un JSON corrigé**, en le comparant toujours à l’image d’origine :

```bash
bpmn-mermaid output/demande-affinee/model.json --from-json --reference-image examples/demande/source.png --provider ollama --model qwen3-vl:8b --refine --rounds 3 -o output/demande-reprise
```

`--rounds` borne les tours de correction entre **2 et 8**, avec **3 par défaut**. `--refine` produit toujours les PNG, SVG et HTML, sans nécessiter `--html`. L’option `--direction LR` ou `TB` fixe le sens initial; la boucle peut proposer l’autre sens si cela améliore la lisibilité sans changer le processus.

Dans **l’interface Streamlit**, cocher « Comparer et corriger les rendus », choisir le nombre de tours, puis lancer la reconnaissance. Le bouton « Affiner le JSON courant avec l’image source » reprend le JSON affiché. L’image originale doit rester chargée. Le ZIP téléchargeable contient l’ensemble des tours et de leurs pièces.

## Déroulement précis

1. **Vérifier le navigateur avant tout appel au fournisseur**, puis extraire les pools, couloirs, activités, passerelles et flux.
2. Valider le JSON, produire le Mermaid et l’exécuter avec le moteur JS embarqué dans Chromium. Conserver HTML, SVG et capture PNG du diagramme complet.
3. Envoyer **deux images**, dans cet ordre : BPMN original, puis rendu courant. Le modèle décrit les écarts avec leurs indices dans la source et propose un JSON complet corrigé ou un changement de sens.
4. Valider la proposition, régénérer le Mermaid et produire une nouvelle capture. Les modifications du JSON sont consignées dans un fichier `.diff`.
5. Envoyer **trois images** : original, rendu courant, rendu candidat. Le modèle doit comparer les deux versions à la source et justifier son choix. Une candidate n’est retenue que si le verdict la privilégie et ne signale aucune régression sémantique.
6. Recommencer dans la limite fixée. Deux avis successifs « equivalent » sur la version retenue permettent l’arrêt anticipé. Sinon, une dernière revue examine la version finale sans appliquer de nouvelle correction.

Les corrections du JSON se traduisent en modifications du code Mermaid généré. Le modèle ne peut pas injecter de JavaScript, de commandes ou de directives Mermaid arbitraires. Les seuls réglages graphiques automatiques sont actuellement le sens LR/TB; le placement libre des nœuds n’est pas pris en charge.

## Ce qui est comparé

Priorité aux éléments et à leur sens métier :

- activités et événements présents ou manquants;
- rattachement au bon pool et au bon couloir;
- source, destination, sens, nature et libellé des flèches;
- alternatives exclusives, parallélisme, synchronisation et boucles;
- libellés, texte coupé et recouvrements gênant la lecture.

La comparaison est **sémantique et visuelle**, pas une mesure de similitude des pixels. Les coordonnées d’une image BPMN et celles du rendu Mermaid diffèrent légitimement. Un changement de disposition ne doit pas entraîner la suppression d’un flux ou le changement de type d’une passerelle.

## Résultats et historique

À la racine du dossier de sortie :

| Fichier | Contenu |
|---|---|
| `model.json` | Dernier modèle retenu |
| `diagram.mmd` | Code Mermaid correspondant |
| `diagram.png`, `diagram.svg` | Rendus graphiques du modèle retenu |
| `diagram.html` | Page autonome, modifiable et utilisable hors connexion |
| `refinement.json` | Statut, version sélectionnée, compteurs et décisions |
| `review.txt` | Avertissements et chemin de l’historique |

Chaque exécution crée un sous-dossier unique dans `refinement/`. Il contient l’image d’origine, la première version, les candidates rendues, les avis JSON du modèle et les différences de modèles. Une exécution n’écrase pas l’historique d’une autre. Les fichiers finaux de même nom à la racine sont remplacés.

Dans le rapport, `comparisons_attempted` compte les demandes de comparaison, y compris celles échouées. `comparisons` compte les réponses de comparaison structurellement valides. Une proposition de modèle invalide peut donc suivre une comparaison valide, puis être rejetée.

| Statut | Interprétation |
|---|---|
| `visually_consistent` | Deux avis successifs sans écart signalé par le modèle |
| `review_required` | Budget atteint, désaccord, ambiguïté ou erreur; contrôle humain requis |
| `failed_initial` | Impossible d’obtenir le premier modèle/rendu; détails dans le rapport du tour |

Ces statuts ne constituent pas une preuve de fidélité. Même deux avis concordants peuvent reproduire la même erreur du modèle.

## Protections contre les dégradations

- Un modèle invalide ou un rendu impossible n’est pas sélectionné.
- Une candidate déclarée moins bonne, incertaine ou régressive est rejetée.
- Une proposition déjà observée est bloquée pour éviter les oscillations. Le dernier rendu retenu reste disponible.
- Une erreur du fournisseur pendant la correction est tracée; la version courante est conservée et la boucle continue dans son budget.
- Les identifiants et les références sont validés avant chaque rendu.
- Les captures trop grandes sont refusées au lieu d’être silencieusement tronquées : maximum 12 000 pixels par côté et 24 mégapixels.
- La clé API n’est pas enregistrée dans l’historique ni dans le HTML.

## Nombre d’appels et confidentialité

Pour `N` tours, le plafond est de **1 extraction + 2 × N + 1 comparaisons**. Avec trois tours : au plus **8 appels au fournisseur**. Si un JSON initial est fourni, l’extraction est évitée. L’arrêt anticipé ou le rejet d’une proposition avant rendu réduit le nombre d’appels.

À chaque comparaison, l’image d’origine et un ou deux rendus sont transmis au fournisseur configuré. Avec OpenAI ou un serveur distant, ces images quittent le poste. Le coût et le temps peuvent donc être nettement supérieurs à ceux d’une extraction simple. Aucune relance réseau automatique supplémentaire n’est effectuée en dehors des tours annoncés.

## Vérifications reproductibles

```bash
# Tests de la boucle avec rendus et avis simulés :
python -m unittest discover -s tests -v

# Vrai Chromium + serveur vision local simulé, sans appel LLM payant :
# Linux/macOS :
BPMN_RUN_VISUAL_TESTS=1 python -m unittest discover -s tests -p test_visual_integration.py -v
# PowerShell :
# $env:BPMN_RUN_VISUAL_TESTS='1'
# python -m unittest discover -s tests -p test_visual_integration.py -v
```

Le test d’intégration contrôle les captures réelles, l’ordre des images envoyées, l’acceptation d’une correction et l’arrêt après deux avis concordants. Il ne mesure pas les capacités d’un véritable modèle vision. Aucun résultat de qualité réelle n’est revendiqué sans corpus d’images annoté et exécution avec le modèle choisi.

Références : [captures Playwright](https://playwright.dev/python/docs/screenshots), [installation des navigateurs](https://playwright.dev/python/docs/browsers), [sous-graphes Mermaid](https://mermaid.js.org/syntax/flowchart.html).
