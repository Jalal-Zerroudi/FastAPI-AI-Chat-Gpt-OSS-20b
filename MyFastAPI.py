import os
import logging
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
import hashlib
import re
import httpx

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Depends, BackgroundTasks, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('dental_assistant.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Charger les variables d'environnement
load_dotenv()

# Configuration
API_URL = os.getenv("ATLASCLOUD_API_URL")
API_KEY = os.getenv("ATLASCLOUD_API_KEY")
API_SECRET = os.getenv("API_SECRET", "jalal")
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

# Constantes
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
CACHE_DURATION = timedelta(minutes=30)
RATE_LIMIT_REQUESTS = 100
RATE_LIMIT_WINDOW = timedelta(hours=1)

SUPPORTED_EXTENSIONS = {
    'pdf': 'application/pdf',
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg', 
    'png': 'image/png',
    'gif': 'image/gif',
    'bmp': 'image/bmp',
    'webp': 'image/webp',
    'txt': 'text/plain',
    'doc': 'application/msword',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
}

# Cache simple en mémoire
request_cache = {}
rate_limit_tracker = {}







# --- Ajoute ces regex en haut à côté des autres ---
MD_HEADING_RE = re.compile(r"(?m)^\s{0,3}#{2,3}\s*")       # ## ou ### au début de ligne
MD_TRIPLE_RE = re.compile(r"\*{3}([^\*]+?)\*{3}")          # ***texte***
MD_BOLD_RE   = re.compile(r"\*{2}([^\*]+?)\*{2}")          # **texte**
MD_IBOLD_RE  = re.compile(r"__([^_]+?)__")                 # __texte__
MD_ITALIC_RE = re.compile(r"(?<!\*)\*([^*\n]+?)\*(?!\*)")  # *texte* (non collé à d'autres *)
MD_INLINE_CODE_RE = re.compile(r"`([^`]+)`")               # `code`
MD_FENCE_RE  = re.compile(r"(?s)```(.*?)```")              # ```blocs```

def sanitize_model_text(text: str) -> str:
    """
    Supprime **, ***, ##, ### (et équivalents courants) sans casser le contenu.
    Laisse le texte tel quel, conserve le contenu des blocs/code inline mais retire juste les backticks/```.
    """
    if not text:
        return text

    # 1) Retirer les entêtes ##/###
    text = MD_HEADING_RE.sub("", text)

    # 2) Nettoyer les blocs de code fence: on retire les ``` mais on garde leur contenu
    def _strip_fence(m):
        inner = m.group(1)
        return inner.strip("\n")
    text = MD_FENCE_RE.sub(_strip_fence, text)

    # 3) Nettoyer l'inline code: enlever les backticks mais garder le contenu
    text = MD_INLINE_CODE_RE.sub(r"\1", text)

    # 4) Enlever ***gras/italique*** puis **gras** puis __gras__ puis *italique*
    text = MD_TRIPLE_RE.sub(r"\1", text)
    text = MD_BOLD_RE.sub(r"\1", text)
    text = MD_IBOLD_RE.sub(r"\1", text)
    text = MD_ITALIC_RE.sub(r"\1", text)

    # 5) Compacter lignes vides
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()






# Sécurité
security = HTTPBearer(auto_error=False)

# Modèles Pydantic améliorés
class Query(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=5000, description="Question ou demande")
    action: str = Field(default="default", description="Type d'action à effectuer")
    context: Optional[str] = Field(None, max_length=2000, description="Contexte additionnel")
    priority: Optional[str] = Field(default="normal", pattern="^(low|normal|high|urgent)$")
    
    @field_validator('prompt')
    @classmethod
    def validate_prompt(cls, v):
        if not v.strip():
            raise ValueError('Le prompt ne peut pas être vide')
        return v.strip()

class FileQuery(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=5000)
    action: str = Field(default="pdf_analysis")
    extract_text: bool = Field(default=True, description="Extraire le texte du fichier")
    analyze_structure: bool = Field(default=False, description="Analyser la structure du document")

class APIResponse(BaseModel):
    success: bool
    action: str
    answer: str
    processing_time: float
    file_info: Optional[Dict[str, Any]] = None
    warnings: Optional[List[str]] = None
    cached: bool = False

# Application FastAPI
app = FastAPI(
    title="Assistant IA Cabinet Dentaire",
    description="API avancée pour l'assistant IA spécialisé en gestion de cabinet dentaire",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Middlewares
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=ALLOWED_HOSTS
)

def get_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Validation de la clé API (optionnelle)"""
    if not credentials and API_SECRET != "jalal":
        raise HTTPException(status_code=401, detail="Clé API requise")
    
    if credentials and credentials.credentials != API_SECRET:
        raise HTTPException(status_code=401, detail="Clé API invalide")
    
    return credentials.credentials if credentials else None

def check_rate_limit(client_ip: str) -> bool:
    """Vérification simple du rate limiting"""
    now = datetime.now()
    
    if client_ip not in rate_limit_tracker:
        rate_limit_tracker[client_ip] = []
    
    # Nettoyer les anciennes requêtes
    rate_limit_tracker[client_ip] = [
        req_time for req_time in rate_limit_tracker[client_ip] 
        if now - req_time < RATE_LIMIT_WINDOW
    ]
    
    # Vérifier la limite
    if len(rate_limit_tracker[client_ip]) >= RATE_LIMIT_REQUESTS:
        return False
    
    # Ajouter la requête actuelle
    rate_limit_tracker[client_ip].append(now)
    return True

def get_cache_key(prompt: str, action: str, file_hash: Optional[str] = None) -> str:
    """Génère une clé de cache unique"""
    key_content = f"{prompt}:{action}:{file_hash or 'no_file'}"
    return hashlib.md5(key_content.encode()).hexdigest()

def get_from_cache(cache_key: str) -> Optional[Dict[str, Any]]:
    """Récupère une réponse du cache"""
    if cache_key in request_cache:
        cached_item = request_cache[cache_key]
        if datetime.now() - cached_item["timestamp"] < CACHE_DURATION:
            logger.info(f"Réponse trouvée en cache: {cache_key}")
            return cached_item["data"]
        else:
            # Cache expiré
            del request_cache[cache_key]
    return None

def save_to_cache(cache_key: str, data: Dict[str, Any]) -> None:
    """Sauvegarde une réponse en cache"""
    request_cache[cache_key] = {
        "data": data,
        "timestamp": datetime.now()
    }

def get_system_prompt_safe(action: str) -> str:
    """Récupère le prompt système avec fallback robuste"""
    try:
        from action import get_system_prompt
        return get_system_prompt(action)
    except ImportError:
        logger.warning("Module 'action' non trouvé, utilisation du prompt par défaut")
        return "Tu es un assistant IA professionnel spécialisé dans la gestion de cabinet dentaire."
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du prompt: {str(e)}")
        return "Tu es un assistant IA professionnel."

def validate_file_advanced(file: UploadFile) -> Tuple[bool, str, Dict[str, Any]]:  # Changé ici
    """Validation avancée des fichiers"""
    if not file.filename:
        return False, "Nom de fichier manquant", {}
    
    file_path = Path(file.filename)
    file_extension = file_path.suffix.lower().lstrip('.')
    
    if file_extension not in SUPPORTED_EXTENSIONS:
        supported = ', '.join(SUPPORTED_EXTENSIONS.keys())
        return False, f"Type de fichier non supporté: {file_extension}. Types supportés: {supported}", {}
    
    # Informations du fichier
    file_info = {
        "name": file.filename,
        "extension": file_extension,
        "mime_type": SUPPORTED_EXTENSIONS[file_extension],
        "size_bytes": 0
    }
    
    return True, "OK", file_info

async def process_file_content(file: UploadFile, file_info: Dict[str, Any]) -> Tuple[str, str]:  # Changé ici
    """Traite le contenu du fichier selon son type"""
    content = await file.read()
    file_info["size_bytes"] = len(content)
    
    if len(content) > MAX_FILE_SIZE:
        max_mb = MAX_FILE_SIZE // (1024*1024)
        raise HTTPException(
            status_code=413,
            detail=f"Fichier trop volumineux. Taille maximum: {max_mb}MB"
        )
    
    # Hash du fichier pour le cache
    file_hash = hashlib.md5(content).hexdigest()
    
    extension = file_info["extension"]
    
    if extension == 'txt':
        try:
            text_content = content.decode('utf-8')
            return text_content, file_hash
        except UnicodeDecodeError:
            return f"[Fichier texte non décodable: {file.filename}]", file_hash
    
    elif extension == 'pdf':
        return f"[Document PDF: {file.filename} - {len(content)} bytes]", file_hash
    
    elif extension in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']:
        return f"[Image: {file.filename} - {len(content)} bytes]", file_hash
    
    else:
        return f"[Fichier: {file.filename} - Type: {extension}]", file_hash

async def call_atlascloud_api_async(system_prompt: str, user_prompt: str, max_tokens: int = 1000) -> Dict[str, Any]:
    if not API_URL or not API_KEY:
        raise HTTPException(
            status_code=500,
            detail="Configuration API manquante. Vérifiez ATLASCLOUD_API_URL et ATLASCLOUD_API_KEY."
        )

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "openai/gpt-oss-20b",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "max_tokens": max_tokens,
        "temperature": 0.7
    }

    start_time = datetime.now()
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(API_URL, headers=headers, json=data)
        processing_time = (datetime.now() - start_time).total_seconds()

        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Erreur API {resp.status_code}: {resp.text}")

        result = resp.json()
        msg = None
        if "choices" in result and result["choices"]:
            choice = result["choices"][0]
            msg = choice.get("message", {}).get("content") or choice.get("text")

        if not msg:
            raise HTTPException(status_code=502, detail="Réponse API vide ou inattendue")

        return {"success": True, "message": msg.strip(), "processing_time": processing_time}

    except httpx.ReadTimeout:
        logger.error("Timeout de la requête API")
        raise HTTPException(status_code=504, detail="Timeout de la requête API")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur API: {str(e)}")
        raise HTTPException(status_code=502, detail=f"Erreur API: {str(e)}")

@app.get("/", response_class=HTMLResponse)
def read_root():
    """Page d'accueil avec interface simple"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Assistant IA Cabinet Dentaire</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .endpoint { background: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 5px; border-left: 4px solid #007bff; }
            .status { color: #28a745; font-weight: bold; }
            h1 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }
            .badge { background: #17a2b8; color: white; padding: 4px 8px; border-radius: 3px; font-size: 12px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🦷 Assistant IA Cabinet Dentaire</h1>
            <p class="status">✅ Service en ligne - Version 2.0.0</p>
            
            <h2>Endpoints disponibles</h2>
            
            <div class="endpoint">
                <h3>POST /ask <span class="badge">Texte</span></h3>
                <p>Requêtes textuelles simples avec actions configurables</p>
            </div>
            
            <div class="endpoint">
                <h3>POST /ask-with-file <span class="badge">Fichier</span></h3>
                <p>Upload et analyse de fichiers (PDF, images, documents)</p>
            </div>
            
            <div class="endpoint">
                <h3>GET /actions <span class="badge">Info</span></h3>
                <p>Liste des actions disponibles et leurs descriptions</p>
            </div>
            
            <div class="endpoint">
                <h3>GET /actions/categories <span class="badge">Info</span></h3>
                <p>Actions groupées par catégorie</p>
            </div>
            
            <div class="endpoint">
                <h3>GET /health <span class="badge">Status</span></h3>
                <p>État de santé du service et configuration</p>
            </div>
            
            <div class="endpoint">
                <h3>GET /docs <span class="badge">API</span></h3>
                <p>Documentation interactive Swagger UI</p>
            </div>
            
            <h2>Utilisation</h2>
            <p>Cette API permet d'interagir avec un assistant IA spécialisé pour les cabinets dentaires. 
            Elle supporte l'analyse de documents, radiographies, gestion de rendez-vous et aide au diagnostic.</p>
            
            <p><strong>Note :</strong> Les suggestions de diagnostic ne remplacent jamais l'expertise d'un dentiste qualifié.</p>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/ask", response_model=APIResponse)
async def ask_atlascloud(
    query: Query,
    background_tasks: BackgroundTasks,
    request: Request,
    api_key: Optional[str] = Depends(get_api_key)
):
    # IP client (priorité au X-Forwarded-For si présent)
    xff = request.headers.get("x-forwarded-for")
    client_ip = (xff.split(",")[0].strip() if xff else request.client.host) or "unknown"

    if not check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Trop de requêtes. Limite: 100 requêtes par heure.")

    
    try:
        start_time = datetime.now()
        
        # Vérification du cache
        cache_key = get_cache_key(query.prompt, query.action)
        cached_response = get_from_cache(cache_key)
        
        if cached_response:
            cached_response["cached"] = True
            return APIResponse(**cached_response)
        
        # Récupération du prompt système
        system_prompt = get_system_prompt_safe(query.action)
        
        # Construction du prompt utilisateur
        user_prompt = query.prompt
        if query.context:
            user_prompt = f"Contexte: {query.context}\n\nQuestion: {query.prompt}"
        
        # Ajustement des tokens selon la priorité
        max_tokens = {
            "low": 300,
            "normal": 500,
            "high": 800,
            "urgent": 1200
        }.get(query.priority, 500)
        
        # Appel API
        result = await call_atlascloud_api_async(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens
        )
        
        processing_time = (datetime.now() - start_time).total_seconds()
        clean_answer = sanitize_model_text(result["message"])

        response_data = {
            "success": True,
            "action": query.action,
            "answer": clean_answer,
            "processing_time": processing_time,
            "cached": False
        }
        
        # Sauvegarder en cache
        background_tasks.add_task(save_to_cache, cache_key, response_data)
        
        return APIResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur dans ask_atlascloud: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur inattendue: {str(e)}")

@app.post("/ask-with-file", response_model=APIResponse)
async def ask_with_file(
    file: UploadFile = File(...),
    prompt: str = Form(...),
    action: str = Form("pdf_analysis"),
    extract_text: bool = Form(True),
    api_key: Optional[str] = Depends(get_api_key)
):
    """Endpoint amélioré pour les fichiers avec métadonnées"""
    
    start_time = datetime.now()
    logger.info(f"Fichier reçu: {file.filename}, action: {action}")
    
    # Validation avancée
    is_valid, validation_message, file_info = validate_file_advanced(file)
    if not is_valid:
        raise HTTPException(status_code=400, detail=validation_message)
    
    try:
        # Traitement du fichier
        file_content_desc, file_hash = await process_file_content(file, file_info)
        
        # Vérification du cache
        cache_key = get_cache_key(prompt, action, file_hash)
        cached_response = get_from_cache(cache_key)
        
        if cached_response:
            cached_response["cached"] = True
            return APIResponse(**cached_response)
        
        # Construction du prompt
        system_prompt = get_system_prompt_safe(action)
        
        full_prompt = f"""Fichier uploadé: {file.filename}
                        Type: {file_info['extension'].upper()}
                        Taille: {file_info['size_bytes']} bytes
                        Contenu: {file_content_desc}

                        Question de l'utilisateur: {prompt}

                        Instructions spéciales:
                        - Analyse approfondie du contenu
                        - Réponse adaptée au contexte médical dentaire
                        - Précision et clarté professionnelle"""
        
        # Appel API
        result = await call_atlascloud_api_async(
            system_prompt=system_prompt,
            user_prompt=full_prompt,
            max_tokens=1200
        )
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        clean_answer = sanitize_model_text(result["message"])

        response_data = {
            "success": True,
            "action": action,
            "answer": clean_answer,
            "processing_time": processing_time,
            "file_info": file_info,
            "cached": False
        }
        
        # Cache en arrière-plan
        save_to_cache(cache_key, response_data)
        
        return APIResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur dans ask_with_file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors du traitement: {str(e)}"
        )

@app.get("/actions")
def get_available_actions():
    """Actions disponibles avec métadonnées enrichies"""
    try:
        from action import get_actions_info
        return get_actions_info()
    except ImportError:
        logger.warning("Module action non disponible")
        return {
            "actions": {
                "default": {"description": "Assistant général", "format": "conversational"},
                "dental_diagnosis": {"description": "Aide au diagnostic", "format": "medical"}
            },
            "error": "Configuration limitée disponible"
        }

@app.get("/actions/categories")
def get_action_categories():
    """Actions groupées par catégories"""
    try:
        from action import _action_manager
        if _action_manager:
            return _action_manager.get_actions_by_category()
    except:
        pass
    
    return {
        "Médical": ["dental_diagnosis", "treatment_plan"],
        "Analyse": ["pdf_analysis", "image_analysis"],
        "Communication": ["short", "long", "resume"],
        "Traduction": ["translate_fr", "translate_en"]
    }

@app.get("/health")
def health_check():
    """Vérification complète de l'état du système"""
    config_status = {
        "api_url_configured": bool(API_URL),
        "api_key_configured": bool(API_KEY),
        "max_file_size_mb": MAX_FILE_SIZE // (1024 * 1024),
        "supported_extensions": len(SUPPORTED_EXTENSIONS),
        "cache_entries": len(request_cache),
        "rate_limit_active_ips": len(rate_limit_tracker)
    }
    
    # Test de connectivité API (optionnel)
    api_healthy = True
    try:
        if API_URL and API_KEY:
            # Test ping rapide (vous pouvez implémenter un endpoint de santé)
            pass
    except:
        api_healthy = False
    
    return {
        "status": "healthy" if all([API_URL, API_KEY, api_healthy]) else "degraded",
        "timestamp": datetime.now().isoformat(),
        "configuration": config_status,
        "api_connectivity": api_healthy
    }

@app.get("/supported-files")
def get_supported_files():
    """Types de fichiers supportés avec détails"""
    file_types = {}
    for ext, mime in SUPPORTED_EXTENSIONS.items():
        file_types[ext] = {
            "mime_type": mime,
            "category": "document" if ext in ['pdf', 'doc', 'docx', 'txt'] else "image"
        }
    
    return {
        "supported_extensions": file_types,
        "max_file_size_mb": MAX_FILE_SIZE // (1024 * 1024),
        "total_supported": len(SUPPORTED_EXTENSIONS)
    }

@app.get("/cache/stats")
def get_cache_stats():
    """Statistiques du cache"""
    now = datetime.now()
    valid_entries = sum(
        1 for item in request_cache.values() 
        if now - item["timestamp"] < CACHE_DURATION
    )
    
    return {
        "total_entries": len(request_cache),
        "valid_entries": valid_entries,
        "cache_duration_minutes": CACHE_DURATION.total_seconds() / 60,
        "hit_rate": "Non disponible"  # Nécessiterait un tracking additionnel
    }

@app.delete("/cache/clear")
def clear_cache(api_key: str = Depends(get_api_key)):
    """Vide le cache (nécessite authentification)"""
    request_cache.clear()
    return {"message": "Cache vidé", "timestamp": datetime.now().isoformat()}

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Gestionnaire d'erreurs HTTP enrichi"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.now().isoformat(),
            "path": str(request.url)
        }
    )

# Nettoyage périodique du cache
@app.on_event("startup")
async def startup_event():
    """Initialisation au démarrage"""
    logger.info("🚀 Assistant IA Cabinet Dentaire démarré")
    logger.info(f"Configuration API: {'✅' if API_URL and API_KEY else '❌'}")
    
    # Démarrer le nettoyage périodique du cache
    asyncio.create_task(periodic_cache_cleanup())

async def periodic_cache_cleanup():
    """Nettoyage périodique du cache"""
    while True:
        try:
            await asyncio.sleep(1800)  # 30 minutes
            now = datetime.now()
            expired_keys = [
                key for key, item in request_cache.items()
                if now - item["timestamp"] > CACHE_DURATION
            ]
            
            for key in expired_keys:
                del request_cache[key]
            
            if expired_keys:
                logger.info(f"Cache nettoyé: {len(expired_keys)} entrées supprimées")
                
        except Exception as e:
            logger.error(f"Erreur lors du nettoyage du cache: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    
    logger.info("🏥 Démarrage du serveur Assistant IA Cabinet Dentaire...")
    logger.info(f"API URL: {'✅ Configurée' if API_URL else '❌ Manquante'}")
    logger.info(f"API KEY: {'✅ Configurée' if API_KEY else '❌ Manquante'}")
    logger.info(f"Hosts autorisés: {ALLOWED_HOSTS}")
    
    uvicorn.run(
        app, 
        host="0.0.0.0",  # Écoute sur toutes les interfaces
        port=8000,
        log_level="info",
        reload=True,
        access_log=True
    )