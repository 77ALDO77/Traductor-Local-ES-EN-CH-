"""
Servicio de reconocimiento de voz.
Actúa como cliente para el servicio 'translator_engine' donde corre Whisper.
"""

import logging
import time
import httpx
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

# URL del servicio de traducción (docker container name)
TRANSLATOR_HOST = "http://translator_engine:9000"


class VoiceService:
    """
    Cliente para el servicio de voz remoto (translator_engine).
    """

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=60.0)
        self.model_loaded = True # Asumimos remoto siempre listo o cargando bajo demanda

    def load_model(self) -> bool:
        # El modelo remoto se maneja solo
        return True

    def get_model_info(self) -> dict:
        return {
            "model_size": "remote",
            "device": "remote-gpu",
            "compute_type": "float16",
            "loaded": True,
            "supported_languages": ["Multilingual"]
        }

    async def transcribe_audio(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        forced_language: Optional[str] = None
    ) -> Tuple[str, str, float]:
        """
        Envía audio completo a translator_engine para transcripción.
        """
        start_time = time.time()
        
        try:
            # Preparar multipart form upload
            files = {'file': ('audio.webm', audio_data, 'audio/webm')}
            data = {}
            if forced_language:
                data['language'] = forced_language
                
            response = await self.client.post(
                f"{TRANSLATOR_HOST}/transcribe",
                files=files,
                data=data
            )
            
            if response.status_code != 200:
                raise Exception(f"Error remoto ({response.status_code}): {response.text}")
            
            result = response.json()
            
            text = result.get("text", "")
            detected_lang = result.get("language", "en")
            processing_time = result.get("processing_time", (time.time() - start_time) * 1000)
            
            return text, detected_lang, processing_time
            
        except Exception as e:
            logger.error(f"Error llamada servicio voz remoto: {e}")
            raise

    async def transcribe_audio_chunk(
        self,
        audio_chunk: bytes,
        sample_rate: int = 16000,
        forced_language: Optional[str] = None
    ) -> Tuple[str, str, float]:
        """
        Envía chunk de audio a translator_engine.
        """
        start_time = time.time()
        try:
            files = {'audio_data': ('chunk.wav', audio_chunk, 'application/octet-stream')}
            data = {'sample_rate': str(sample_rate)}
            if forced_language:
                data['language'] = forced_language

            response = await self.client.post(
                f"{TRANSLATOR_HOST}/transcribe_chunk",
                files=files,
                data=data
            )

            if response.status_code != 200:
                raise Exception(f"Error remoto chunk ({response.status_code}): {response.text}")

            result = response.json()
            return result.get("text", ""), result.get("language", "en"), result.get("processing_time", 0)

        except Exception as e:
            logger.error(f"Error llamada chunk remoto: {e}")
            raise


voice_service = VoiceService()
