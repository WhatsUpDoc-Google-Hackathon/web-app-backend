import logging
import io
import base64
from typing import Dict, Any, Optional, List
from google.cloud import speech
import config

logger = logging.getLogger(__name__)


class STTClient:
    """Google Cloud Speech-to-Text client for audio transcription"""

    def __init__(
        self,
        project_id: Optional[str] = None,
        language_code: str = "en-US",
        auto_initialize: bool = True,
    ):
        """
        Initialize Speech-to-Text client

        Args:
            project_id: Google Cloud project ID
            language_code: Language code for transcription (default: en-US)
            auto_initialize: Whether to initialize the client automatically
        """
        self.project_id = project_id or config.GCP_PROJECT_ID
        self.language_code = language_code
        self.client = None
        self.connected = False

        # Supported audio formats and their configurations
        self.audio_configs = {
            "wav": {
                "encoding": speech.RecognitionConfig.AudioEncoding.LINEAR16,
                "sample_rate_hertz": 16000,
            },
            "webm": {
                "encoding": speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
                "sample_rate_hertz": 16000,
            },
            "ogg": {
                "encoding": speech.RecognitionConfig.AudioEncoding.OGG_OPUS,
                "sample_rate_hertz": 16000,
            },
            "m4a": {
                "encoding": speech.RecognitionConfig.AudioEncoding.LINEAR16,
                "sample_rate_hertz": 16000,
            },
        }

        if auto_initialize:
            self.initialize()

    def initialize(self):
        """Initialize the Speech-to-Text client"""
        try:
            self.client = speech.SpeechClient()
            self.connected = True
            logger.info("Google Cloud Speech-to-Text client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Speech-to-Text client: {e}")
            raise

    def transcribe_audio(
        self,
        audio_data: bytes,
        audio_format: str = "wav",
        language_code: Optional[str] = None,
        enable_automatic_punctuation: bool = True,
        enable_word_time_offsets: bool = False,
        model: str = "default",
    ) -> Dict[str, Any]:
        """
        Transcribe audio data to text

        Args:
            audio_data: Binary audio data
            audio_format: Audio format (wav, mp3, webm, ogg, m4a)
            language_code: Language code for transcription
            enable_automatic_punctuation: Whether to enable automatic punctuation
            enable_word_time_offsets: Whether to include word time offsets
            model: Speech recognition model to use

        Returns:
            Dict containing transcription results
        """
        if not self.connected:
            raise RuntimeError("Speech-to-Text client not initialized")

        try:
            # Get audio configuration
            audio_config = self.audio_configs.get(audio_format.lower())
            if not audio_config:
                raise ValueError(f"Unsupported audio format: {audio_format}")

            # Prepare audio for recognition
            audio = speech.RecognitionAudio(content=audio_data)

            # Configure recognition
            config = speech.RecognitionConfig(
                encoding=audio_config["encoding"],
                sample_rate_hertz=audio_config["sample_rate_hertz"],
                language_code=language_code or self.language_code,
                enable_automatic_punctuation=enable_automatic_punctuation,
                enable_word_time_offsets=enable_word_time_offsets,
                model=model,
            )

            # Perform the transcription
            response = self.client.recognize(config=config, audio=audio)

            # Process results
            transcriptions = []
            for result in response.results:
                alternative = result.alternatives[0]
                transcription = {
                    "transcript": alternative.transcript,
                    "confidence": alternative.confidence,
                }

                # Add word time offsets if requested
                if enable_word_time_offsets:
                    words = []
                    for word in alternative.words:
                        words.append(
                            {
                                "word": word.word,
                                "start_time": word.start_time.total_seconds(),
                                "end_time": word.end_time.total_seconds(),
                            }
                        )
                    transcription["words"] = words

                transcriptions.append(transcription)

            result = {
                "success": True,
                "transcriptions": transcriptions,
                "language_code": language_code or self.language_code,
                "audio_format": audio_format,
            }

            logger.info(f"Audio transcription completed successfully")
            return result

        except Exception as e:
            logger.error(f"Error during audio transcription: {e}")
            return {
                "success": False,
                "error": str(e),
                "transcriptions": [],
                "language_code": language_code or self.language_code,
                "audio_format": audio_format,
            }

    def transcribe_base64_audio(
        self,
        base64_audio: str,
        audio_format: str = "wav",
        language_code: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Transcribe base64 encoded audio data

        Args:
            base64_audio: Base64 encoded audio data
            audio_format: Audio format
            language_code: Language code for transcription
            **kwargs: Additional arguments for transcribe_audio

        Returns:
            Dict containing transcription results
        """
        try:
            # Decode base64 audio data
            audio_data = base64.b64decode(base64_audio)
            return self.transcribe_audio(
                audio_data=audio_data,
                audio_format=audio_format,
                language_code=language_code,
                **kwargs,
            )
        except Exception as e:
            logger.error(f"Error decoding base64 audio: {e}")
            return {
                "success": False,
                "error": f"Failed to decode base64 audio: {str(e)}",
                "transcriptions": [],
                "language_code": language_code or self.language_code,
                "audio_format": audio_format,
            }

    def get_supported_languages(self) -> List[str]:
        """
        Get list of supported language codes

        Returns:
            List of supported language codes
        """
        # Common supported languages for Google Cloud Speech-to-Text
        return [
            "en-US",  # English (United States)
            "en-GB",  # English (United Kingdom)
            "es-ES",  # Spanish (Spain)
            "es-US",  # Spanish (United States)
            "fr-FR",  # French (France)
            "de-DE",  # German (Germany)
            "it-IT",  # Italian (Italy)
            "pt-BR",  # Portuguese (Brazil)
            "ja-JP",  # Japanese (Japan)
            "ko-KR",  # Korean (South Korea)
            "zh-CN",  # Chinese (Simplified)
            "zh-TW",  # Chinese (Traditional)
            "ar-SA",  # Arabic (Saudi Arabia)
            "hi-IN",  # Hindi (India)
            "ru-RU",  # Russian (Russia)
            "nl-NL",  # Dutch (Netherlands)
            "sv-SE",  # Swedish (Sweden)
            "da-DK",  # Danish (Denmark)
            "no-NO",  # Norwegian (Norway)
            "fi-FI",  # Finnish (Finland)
        ]

    def get_supported_formats(self) -> List[str]:
        """
        Get list of supported audio formats

        Returns:
            List of supported audio formats
        """
        return list(self.audio_configs.keys())

    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check for the Speech-to-Text client

        Returns:
            Dict containing health status
        """
        try:
            if not self.connected:
                return {
                    "status": "unhealthy",
                    "connected": False,
                    "error": "Client not initialized",
                }

            # Simple health check - try to create a minimal config
            test_config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                language_code=self.language_code,
            )

            return {
                "status": "healthy",
                "connected": True,
                "project_id": self.project_id,
                "language_code": self.language_code,
                "supported_formats": self.get_supported_formats(),
                "supported_languages": len(self.get_supported_languages()),
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "connected": False,
                "error": str(e),
            }
