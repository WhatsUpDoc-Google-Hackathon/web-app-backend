import logging
import os
import json
import base64
from typing import List, Dict, Any, Optional, Union
from google.cloud import aiplatform
from enum import Enum
import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class VertexModelConfig:
    """Configuration optimisée pour modèles multimodaux"""
    
    def __init__(self, config_dict: Dict[str, Any]):
        self.model_id = config_dict["model_id"]
        self.model_type = config_dict["model_type"]
        self.endpoint_id = config_dict["endpoint_id"]
        self.region = config_dict.get("region")
        self.display_name = config_dict.get("display_name", self.model_id)
        
        # Capacités multimodales
        self.supports_images = config_dict.get("supports_images", False)
        self.max_images_per_request = config_dict.get("max_images_per_request", 1)
        self.supported_image_formats = config_dict.get("supported_image_formats", ["jpeg", "png", "webp"])
        self.max_image_size_mb = config_dict.get("max_image_size_mb", 20)
        
        # Paramètres par défaut
        self.default_params = config_dict.get("default_params", {})
        self.max_tokens = self.default_params.get("max_tokens", 1000)
        self.temperature = self.default_params.get("temperature", 0.0)
        
        # Configuration système
        self.system_instruction = config_dict.get("system_instruction", "")
        self.use_dedicated_endpoint = config_dict.get("use_dedicated_endpoint", True)
        self.enabled = config_dict.get("enabled", True)

class VertexClient:
    """Client Vertex AI spécialisé pour entrées multimodales (texte + images)"""
    
    def __init__(
        self,
        config_path: Optional[str] = None,
        config_dict: Optional[Dict[str, Any]] = None,
        project_id: Optional[str] = None,
        default_region: str = "europe-west4",
        auto_initialize: bool = True,
    ):
        self.project_id = project_id
        self.default_region = default_region
        self.models: Dict[str, VertexModelConfig] = {}
        self.endpoints: Dict[str, aiplatform.Endpoint] = {}
        self.connected = False
        
        # Charger la configuration
        self.config = self._load_configuration(config_path, config_dict)
        self._apply_global_config()
        
        if auto_initialize:
            self._initialize_vertex_ai()
            self._load_models()
    
    def _load_configuration(
        self, 
        config_path: Optional[str], 
        config_dict: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Charge la configuration multimodale"""
        if config_dict:
            return config_dict
        
        if config_path:
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Erreur lors du chargement de la configuration: {e}")
                raise
        
        return self._get_default_multimodal_config()
    
    def _get_default_multimodal_config(self) -> Dict[str, Any]:
        """Configuration par défaut optimisée pour le multimodal"""
        return {
            "vertex_ai": {
                "project_id": os.environ.get("GOOGLE_CLOUD_PROJECT"),
                "default_region": "europe-west4"
            },
            "models": {
                "gemini_vision": {
                    "model_type": "gemini-pro-vision",
                    "endpoint_id": "your-gemini-vision-endpoint",
                    "supports_images": True,
                    "max_images_per_request": 16,
                    "supported_image_formats": ["jpeg", "png", "webp", "heic"],
                    "system_instruction": "Tu es un expert en analyse multimodale. Analyse le texte et les images fournis.",
                    "default_params": {
                        "max_tokens": 2048,
                        "temperature": 0.0
                    }
                }
            }
        }
    
    def _apply_global_config(self):
        """Applique la configuration globale"""
        vertex_config = self.config.get("vertex_ai", {})
        
        if not self.project_id:
            self.project_id = (
                vertex_config.get("project_id")
            )
        
        if "default_region" in vertex_config:
            self.default_region = vertex_config["default_region"]
    
    def _initialize_vertex_ai(self):
        """Initialise Vertex AI"""
        try:
            aiplatform.init(project=self.project_id, location=self.default_region)
            self.connected = True
            logger.info(f"Vertex AI initialisé pour les entrées multimodales")
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation: {e}")
            raise
    
    def _load_models(self):
        """Charge les modèles multimodaux"""
        models_config = self.config.get("models", {})
        
        for model_id, model_config in models_config.items():
            try:
                model_config["model_id"] = model_id
                model_config["region"] = self.default_region
                vertex_model = VertexModelConfig(model_config)
                
                if not vertex_model.enabled:
                    continue
                
                endpoint = aiplatform.Endpoint(
                    endpoint_name=vertex_model.endpoint_id,
                    project=self.project_id,
                    location=vertex_model.region,
                )
                
                self.models[model_id] = vertex_model
                self.endpoints[model_id] = endpoint
                
                logger.info(f"Modèle multimodal {model_id} chargé")
                
            except Exception as e:
                logger.error(f"Erreur lors du chargement du modèle {model_id}: {e}")
                raise
    
    def _encode_image(self, image_input: Union[str, bytes]) -> str:
        """Encode une image en base64"""
        if isinstance(image_input, str):
            # Chemin vers fichier
            with open(image_input, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        elif isinstance(image_input, bytes):
            # Données binaires
            return base64.b64encode(image_input).decode("utf-8")
        else:
            raise ValueError("image_input doit être un chemin (str) ou des données (bytes)")
    
    def _get_image_mime_type(self, image_path: str) -> str:
        """Détermine le type MIME d'une image"""
        extension = Path(image_path).suffix.lower()
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg', 
            '.png': 'image/png',
            '.webp': 'image/webp',
            '.heic': 'image/heic',
            '.heif': 'image/heif'
        }
        return mime_types.get(extension, 'image/jpeg')
    
    def predict(
        self,
        model_id: str,
        text_prompt: str,
        images: Optional[List[Union[str, bytes]]] = None,
        system_instruction: Optional[str] = None,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Prédiction multimodale avec texte et images en entrée
        
        Args:
            model_id: ID du modèle à utiliser
            text_prompt: Prompt textuel
            images: Liste d'images (chemins de fichiers ou données binaires)
            system_instruction: Instruction système personnalisée
            **kwargs: Paramètres supplémentaires (max_tokens, temperature, etc.)
        """
        if not self._validate_model(model_id):
            return None
        
        model_config = self.models[model_id]
        endpoint = self.endpoints[model_id]
        
        if not model_config.supports_images and images:
            logger.error(f"Le modèle {model_id} ne supporte pas les images")
            return None
        
        try:
            # Préparer l'instruction système
            sys_instruction = system_instruction or model_config.system_instruction
            
            # Construire les parts de contenu
            content_parts = []
            
            # Ajouter l'instruction système et le prompt
            if sys_instruction:
                full_prompt = f"{sys_instruction}\n\n{text_prompt}"
            else:
                full_prompt = text_prompt
            
            # Ajouter les images si présentes
            if images:
                # Vérifier le nombre d'images
                if len(images) > model_config.max_images_per_request:
                    logger.warning(f"Trop d'images ({len(images)}), limite: {model_config.max_images_per_request}")
                    images = images[:model_config.max_images_per_request]
                
                # Traiter chaque image
                for i, image in enumerate(images):
                    try:
                        # Encoder l'image
                        image_base64 = self._encode_image(image)
                        
                        # Déterminer le type MIME
                        if isinstance(image, str):
                            mime_type = self._get_image_mime_type(image)
                        else:
                            mime_type = "image/jpeg"  # Défaut pour données binaires
                        
                        # Ajouter à la liste des parts
                        content_parts.append({
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": image_base64
                            }
                        })
                        
                    except Exception as e:
                        logger.error(f"Erreur lors du traitement de l'image {i}: {e}")
                        continue
            
            # Ajouter le texte en dernier
            content_parts.append({"text": full_prompt})
            
            # Paramètres de génération
            generation_params = {
                "max_tokens": kwargs.get("max_tokens", model_config.max_tokens),
                "temperature": kwargs.get("temperature", model_config.temperature),
                "top_p": kwargs.get("top_p", 1.0),
                "raw_response": kwargs.get("raw_response", True),
            }
            
            # Construire la requête
            instances = [{
                "content": {
                    "parts": content_parts
                },
                **generation_params
            }]
            
            logger.info(f"Prédiction multimodale: {len(content_parts)} parts ({len(images or [])} images)")
            
            # Faire la prédiction
            response = endpoint.predict(
                instances=instances,
                use_dedicated_endpoint=model_config.use_dedicated_endpoint
            )
            
            prediction = response.predictions[0] if response.predictions else None
            
            return {
                "prediction": prediction,
                "model_id": model_id,
                "model_type": model_config.model_type,
                "input_type": self._determine_input_type(text_prompt, images),
                "images_count": len(images) if images else 0,
                "text_prompt": text_prompt,
                "success": True,
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la prédiction multimodale: {e}")
            return {
                "prediction": None,
                "model_id": model_id,
                "error": str(e),
                "success": False,
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            }
    
    def _determine_input_type(self, text: str, images: Optional[List]) -> str:
        """Détermine le type d'entrée utilisé"""
        has_text = bool(text and text.strip())
        has_images = bool(images and len(images) > 0)
        
        if has_text and has_images:
            return "text_and_images" if len(images) == 1 else "text_and_multiple_images"
        elif has_text:
            return "text"
        elif has_images:
            return "images"
        return "unknown"