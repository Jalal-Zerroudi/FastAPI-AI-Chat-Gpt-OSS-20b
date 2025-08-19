# Assistant IA Cabinet Dentaire — API FastAPI

API avancée d’assistance pour cabinet dentaire : questions texte, analyse de fichiers (PDF/images), actions configurables via `actions.json`, cache en mémoire, rate limiting par IP et nettoyage des réponses modèles (suppression des `**`, `***`, `##`, `###`, etc.).

## ✨ Fonctionnalités

* **/ask** : requêtes texte avec actions (`default`, `resume`, `dental_diagnosis`, …)
* **/ask-with-file** : upload + analyse (PDF, images, docs)
* **Cache** : réponses mises en cache pendant 30 min (clé = `prompt+action+fichier`)
* **Rate limiting** : 100 requêtes / heure / IP
* **Sécurité** : HTTP Bearer optionnel (`API_SECRET`), Trusted hosts
* **CORS** : configurable (SPA, desktop, etc.)
* **Logs** : `dental_assistant.log` + console
* **Nettoyage Markdown** : supprime `**`, `***`, `##`, `###`, etc. pour des réponses “propres”

---

## 🧱 Architecture

```
.
├─ MyFastAPI.py           # Application FastAPI (point d’entrée: app)
├─ action.py              # ActionManager, prompts système, catégories
├─ actions.json           # (optionnel) Définition des actions (auto-généré si absent)
├─ requirements.txt
└─ .env                   # Variables d'environnement (à créer)
```

> `action.py` charge `actions.json` si présent, sinon il génère une version par défaut.

---

## 🛠️ Prérequis

* Python **3.10+**
* (Optionnel) `virtualenv` / `conda`
* Accès à une **API LLM** compatible `chat/completions` (via `ATLASCLOUD_API_URL` + `ATLASCLOUD_API_KEY`)

---

## 📦 Installation

```bash
git clone <ton-repo>
cd <ton-repo>

python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

---

## 🔧 Configuration (`.env`)

Crée un fichier `.env` à la racine :

```env
# API LLM (OpenAI/compatible)
ATLASCLOUD_API_URL=https://api.atlascloud.ai/v1/chat/completions
ATLASCLOUD_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx

# Sécurité (Bearer)
API_SECRET=change-me-strong-secret

# Hôtes/Origins
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:5500
```

> **Prod** : utilise un **API\_SECRET** robuste + configure précisément **ALLOWED\_HOSTS** et **CORS\_ORIGINS**.

---

## ▶️ Lancement

**Dev (auto-reload)**

```bash
uvicorn MyFastAPI:app --host 0.0.0.0 --port 8000 --reload
```

**Prod (simple)**

```bash
uvicorn MyFastAPI:app --host 0.0.0.0 --port 8000 --log-level info
```

Accès :

* Accueil : `http://127.0.0.1:8000/`
* Swagger UI : `http://127.0.0.1:8000/docs`
* ReDoc : `http://127.0.0.1:8000/redoc`

---

## 🔌 Endpoints

### GET `/`

Page HTML d’accueil et aperçu des endpoints.

### POST `/ask`

Requête texte avec action.

**Body**

```json
{
  "prompt": "Quels sont les symptômes d'une pulpite aiguë ?",
  "action": "dental_diagnosis",
  "context": "Patient adulte, douleur vive nocturne",
  "priority": "normal"
}
```

**Auth**

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

* `file` : PDF/PNG/JPG/DOC/DOCX/TXT (≤ 50MB)
* `prompt` : texte
* `action` : défaut `pdf_analysis`
* `extract_text` : bool (défaut `true`)

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

Regroupement par catégories (Traduction, Analyse, Médical, …).

### GET `/health`

État général (config + ping LLM basique).

### GET `/supported-files`

Extensions & MIME supportés.

### GET `/cache/stats`

Stats du cache en mémoire.

### DELETE `/cache/clear`

Vide le cache (auth requise).

---

## 📑 `actions.json` (extrait)

```json
{
  "response_modes": {
    "default": {
      "name": "Assistant Professionnel",
      "instruction": "Tu es un assistant IA professionnel spécialisé dans la gestion de cabinet dentaire. Réponds de manière précise, claire et structurée.",
      "format": "conversational",
      "description": "Mode standard"
    },
    "resume": {
      "name": "Résumé Structuré",
      "instruction": "Résume le texte suivant en exactement 5 points clés concis et clairs.",
      "max_length": "5_bullets",
      "format": "bullet_points",
      "description": "Résumé concis"
    },
    "dental_diagnosis": {
      "name": "Assistant Diagnostic",
      "instruction": "Assistant spécialisé en diagnostic dentaire. Mentionne que ça ne remplace pas l’avis d’un dentiste.",
      "format": "medical_analysis",
      "description": "Hypothèses et conseils"
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

---

## 🔐 Sécurité & bonnes pratiques

* **API\_SECRET** : protège `/ask`, `/ask-with-file`, `/cache/clear`.
* **TrustedHostMiddleware** : configure `ALLOWED_HOSTS`.
* **CORS** : renseigne tes origines exactes si cookies/credentials.
* **Proxy** : passe `X-Forwarded-For` pour un rate-limit IP correct.
* **Secrets** : n’upload pas `.env` ni `*.log` (voir `.gitignore`). Si déjà poussé, **rotate** les clés.

---

## 🧪 Qualité & perfs (conseils)

* Passage en **async** : remplace `requests` par `httpx.AsyncClient`.
* Tests unitaires pour `sanitize_model_text` (gras, titres, italique, code inline/blocs).
* En charge élevée : préférer un **LRU cache**/TTL borné.

---

## 👥 Équipe

- **Jalal Zerroudi** — [Portfolio](https://jalal-zerroudi.github.io/) · [GitHub](https://github.com/Jalal-Zerroudi)
- **Ayat Bouhrir** — [Portfolio](https://ayatbouhrir.github.io/) · [GitHub](https://github.com/ayatbouhrir)