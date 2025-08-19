import json
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime

# Configuration du logger
logger = logging.getLogger(__name__)

class ActionManager:
    """Gestionnaire des actions et prompts système avec fonctionnalités avancées"""
    
    def __init__(self, config_file: str = "actions.json", enable_cache: bool = True):
        self.config_file = config_file
        self.actions = {}
        self.metadata = {}
        self.last_modified = None
        self.enable_cache = enable_cache
        self._load_actions()
    
    def _get_config_path(self) -> Path:
        """Retourne le chemin complet vers le fichier de configuration"""
        current_dir = Path(__file__).parent
        return current_dir / self.config_file
    
    def _validate_config_structure(self, data: Dict[str, Any]) -> bool:
        """Valide la structure du fichier de configuration"""
        try:
            if "response_modes" not in data:
                logger.error("Structure invalide : 'response_modes' manquant")
                return False
            
            required_fields = ["name", "instruction"]
            for key, value in data["response_modes"].items():
                if not isinstance(value, dict):
                    logger.error(f"Action '{key}' doit être un objet")
                    return False
                
                for field in required_fields:
                    if field not in value:
                        logger.error(f"Action '{key}' manque le champ requis : {field}")
                        return False
            
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la validation : {str(e)}")
            return False
    
    def _load_actions(self) -> None:
        """Charge les actions depuis le fichier JSON avec validation"""
        config_path = self._get_config_path()
        
        try:
            if config_path.exists():
                current_modified = config_path.stat().st_mtime
                
                # Vérifier le cache si activé
                if (self.enable_cache and 
                    self.last_modified is not None and 
                    current_modified <= self.last_modified):
                    return
                
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # Validation de la structure
                if not self._validate_config_structure(data):
                    logger.error("Configuration invalide, utilisation des valeurs par défaut")
                    self._load_default_actions()
                    return
                
                # Chargement des actions validées
                self.actions = {}
                self.metadata = {}
                
                for key, value in data["response_modes"].items():
                    self.actions[key] = value["instruction"]
                    self.metadata[key] = {
                        "name": value.get("name", key),
                        "max_length": value.get("max_length"),
                        "format": value.get("format", "conversational"),
                        "description": value.get("description", "")
                    }
                
                self.last_modified = current_modified
                logger.info(f"Actions chargées depuis {config_path} ({len(self.actions)} actions)")
                
            else:
                logger.warning(f"Fichier de configuration {config_path} non trouvé")
                self._load_default_actions()
                self._create_default_config_file(config_path)
                
        except json.JSONDecodeError as e:
            logger.error(f"Erreur JSON dans {config_path}: {str(e)}")
            self._load_default_actions()
        except Exception as e:
            logger.error(f"Erreur lors du chargement: {str(e)}")
            self._load_default_actions()
    
    def _load_default_actions(self) -> None:
        """Charge les actions par défaut"""
        self.actions = {
            "default": "Tu es un assistant IA professionnel spécialisé dans la gestion de cabinet dentaire. Réponds de manière précise, claire et structurée.",
            "resume": "Résume le texte suivant en 5 points clés concis et clairs. Concentre-toi sur les informations essentielles.",
            "explain": "Explique le concept suivant comme si tu enseignais à un débutant dans le domaine dentaire. Utilise un langage simple et des exemples pratiques.",
            "translate_fr": "Traduis le texte suivant en français avec un ton formel et professionnel médical.",
            "translate_en": "Traduis le texte suivant en anglais avec un ton formel et professionnel médical.",
            "short": "Fournis une réponse directe et professionnelle en maximum 2 phrases concises.",
            "long": "Fournis une réponse détaillée, structurée et bien organisée avec des exemples pertinents au domaine dentaire.",
            "dental_diagnosis": "Tu es un assistant spécialisé en diagnostic dentaire. Analyse les informations et aide au diagnostic en rappelant que tes suggestions ne remplacent pas l'expertise d'un dentiste qualifié.",
            "appointment_scheduler": "Tu es un assistant spécialisé dans la gestion des rendez-vous dentaires. Aide à organiser et planifier les créneaux de consultation.",
            "treatment_plan": "Tu es un assistant pour l'élaboration de plans de traitement dentaire. Aide à structurer les étapes de soins selon les protocoles dentaires."
        }
        
        # Métadonnées par défaut
        self.metadata = {key: {"name": key.title(), "format": "conversational"} 
                        for key in self.actions.keys()}
        
        logger.info(f"Actions par défaut chargées ({len(self.actions)} actions)")
    
    def _create_default_config_file(self, config_path: Path) -> None:
        """Crée un fichier de configuration par défaut"""
        try:
            default_config = self._generate_default_config()
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(default_config, f, ensure_ascii=False, indent=2)
            logger.info(f"Fichier de configuration par défaut créé : {config_path}")
        except Exception as e:
            logger.error(f"Impossible de créer le fichier de configuration : {str(e)}")
    
    def _generate_default_config(self) -> Dict[str, Any]:
        """Génère la configuration par défaut"""
        return {
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
                    "instruction": "Tu es un assistant spécialisé en diagnostic dentaire. Analyse les informations et aide au diagnostic en rappelant que tes suggestions ne remplacent pas l'expertise d'un dentiste qualifié.",
                    "format": "medical_analysis",
                    "description": "Assistance pour le diagnostic dentaire"
                }
            },
            "default_settings": {
                "language": "fr",
                "tone": "professional",
                "domain": "dental_medicine",
                "medical_disclaimer": "Les informations fournies sont à titre informatif et ne remplacent pas l'avis d'un professionnel de santé qualifié.",
                "created_at": datetime.now().isoformat(),
                "version": "1.0.0"
            }
        }
    
    def get_system_prompt(self, action: str) -> str:
        """Retourne le prompt système pour une action donnée"""
        self._load_actions()
        
        if action in self.actions:
            prompt = self.actions[action]
            logger.debug(f"Prompt récupéré pour l'action '{action}'")
            return prompt
        else:
            # Recherche fuzzy pour les erreurs de frappe
            similar_actions = self._find_similar_actions(action)
            if similar_actions:
                logger.warning(f"Action '{action}' non trouvée. Actions similaires : {similar_actions}")
            else:
                logger.warning(f"Action '{action}' non trouvée, utilisation du mode par défaut")
            return self.actions.get("default", "Tu es un assistant IA professionnel.")
    
    def _find_similar_actions(self, action: str, threshold: int = 2) -> List[str]:
        """Trouve des actions similaires pour les erreurs de frappe"""
        def levenshtein_distance(s1: str, s2: str) -> int:
            if len(s1) < len(s2):
                return levenshtein_distance(s2, s1)
            if len(s2) == 0:
                return len(s1)
            
            previous_row = list(range(len(s2) + 1))
            for i, c1 in enumerate(s1):
                current_row = [i + 1]
                for j, c2 in enumerate(s2):
                    insertions = previous_row[j + 1] + 1
                    deletions = current_row[j] + 1
                    substitutions = previous_row[j] + (c1 != c2)
                    current_row.append(min(insertions, deletions, substitutions))
                previous_row = current_row
            return previous_row[-1]
        
        similar = []
        for existing_action in self.actions.keys():
            distance = levenshtein_distance(action.lower(), existing_action.lower())
            if distance <= threshold:
                similar.append(existing_action)
        
        return similar
    
    def get_action_metadata(self, action: str) -> Optional[Dict[str, Any]]:
        """Retourne les métadonnées d'une action"""
        self._load_actions()
        return self.metadata.get(action)
    
    def get_all_actions(self) -> Dict[str, str]:
        """Retourne toutes les actions disponibles"""
        self._load_actions()
        return self.actions.copy()
    
    def get_actions_by_category(self) -> Dict[str, List[str]]:
        """Groupe les actions par catégorie basée sur leur nom"""
        categories = {
            "Traduction": [],
            "Analyse": [],
            "Communication": [],
            "Médical": [],
            "Général": []
        }
        
        for action in self.actions.keys():
            if "translate" in action:
                categories["Traduction"].append(action)
            elif any(word in action for word in ["analysis", "pdf", "image"]):
                categories["Analyse"].append(action)
            elif any(word in action for word in ["short", "long", "resume"]):
                categories["Communication"].append(action)
            elif any(word in action for word in ["dental", "diagnosis", "treatment", "appointment"]):
                categories["Médical"].append(action)
            else:
                categories["Général"].append(action)
        
        return {k: v for k, v in categories.items() if v}  # Retirer les catégories vides
    
    def action_exists(self, action: str) -> bool:
        """Vérifie si une action existe"""
        self._load_actions()
        return action in self.actions
    
    def get_action_description(self, action: str) -> Optional[str]:
        """Retourne une description de l'action"""
        metadata = self.get_action_metadata(action)
        if metadata and "description" in metadata:
            return metadata["description"]
        
        # Descriptions par défaut
        descriptions = {
            "default": "Assistant général pour cabinet dentaire",
            "resume": "Résumé en points clés",
            "explain": "Explication pédagogique",
            "translate_fr": "Traduction française professionnelle",
            "translate_en": "Traduction anglaise professionnelle",
            "short": "Réponse concise (2 phrases max)",
            "long": "Analyse détaillée et structurée",
            "pdf_analysis": "Analyse de documents PDF médicaux",
            "image_analysis": "Analyse d'images médicales/radiographies",
            "dental_diagnosis": "Assistance au diagnostic dentaire",
            "appointment_scheduler": "Gestion des rendez-vous",
            "treatment_plan": "Planification de traitements"
        }
        return descriptions.get(action, f"Action personnalisée: {action}")
    
    def add_custom_action(self, action_name: str, instruction: str, 
                         metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Ajoute une action personnalisée (en mémoire uniquement)"""
        try:
            self.actions[action_name] = instruction
            self.metadata[action_name] = metadata or {
                "name": action_name.title(),
                "format": "conversational",
                "description": "Action personnalisée ajoutée dynamiquement"
            }
            logger.info(f"Action personnalisée '{action_name}' ajoutée")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de l'ajout de l'action '{action_name}': {str(e)}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne des statistiques sur les actions"""
        self._load_actions()
        categories = self.get_actions_by_category()
        
        return {
            "total_actions": len(self.actions),
            "categories": {cat: len(actions) for cat, actions in categories.items()},
            "last_reload": datetime.fromtimestamp(self.last_modified).isoformat() if self.last_modified else None,
            "config_file": str(self._get_config_path()),
            "config_exists": self._get_config_path().exists()
        }

# Instance globale avec gestion d'erreur
try:
    _action_manager = ActionManager()
except Exception as e:
    logger.error(f"Erreur lors de l'initialisation d'ActionManager: {str(e)}")
    _action_manager = None

def get_system_prompt(action: str) -> str:
    """Fonction de compatibilité avec fallback robuste"""
    if _action_manager:
        return _action_manager.get_system_prompt(action)
    else:
        logger.warning("ActionManager non disponible, utilisation du prompt minimal")
        return "Tu es un assistant IA professionnel."

def get_all_actions() -> Dict[str, str]:
    """Fonction de compatibilité"""
    if _action_manager:
        return _action_manager.get_all_actions()
    return {"default": "Tu es un assistant IA professionnel."}

def get_actions_info() -> Dict[str, Any]:
    """Retourne des informations détaillées sur toutes les actions"""
    if not _action_manager:
        return {"error": "ActionManager non disponible"}
    
    actions_info = {}
    for action in _action_manager.get_all_actions().keys():
        actions_info[action] = {
            "description": _action_manager.get_action_description(action),
            "metadata": _action_manager.get_action_metadata(action),
            "prompt_length": len(_action_manager.get_system_prompt(action))
        }
    
    return {
        "actions": actions_info,
        "stats": _action_manager.get_stats(),
        "categories": _action_manager.get_actions_by_category()
    }