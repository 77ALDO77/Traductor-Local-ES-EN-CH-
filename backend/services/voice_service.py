"""
Servicio de reconocimiento de voz.
MODO: DUMMY / DESACTIVADO TEMPORALMENTE (Hardware Optimization)
"""

import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


class VoiceService:
    """
    Servicio de reconocimiento de voz.
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
        Transcribe audio completo.
        """
        raise Exception("El servicio de voz está desactivado temporalmente por mantenimiento de hardware.")

    async def transcribe_audio_chunk(
        self,
        audio_chunk: bytes,
        sample_rate: int = 16000,
        forced_language: Optional[str] = None
    ) -> Tuple[str, str, float]:
        """
        Transcribe chunk de audio.
        """
        raise Exception("El servicio de voz está desactivado temporalmente por mantenimiento de hardware.")


voice_service = VoiceService()
