"""
Servicio de reconocimiento de voz.
Actúa como cliente para el servicio 'translator_engine' donde corre Whisper.
"""

import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

# URL del servicio de traducción (docker container name)
# TRANSLATOR_HOST = "http://translator_engine:9000" # DISABLED


class VoiceService:
    """
    Cliente para el servicio de voz remoto (translator_engine).
    MODO: DUMMY / DESACTIVADO TEMPORALMENTE (Hardware Optimization)
    """

    def __init__(self):
        # self.client = httpx.AsyncClient(timeout=60.0)
        self.model_loaded = False 

    def load_model(self) -> bool:
        # El modelo remoto está desactivado
        return False

    def get_model_info(self) -> dict:
        return {
            "model_size": "disabled",
            "device": "none",
            "compute_type": "none",
            "loaded": False,
            "supported_languages": []
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
        raise Exception("El servicio de voz está desactivado temporalmente por mantenimiento de hardware.")

    async def transcribe_audio_chunk(
        self,
        audio_chunk: bytes,
        sample_rate: int = 16000,
        forced_language: Optional[str] = None
    ) -> Tuple[str, str, float]:
        """
        Envía chunk de audio a translator_engine.
        """
        raise Exception("El servicio de voz está desactivado temporalmente por mantenimiento de hardware.")


voice_service = VoiceService()
