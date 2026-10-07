# Assistant IA Cabinet Dentaire

API FastAPI pour envoyer des demandes textuelles à un modèle compatible avec l’API Chat Completions. Les instructions de réponse sont configurables dans `actions.json`.

## Fonctionnalités

- `POST /ask` : envoie une question, un contexte facultatif et un mode de réponse.
- `POST /ask-with-file` : accepte certains fichiers et transmet une description avec la demande. Le contenu des fichiers `.txt` est lu; pour les PDF, images et documents bureautiques, le code actuel ne lit pas le contenu.
- `GET /actions` et `GET /actions/categories` : consulte les modes disponibles.
- Cache en mémoire de 30 minutes et limite de 100 requêtes par heure et par adresse IP.
- Documentation interactive disponible avec Swagger UI et ReDoc.

## Prérequis

- Python 3.10 ou plus récent
- Une API LLM compatible avec le format Chat Completions

## Installation

```bash
git clone https://github.com/Jalal-Zerroudi/FastAPI-AI-Chat-Gpt-OSS-20b.git
cd FastAPI-AI-Chat-Gpt-OSS-20b

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Configuration

Crée un fichier `.env` à la racine du projet :

```env
ATLASCLOUD_API_URL=https://<provider>/v1/chat/completions
ATLASCLOUD_API_KEY=<api-key>
API_SECRET=<secret-personalise>
ALLOWED_HOSTS=localhost,127.0.0.1
```

L’application nécessite `ATLASCLOUD_API_URL` et `ATLASCLOUD_API_KEY` pour appeler le modèle. Définis un `API_SECRET` personnalisé pour exiger l’authentification Bearer sur les endpoints protégés. Ne publie pas de clés ni de secrets.

## Lancement

Depuis la racine du dépôt :

```bash
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

- Accueil : http://127.0.0.1:8000/
- Swagger UI : http://127.0.0.1:8000/docs
- ReDoc : http://127.0.0.1:8000/redoc

## Exemple

```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <API_SECRET>" \
  -d '{"prompt":"Résume les points importants","action":"resume"}'
```

Les modes disponibles sont définis dans `actions.json`. Si ce fichier est absent, `action.py` charge les modes par défaut et tente de générer une configuration.

## Endpoints

| Méthode | Chemin | Description |
| --- | --- | --- |
| GET | `/` | Page d’accueil |
| POST | `/ask` | Demande textuelle |
| POST | `/ask-with-file` | Demande avec fichier |
| GET | `/actions` | Modes et métadonnées |
| GET | `/actions/categories` | Modes regroupés par catégorie |
| GET | `/health` | État de configuration |
| GET | `/supported-files` | Extensions acceptées |
| GET | `/cache/stats` | Statistiques du cache |
| DELETE | `/cache/clear` | Vide le cache |
