import logging
import json
import google.auth
from google.auth.transport import requests
from typing import List, Dict, Any, Optional
import openai
import datetime
from utils.custom_types import ChatMessage

logger = logging.getLogger(__name__)


class VertexModelConfig:
    """Configuration for OpenAI-compatible Vertex AI models"""

    def __init__(self, config_dict: Dict[str, Any]):
        """
        Initialize model configuration

        Args:
            config_dict: Dictionary containing model configuration parameters
        """
        self.model_id = config_dict["model_id"]
        self.model_type = config_dict["model_type"]
        self.endpoint_id = config_dict["endpoint_id"]
        self.region = config_dict.get("region", "europe-west4")
        self.display_name = config_dict.get("display_name", self.model_id)
        self.openai_model_name = config_dict.get("openai_model_name", "gemma-4b-it")

        # Default parameters
        self.default_params = config_dict.get("default_params", {})
        self.max_tokens = self.default_params.get("max_tokens", 800)
        self.temperature = self.default_params.get("temperature", 0.0)

        # System configuration
        self.system_instruction = config_dict.get("system_instruction", "")
        self.enabled = config_dict.get("enabled", True)


class VertexClient:
    """Vertex AI client using OpenAI compatibility layer"""

    def __init__(
        self,
        config_path: Optional[str] = None,
        config_dict: Optional[Dict[str, Any]] = None,
        project_id: Optional[str] = None,
        default_region: str = "europe-west4",
        auto_initialize: bool = True,
    ):
        """
        Initialize Vertex AI client with OpenAI compatibility

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
        self.clients: Dict[str, openai.OpenAI] = {}
        self.connected = False

        # Load configuration
        self.config = self._load_configuration(config_path, config_dict)
        self._apply_global_config()

        # Get default credentials
        self.creds, self.project_id = google.auth.default()

        if auto_initialize:
            self._initialize_auth()
            self._load_models()

    def _load_configuration(
        self, config_path: Optional[str], config_dict: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Load configuration from file or dictionary"""
        if config_dict:
            return config_dict

        try:
            with open(config_path, "r", encoding="utf-8") as f:
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

    def _initialize_auth(self):
        """Initialize authentication"""
        try:
            auth_req = requests.Request()
            self.creds.refresh(auth_req)
            self.connected = True
            logger.info("Authentication initialized successfully")
        except Exception as e:
            logger.error(f"Error during authentication: {e}")
            raise

    def _load_models(self):
        """Load models and create OpenAI clients"""
        models_config = self.config.get("models", {})

        for model_id, model_config in models_config.items():
            try:
                model_config["model_id"] = model_id
                model_config["region"] = self.default_region
                vertex_model = VertexModelConfig(model_config)

                if not vertex_model.enabled:
                    continue

                # Build endpoint name
                endpoint_name = f"projects/{self.project_id}/locations/{vertex_model.region}/endpoints/{vertex_model.endpoint_id}"
                base_url = f"https://{vertex_model.region}-aiplatform.googleapis.com/v1beta1/{endpoint_name}"

                # Create OpenAI client for this model
                client = openai.OpenAI(
                    base_url=base_url,
                    api_key=self.creds.token,
                )

                self.models[model_id] = vertex_model
                self.clients[model_id] = client

                logger.info(
                    f"Model {model_id} loaded with endpoint: {vertex_model.endpoint_id}"
                )

            except Exception as e:
                logger.error(f"Error loading model {model_id}: {e}")
                raise

    def predict(
        self,
        conversation_history: List[ChatMessage],
        model_id: Optional[str] = None,
        **kwargs,
    ) -> Optional[Dict[str, Any]]:
        """
        Make a prediction using conversation history

        Args:
            conversation_history: List of chat messages in OpenAI format
            model_id: Model ID to use (uses first available if None)
            **kwargs: Additional parameters (max_tokens, temperature, etc.)

        Returns:
            Dict containing prediction results or None if error
        """
        # Get available models
        available_models = list(self.models.keys())
        if not available_models:
            logger.error("No models available")
            return None

        # Use specified model or first available
        target_model_id = model_id or available_models[0]

        if target_model_id not in self.models:
            logger.error(f"Model {target_model_id} not found")
            return None

        model_config = self.models[target_model_id]
        client = self.clients[target_model_id]

        # Refresh token if needed
        if not self.creds.valid:
            auth_req = google.auth.transport.requests.Request()
            self.creds.refresh(auth_req)
            client.api_key = self.creds.token

        try:
            # Prepare messages
            messages = conversation_history.copy()

            # Add system instruction at the beginning if provided
            if model_config.system_instruction:
                sys_msg = model_config.system_instruction
                if model_config.model_type == "gemma_4b":
                    messages.insert(
                        0,
                        {
                            "role": "system",
                            "content": "Enhanced Medical AI System Prompt for Emma\n\nCore Identity & Architecture\nEmma is a warm, concise digital cardiologist assistant powered by MedGemma 4B-IT - Google's specialized medical AI model with demonstrated expertise in:\n- Medical text comprehension (89.8% accuracy on MedQA benchmark)\n- Cardiovascular disease detection (66.4% accuracy, 39-point improvement over baseline)\n- Clinical reasoning and patient triage capabilities\n- Multimodal medical understanding (text + image processing)\n\nPre-trained Medical Capabilities\nClinical Knowledge Base:\n- Trained on 22+ medical datasets across 5 clinical tasks\n- Chest X-ray analysis (88.9% F1 score on MIMIC-CXR)\n- Cardiovascular risk assessment from patient data\n- Medical text interpretation and clinical reasoning\n- Patient symptom analysis and triage recommendations\n\nSpecialized Training:\n- De-identified medical imaging data (chest X-rays, dermatology, ophthalmology, histopathology)\n- Clinical text and medical literature\n- Patient-physician interaction patterns\n- Evidence-based medical decision making\n\nOperational Framework\nCommunication Protocol\n- Style: Warm, nurse-like, ≤2 sentences per response\n- Language: Everyday terms, define medical concepts simply\n- Empathy: Always acknowledge patient concerns (\"I understand that can feel worrying\")\n- Precision: ONE clear question per turn, await response\n\nClinical Decision Tree (Priority Order)\n- Emergency Red Flags → Immediate escalation with ref R69-073\n- Heart Failure Indicators (EPOF) → Rapid cardiology referral\n- Symptom Characterization → Systematic assessment\n- Risk Stratification → Leveraging MedGemma's cardiovascular expertise\n- Care Pathway Assignment → Appointment/referral/emergency protocols\n\nTriage Protocols (MedGemma-Enhanced)\nChest Pain Assessment:\n- Rest pain >10min or intense → Emergency call (SAMU, ref R69-073)\n- Leveraging trained pattern recognition for cardiovascular risk factors\n- Exertional-only symptoms → Cardiology within 1 week\n\nHeart Failure Protocol (EPOF):\n- Dyspnea at rest/orthopnea → Emergency (SAMU, ref R69-073)\n- Any EPOF sign → Same/next day cardiology appointment\n- Utilize MedGemma's trained understanding of heart failure presentations\n\nRisk Stratification:\n- Apply MedGemma's cardiovascular disease prediction capabilities\n- Consider: age, cardiac history, medications, comorbidities\n- Integrate clinical reasoning with patient-reported symptoms\n\nCritical Decision Points\nEscalation Triggers:\n- Any red-flag symptoms\n- Unclear severity assessment\n- High clinical uncertainty\n- Patient anxiety requiring immediate attention\n\nVERY IMPORTANTS Output Protocols:\n- End of pre diagnosis questions: <<END_OF_CONVERSTATION>>\n- Emergency situations: <<EMERGENCY>> (same token, immediate escalation)\n\nQuality Assurance\nProhibited Actions:\n- Formal diagnoses or prescriptions\n- Speculation beyond clinical evidence\n- Excessive/irrelevant questioning\n- Contradicting patient preferences\n\nEnhanced Capabilities:\n- Leverage MedGemma's 66.4% accuracy in cardiovascular risk assessment\n- Apply evidence-based clinical reasoning from medical literature training\n- Utilize multimodal understanding for comprehensive patient evaluation\n\nInteraction Workflow\n- Warm greeting + chief complaint identification\n- Systematic questioning guided by MedGemma's clinical training\n- Risk assessment using cardiovascular disease detection capabilities\n- Care pathway determination (appointment/referral/emergency)\n- Patient education + next steps + final questions\n- Conversation closure with appropriate follow-up instructions\n\nClinical Foundation: Built on MedGemma's proven performance across medical benchmarks, specialized cardiovascular disease detection, and evidence-based clinical reasoning to provide accurate, empathetic, and efficient cardiac triage.",
                        },
                    )
                else:
                    messages.insert(0, {"role": "system", "content": sys_msg})

            # Generation parameters
            generation_params = {
                "model": model_config.openai_model_name,
                "messages": messages,
                "temperature": kwargs.get("temperature", model_config.temperature),
                "max_tokens": kwargs.get("max_tokens", model_config.max_tokens),
            }

            logger.info(f"Making prediction with {messages} messages")

            # Make prediction
            response = client.chat.completions.create(**generation_params)

            logger.info(f"Response: {response}")

            # Extract generated text
            generated_text = None
            if not response:
                logger.error("No response from model")
                return {
                    "prediction": None,
                    "generated_text": None,
                    "model_id": target_model_id,
                    "error": "No response from model",
                    "success": False,
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                }
            elif response.choices:
                # Handle both object-style and dictionary-style responses
                message = response.choices[0].message
                if hasattr(message, "content"):
                    generated_text = message.content
                elif isinstance(message, dict) and "content" in message:
                    generated_text = message["content"]
                else:
                    logger.error(f"Could not extract content from message: {message}")
                    raise Exception("Message format not recognized")
            else:
                raise Exception("No choices returned from model")

            return {
                "prediction": (
                    response.model_dump()
                    if hasattr(response, "model_dump")
                    else dict(response)
                ),
                "generated_text": generated_text,
                "model_id": target_model_id,
                "model_type": model_config.model_type,
                "input_type": "chat_messages",
                "messages_count": len(messages),
                "success": True,
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            }

        except Exception as e:
            logger.error(f"Error during prediction: {e}")
            return {
                "prediction": None,
                "generated_text": None,
                "model_id": target_model_id,
                "error": str(e),
                "success": False,
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            }

    def generate_report(
        self, conversation_history: List[ChatMessage]
    ) -> Dict[str, Any]:
        """
        Generate a report for a conversation

        Args:
            conversation_history: List of chat messages in OpenAI format
            model_id: Model ID to use (uses first available if None)

        Returns:
            Dict containing report results or None if error
        """
        # Use the 27b model for report generation
        return self.predict(conversation_history, model_id="gemma_27b")

    def health_check(self) -> Dict[str, Any]:
        """Check if the client is healthy"""
        health_status = {
            "status": "unknown",
            "connected": self.connected,
            "project_id": self.project_id,
            "region": self.default_region,
            "models_loaded": len(self.models),
            "error": None,
        }

        if not self.connected:
            health_status["status"] = "unhealthy"
            health_status["error"] = "Not connected"
            return health_status

        # Test with first available model
        available_models = list(self.models.keys())
        if not available_models:
            health_status["status"] = "unhealthy"
            health_status["error"] = "No models available"
            return health_status

        try:
            # Test connection with a simple message
            test_messages = [{"role": "user", "content": "Test connection"}]
            result = self.predict(test_messages, max_tokens=10)

            if result and result.get("success"):
                health_status["status"] = "healthy"
            else:
                health_status["status"] = "unhealthy"
                health_status["error"] = (
                    result.get("error", "Unknown error") if result else "No response"
                )

        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["error"] = str(e)

        return health_status

    def get_model_info(self, model_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific model

        Args:
            model_id: Model ID to get info for

        Returns:
            Dict containing model information or None if not found
        """
        if model_id not in self.models:
            return None

        model_config = self.models[model_id]
        return {
            "model_id": model_config.model_id,
            "model_type": model_config.model_type,
            "openai_model_name": model_config.openai_model_name,
            "max_tokens": model_config.max_tokens,
            "temperature": model_config.temperature,
            "enabled": model_config.enabled,
            "region": model_config.region,
            "endpoint_id": model_config.endpoint_id,
        }

    def list_models(self) -> List[str]:
        """Get list of available model IDs"""
        return list(self.models.keys())
