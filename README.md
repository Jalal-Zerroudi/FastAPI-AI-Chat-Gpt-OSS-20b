# 🦷 Assistant IA Cabinet Dentaire — API FastAPI

API avancée pour assister un cabinet dentaire : questions texte, analyse de fichiers (PDF/images), actions configurables via `actions.json`, cache en mémoire, rate limiting par IP, et nettoyage des réponses modèles (suppression `**`, `***`, `##`, `###`, etc.).

## ✨ Fonctionnalités
- **/ask** : requêtes texte avec actions (`default`, `resume`, `dental_diagnosis`, …)
- **/ask-with-file** : upload + analyse (PDF, images, docs)
- **Cache** : réponses mises en cache pendant 30 min (clé basée sur `prompt+action+fichier`)
- **Rate limiting** : 100 requêtes / heure / IP
- **Sécurité** : HTTP Bearer optionnel (`API_SECRET`), Trusted hosts
- **CORS** : configurable pour frontends (SPA, desktop, etc.)
- **Logs** : `dental_assistant.log` + console
- **Nettoyage Markdown** : supprime `**`, `***`, `##`, `###`, etc. pour des réponses “propres”

---

## 🧱 Architecture rapide
```

.
├─ app.py                 # (Ton fichier FastAPI principal)
├─ action.py              # ActionManager, prompts système, catégories
├─ actions.json           # (optionnel) Configuration des actions (auto-généré si absent)
├─ requirements.txt
└─ .env                   # Variables d'environnement (à créer)

````

> `action.py` charge `actions.json` si présent, sinon crée une version par défaut.

---

## 🛠️ Prérequis
- Python **3.10+**
- (Optionnel) `virtualenv` / `conda`
- Accès à une **API LLM** compatible avec le schéma `model/messages` attendu (via `ATLASCLOUD_API_URL` + `ATLASCLOUD_API_KEY`)

---

## 📦 Installation
```bash
# 1) Cloner
git clone <ton-repo>
cd <ton-repo>

# 2) Créer un venv
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 3) Installer les dépendances
pip install --upgrade pip
pip install -r requirements.txt
````

---

## 🔧 Configuration (.env)

Crée un fichier `.env` à la racine :

```env
# URL de l'API LLM cible (ex: AtlasCloud / proxy OpenAI-compatible)
ATLASCLOUD_API_URL=https://api.atlascloud.ai/v1/chat/completions

# Clé d'accès à l'API LLM
ATLASCLOUD_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx

# Clé d'accès à TON API (Bearer). Si = "jalal" (valeur par défaut), l’auth est tolérante.
API_SECRET=change-me-strong-secret

# Hôtes autorisés pour TrustedHostMiddleware
ALLOWED_HOSTS=localhost,127.0.0.1

# Origines CORS autorisées (si tu actives allow_credentials=True)
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:5500
```

> **Note sécurité** : en prod, remplace **API\_SECRET** par une vraie valeur robuste et renseigne correctement **ALLOWED\_HOSTS** et **CORS\_ORIGINS**.

---

## ▶️ Lancement

### Dev (auto-reload)

```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

### Prod (simple)

```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --log-level info
```

> Accès :
>
> * Page d’accueil : `http://127.0.0.1:8000/`
> * Swagger UI : `http://127.0.0.1:8000/docs`
> * ReDoc : `http://127.0.0.1:8000/redoc`

---

## 🔌 Endpoints

### GET `/`

Page HTML d’accueil et aperçu des endpoints.

### POST `/ask`

Requête texte avec action.

**Body (JSON)**

```json
{
  "prompt": "Quels sont les symptômes d'une pulpite aiguë ?",
  "action": "dental_diagnosis",
  "context": "Patient adulte, douleur vive nocturne",
  "priority": "normal"
}
```

**Auth (optionnelle si API\_SECRET == 'jalal')**

```
Authorization: Bearer <API_SECRET>
```

**Réponse (200)**

```json
{
  "success": true,
  "action": "dental_diagnosis",
  "answer": "…réponse nettoyée sans ** ni ## …",
  "processing_time": 0.87,
  "cached": false
}
```

### POST `/ask-with-file`

Upload + analyse de fichier + prompt.

**Form-Data**

* `file`: (PDF/PNG/JPG/DOC/DOCX/TXT… — 50MB max)
* `prompt`: texte
* `action`: défaut `pdf_analysis`
* `extract_text`: bool (défaut `true`)

**cURL**

```bash
curl -X POST "http://127.0.0.1:8000/ask-with-file" \
  -H "Authorization: Bearer <API_SECRET>" \
  -F "file=@/chemin/rapport_radio.pdf" \
  -F "prompt=Analyser ce rapport et donner les points clés" \
  -F "action=pdf_analysis" \
  -F "extract_text=true"
```

### GET `/actions`

Liste détaillée des actions disponibles + métadonnées.

### GET `/actions/categories`

Regroupe les actions par catégories (Traduction, Analyse, Médical, …).

### GET `/health`

État général (config, connectivité LLM — ping basique).

### GET `/supported-files`

Extensions et MIME supportés.

### GET `/cache/stats`

Stats du cache en mémoire.

### DELETE `/cache/clear`

Vide le cache (auth requise).

---

## 📑 `actions.json` (optionnel)

Exemple de structure (généré si absent) :

```json
{
  "response_modes": {
    "default": {
      "name": "Assistant Professionnel",
      "instruction": "Tu es un assistant IA professionnel spécialisé dans la gestion de cabinet dentaire. Réponds de manière précise, claire et structurée.",
      "format": "conversational",
      "description": "Mode de réponse standard pour usage général"
    },
    "resume": {
      "name": "Résumé Structuré",
      "instruction": "Résume le texte suivant en exactement 5 points clés concis et clairs. Concentre-toi uniquement sur les informations essentielles.",
      "max_length": "5_bullets",
      "format": "bullet_points",
      "description": "Résumé concis en points clés"
    },
    "dental_diagnosis": {
      "name": "Assistant Diagnostic",
      "instruction": "Tu es un assistant spécialisé en diagnostic dentaire. Analyse les informations et rappelle que tes suggestions ne remplacent pas l'avis d'un dentiste.",
      "format": "medical_analysis",
      "description": "Assistance pour le diagnostic dentaire"
    }
  },
  "default_settings": {
    "language": "fr",
    "tone": "professional",
    "domain": "dental_medicine",
    "medical_disclaimer": "Les informations fournies sont à titre informatif et ne remplacent pas l'avis d'un professionnel de santé qualifié.",
    "created_at": "2025-08-19T12:00:00",
    "version": "1.0.0"
  }
}
```

Tu peux ajouter tes propres actions via `actions.json` ou dynamiquement avec `ActionManager.add_custom_action`.

---

## 🔐 Sécurité & bonnes pratiques

* **API\_SECRET** : protège `/ask`, `/ask-with-file`, `/cache/clear` si différent de `"jalal"`.
* **TrustedHostMiddleware** : configure `ALLOWED_HOSTS` (comma-separated).
* **CORS** : mets tes origines exactes dans `CORS_ORIGINS` si tu utilises cookies/credentials.
* **Proxy / IP réelle** : derrière Nginx/Traefik, assure-toi de passer `X-Forwarded-For` pour un rate-limit correct.

---

## 🧪 Conseils dev

* Pour un **vrai async** de l’appel LLM, remplace `requests` par `httpx.AsyncClient` (le code est prêt).
* Ajoute des **tests unitaires** pour `sanitize_model_text` (\*\*\*, \*\*, \_\_, *italique*, code inline/blocs, titres).
* En charge élevée, envisage un **LRU cache** au lieu d’un dict non borné.

---

## 📝 Licence

Usage interne / académique. Ajoute ta licence si nécessaire.

````

> Ces versions fonctionnent avec Pydantic v2 et FastAPI récents. Garde **requests** (ton code actuel) et **httpx** (si tu passes à l’async total).
