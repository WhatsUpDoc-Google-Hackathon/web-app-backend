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
    """Configuration optimized for multimodal models"""
    
    def __init__(self, config_dict: Dict[str, Any]):
        """
        Initialize model configuration
        
        Args:
            config_dict: Dictionary containing model configuration parameters
        """
        self.model_id = config_dict["model_id"]
        self.model_type = config_dict["model_type"]
        self.endpoint_id = config_dict["endpoint_id"]
        self.region = config_dict.get("region")
        self.display_name = config_dict.get("display_name", self.model_id)
        
        # Multimodal capabilities
        self.supports_images = config_dict.get("supports_images", False)
        self.max_images_per_request = config_dict.get("max_images_per_request", 1)
        self.supported_image_formats = config_dict.get("supported_image_formats", ["jpeg", "png", "webp"])
        self.max_image_size_mb = config_dict.get("max_image_size_mb", 20)
        
        # Default parameters
        self.default_params = config_dict.get("default_params", {})
        self.max_tokens = self.default_params.get("max_tokens", 1000)
        self.temperature = self.default_params.get("temperature", 0.0)
        
        # System configuration
        self.system_instruction = config_dict.get("system_instruction", "")
        self.enabled = config_dict.get("enabled", True)

class VertexClient:
    """Vertex AI client specialized for multimodal inputs (text + images)"""
    
    def __init__(
        self,
        config_path: Optional[str] = None,
        config_dict: Optional[Dict[str, Any]] = None,
        project_id: Optional[str] = None,
        default_region: str = "europe-west4",
        auto_initialize: bool = True,
    ):
        """
        Initialize Vertex AI client
        
        Args:
            config_path: Path to JSON configuration file
            config_dict: Configuration dictionary (overrides config_path)
            project_id: Google Cloud project ID
            default_region: Default region for Vertex AI
            auto_initialize: Whether to initialize connections automatically
        """
        self.project_id = project_id
        self.default_region = default_region
        self.models: Dict[str, VertexModelConfig] = {}
        self.endpoints: Dict[str, aiplatform.Endpoint] = {}
        self.connected = False
        
        # Load configuration
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
        """Load multimodal configuration from file or dictionary"""
        if config_dict:
            return config_dict
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            raise
        
    
    def _apply_global_config(self):
        """Apply global configuration settings"""
        vertex_config = self.config.get("vertex_ai", {})
        
        if not self.project_id:
            self.project_id = vertex_config.get("project_id")
        
        if "default_region" in vertex_config:
            self.default_region = vertex_config["default_region"]
    
    def _initialize_vertex_ai(self):
        """Initialize Vertex AI connection"""
        try:
            aiplatform.init(project=self.project_id, location=self.default_region)
            self.connected = True
            logger.info(f"Vertex AI initialized for multimodal inputs")
        except Exception as e:
            logger.error(f"Error during initialization: {e}")
            raise
    
    def _load_models(self):
        """Load multimodal models and their endpoints"""
        models_config = self.config.get("models", {})
        
        for model_id, model_config in models_config.items():
            try:
                model_config["model_id"] = model_id
                model_config["region"] = self.default_region
                vertex_model = VertexModelConfig(model_config)
                
                if not vertex_model.enabled:
                    continue
                
                # Build full endpoint name for dedicated endpoints
                if vertex_model.endpoint_id.startswith("projects/"):
                    # endpoint_id is already a full resource name
                    endpoint_name = vertex_model.endpoint_id
                else:
                    # Build full endpoint name
                    endpoint_name = f"projects/{self.project_id}/locations/{vertex_model.region}/endpoints/{vertex_model.endpoint_id}"
                endpoint = aiplatform.Endpoint(
                    endpoint_name=endpoint_name,
                    project=self.project_id,
                    location=vertex_model.region,
                )
                
                self.models[model_id] = vertex_model
                self.endpoints[model_id] = endpoint
                
                logger.info(f"Multimodal model {model_id} loaded with endpoint: {endpoint_name}")
                
            except Exception as e:
                logger.error(f"Error loading model {model_id}: {e}")
                raise
    
    def _encode_image(self, image_input: Union[str, bytes]) -> str:
        """
        Encode image to base64 string
        
        Args:
            image_input: File path (str) or binary data (bytes)
            
        Returns:
            str: Base64 encoded image
        """
        if isinstance(image_input, str):
            # File path
            with open(image_input, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        elif isinstance(image_input, bytes):
            # Binary data
            return base64.b64encode(image_input).decode("utf-8")
        else:
            raise ValueError("image_input must be a file path (str) or binary data (bytes)")
    
    def _get_image_mime_type(self, image_path: str) -> str:
        """Determine MIME type of an image based on file extension"""
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
        Multimodal prediction with text and images as input
        
        Args:
            model_id: Model ID to use
            text_prompt: Text prompt
            images: List of images (file paths or binary data)
            system_instruction: Custom system instruction
            **kwargs: Additional parameters (max_tokens, temperature, etc.)
            
        Returns:
            Dict containing prediction results or None if error
        """
        model_config = self.models[model_id]
        endpoint = self.endpoints[model_id]
        
        # Validate image support
        if not model_config.supports_images and images:
            logger.error(f"Model {model_id} does not support images")
            return None
        
        try:
            # Prepare system instruction
            sys_instruction = system_instruction or model_config.system_instruction
            
            # Generation parameters
            generation_params = {
                "max_tokens": kwargs.get("max_tokens", model_config.max_tokens),
                "temperature": kwargs.get("temperature", model_config.temperature),
                "top_p": kwargs.get("top_p", 1.0),
            }
            
            # Build request based on model type
            if model_config.supports_images:
                # Multimodal model - use content/parts structure
                content_parts = []
                
                # Add system instruction and prompt
                if sys_instruction:
                    full_prompt = f"{sys_instruction}\n\n{text_prompt}"
                else:
                    full_prompt = text_prompt
                
                # Add images if present
                if images:
                    # Check image count limit
                    if len(images) > model_config.max_images_per_request:
                        logger.warning(f"Too many images ({len(images)}), limit: {model_config.max_images_per_request}")
                        images = images[:model_config.max_images_per_request]
                    
                    # Process each image
                    for i, image in enumerate(images):
                        try:
                            # Encode image
                            image_base64 = self._encode_image(image)
                            
                            # Determine MIME type
                            if isinstance(image, str):
                                mime_type = self._get_image_mime_type(image)
                            else:
                                mime_type = "image/jpeg"  # Default for binary data
                            
                            # Add to parts list
                            content_parts.append({
                                "inline_data": {
                                    "mime_type": mime_type,
                                    "data": image_base64
                                }
                            })
                            
                        except Exception as e:
                            logger.error(f"Error processing image {i}: {e}")
                            continue
                
                # Add text last
                content_parts.append({"text": full_prompt})
                
                # Build multimodal request
                instances = [{
                    "content": {
                        "parts": content_parts
                    },
                    **generation_params
                }]
                
                logger.info(f"Multimodal prediction: {len(content_parts)} parts ({len(images or [])} images)")
                
            else:
                # Text-only model - use prompt structure
                if sys_instruction:
                    full_prompt = f"{sys_instruction}\n\n{text_prompt}"
                else:
                    full_prompt = text_prompt
                
                # Build text request
                instances = [{
                    "prompt": full_prompt,
                    **generation_params
                }]
                
                logger.info(f"Text prediction for model {model_id}")
            
            # Make prediction
            response = endpoint.predict(instances=instances)
            
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
            logger.error(f"Error during multimodal prediction: {e}")
            return {
                "prediction": None,
                "model_id": model_id,
                "error": str(e),
                "success": False,
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            }
    
    def _determine_input_type(self, text: str, images: Optional[List]) -> str:
        """Determine the type of input used for the prediction"""
        has_text = bool(text and text.strip())
        has_images = bool(images and len(images) > 0)
        
        if has_text and has_images:
            return "text_and_images" if len(images) == 1 else "text_and_multiple_images"
        elif has_text:
            return "text"
        elif has_images:
            return "images"
        return "unknown"