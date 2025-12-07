"""
Servicio de reconocimiento de voz usando Faster-Whisper.
Motor ASR de alta precisión con soporte multilingüe robusto.
Optimizado para CPU (i9-13900H) con compute_type int8.
"""

import io
import os
import time
import logging
import tempfile
from pathlib import Path
from typing import Tuple

import soundfile as sf
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

# Directorio para modelos
MODELS_DIR = Path("models")
MODELS_DIR.mkdir(exist_ok=True)


class VoiceService:
    """
    Servicio de Speech-to-Text usando Faster-Whisper.
    Faster-Whisper es una implementación optimizada de OpenAI Whisper
    con inferencia 4x más rápida usando CTranslate2.
    """
    
    # Mapeo de códigos ISO 639-1 a nombres completos
    LANGUAGE_MAP = {
        'en': 'English',
        'es': 'Spanish',
        'zh': 'Chinese',
        'ja': 'Japanese',
        'ko': 'Korean',
        'fr': 'French',
        'de': 'German',
        'pt': 'Portuguese',
        'ru': 'Russian',
        'ar': 'Arabic',
    }
    
    def __init__(
        self,
        model_size: str = "medium",
        device: str = "cpu",
        compute_type: str = "int8"
    ):
        """
        Inicializa el servicio de voz.
        
        Args:
            model_size: Tamaño del modelo ('tiny', 'base', 'small', 'medium', 'large-v3')
            device: 'cpu' o 'cuda'
            compute_type: 'int8', 'int8_float16', 'float16', 'float32'
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.model = None
        self.model_loaded = False
        self._load_lock = False
    
    def load_model(self) -> bool:
        """
        Carga el modelo Faster-Whisper.
        Se llama de forma lazy en la primera transcripción.
        """
        if self.model_loaded:
            return True
        
        if self._load_lock:
            return False
        
        self._load_lock = True
        
        try:
            logger.info(f"🎤 Cargando modelo Faster-Whisper ({self.model_size})...")
            start_time = time.time()
            
            # Cargar modelo con configuración optimizada para CPU
            self.model = WhisperModel(
                model_size_or_path=self.model_size,
                device=self.device,
                compute_type=self.compute_type,
                download_root=str(MODELS_DIR),
                local_files_only=False  # Primera vez descarga, luego usa caché
            )
            
            load_time = time.time() - start_time
            logger.info(f"✅ Modelo Faster-Whisper cargado en {load_time:.2f}s")
            logger.info(f"   Configuración: {self.model_size} | {self.device} | {self.compute_type}")
            
            self.model_loaded = True
            return True
            
        except Exception as e:
            logger.error(f"❌ Error cargando Faster-Whisper: {e}")
            self._load_lock = False
            return False
    
    def _map_language_code(self, iso_code: str) -> str:
        """
        Mapea código ISO 639-1 a nombre completo del idioma.
        
        Args:
            iso_code: Código de 2 letras ('en', 'es', 'zh', etc.)
            
        Returns:
            Nombre completo del idioma ('English', 'Spanish', etc.)
        """
        return self.LANGUAGE_MAP.get(iso_code.lower(), 'English')
    
    async def transcribe_audio(
        self,
        audio_data: bytes,
        sample_rate: int = 16000
    ) -> Tuple[str, str, float]:
        """
        Transcribe audio a texto con detección automática de idioma.
        
        Args:
            audio_data: Datos de audio en bytes (WAV format)
            sample_rate: Tasa de muestreo del audio
            
        Returns:
            Tupla (texto_transcrito, idioma_detectado, tiempo_ms)
        """
        if not self.model_loaded:
            if not self.load_model():
                raise RuntimeError("No se pudo cargar el modelo Faster-Whisper")
        
        start_time = time.time()
        tmp_path = None
        
        try:
            # Guardar audio en archivo temporal
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                tmp_path = tmp_file.name
                
                # Convertir bytes a numpy array
                audio_array, sr = sf.read(io.BytesIO(audio_data))
                
                # Asegurar mono
                if len(audio_array.shape) > 1:
                    audio_array = audio_array.mean(axis=1)
                
                # Guardar como WAV
                sf.write(tmp_path, audio_array, sample_rate)
            
            # Transcribir con Faster-Whisper
            # beam_size=5 para mejor precisión (default es 5)
            # vad_filter=True para filtrar silencio automáticamente
            segments, info = self.model.transcribe(
                audio=tmp_path,
                language=None,        # Auto-detect
                beam_size=5,
                vad_filter=True,      # Voice Activity Detection
                vad_parameters=dict(
                    threshold=0.5,
                    min_speech_duration_ms=250,
                    min_silence_duration_ms=100
                )
            )
            
            # Limpiar archivo temporal
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
                tmp_path = None
            
            # Unir todos los segmentos en un solo texto
            full_text = ""
            for segment in segments:
                full_text += segment.text + " "
            
            full_text = full_text.strip()
            
            # Extraer idioma detectado
            detected_language_code = info.language
            detected_language = self._map_language_code(detected_language_code)
            
            # Probabilidad de detección de idioma (para logs)
            language_probability = info.language_probability
            
            processing_time = (time.time() - start_time) * 1000
            
            logger.info(
                f"🎤 Transcripción: '{full_text[:50]}{'...' if len(full_text) > 50 else ''}' "
                f"({detected_language} [{detected_language_code}] - {language_probability:.1%} confianza) "
                f"en {processing_time:.0f}ms"
            )
            
            return full_text, detected_language, processing_time
            
        except Exception as e:
            logger.error(f"Error en transcripción: {e}")
            # Limpiar archivo temporal si existe
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise
    
    async def transcribe_audio_chunk(
        self,
        audio_chunk,
        sample_rate: int = 16000
    ) -> Tuple[str, str, float]:
        """
        Transcribe un chunk de audio (numpy array o bytes).
        Útil para streaming.
        
        Args:
            audio_chunk: Array numpy o bytes de audio
            sample_rate: Tasa de muestreo
            
        Returns:
            Tupla (texto_transcrito, idioma_detectado, tiempo_ms)
        """
        if not self.model_loaded:
            if not self.load_model():
                raise RuntimeError("No se pudo cargar el modelo Faster-Whisper")
        
        start_time = time.time()
        tmp_path = None
        
        try:
            # Guardar chunk en archivo temporal
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                tmp_path = tmp_file.name
                
                # Si es numpy array, usar directamente
                # Si es bytes, convertir primero
                if isinstance(audio_chunk, bytes):
                    audio_array, sr = sf.read(io.BytesIO(audio_chunk))
                    if len(audio_array.shape) > 1:
                        audio_array = audio_array.mean(axis=1)
                    sf.write(tmp_path, audio_array, sample_rate)
                else:
                    sf.write(tmp_path, audio_chunk, sample_rate)
            
            # Transcribir
            segments, info = self.model.transcribe(
                audio=tmp_path,
                language=None,
                beam_size=4,
                vad_filter=True,
                vad_parameters=dict(
                    threshold=0.5,
                    min_speech_duration_ms=250,
                    min_silence_duration_ms=100
                )
            )
            
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
                tmp_path = None
            
            # Unir segmentos
            full_text = " ".join(segment.text for segment in segments).strip()
            
            # Detectar idioma
            detected_language_code = info.language
            detected_language = self._map_language_code(detected_language_code)
            
            processing_time = (time.time() - start_time) * 1000
            
            return full_text, detected_language, processing_time
            
        except Exception as e:
            logger.error(f"Error en transcripción de chunk: {e}")
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise
    
    def get_model_info(self) -> dict:
        """Retorna información sobre el modelo cargado."""
        return {
            "model_size": self.model_size,
            "device": self.device,
            "compute_type": self.compute_type,
            "loaded": self.model_loaded,
            "supported_languages": list(self.LANGUAGE_MAP.values())
        }


# Instancia global con configuración optimizada para i9 CPU
voice_service = VoiceService(
    model_size="medium",
    device="cpu",
    compute_type="int8"
)
