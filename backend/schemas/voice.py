"""
Schemas para el módulo de traducción por voz.
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal
from enum import Enum


class Language(str, Enum):
    ENGLISH = "English"
    SPANISH = "Spanish"
    CHINESE = "Chinese"
    AUTO = "Auto"


class TranscriptionResult(BaseModel):
    text: str
    language_detected: Optional[str] = None
    confidence: Optional[float] = None
    duration_ms: float


class VoiceTranslationRequest(BaseModel):
    target_language: Language = Field(..., description="Idioma de destino para la traducción")


class VoiceTranslationResponse(BaseModel):
    original_text: str
    translated_text: str
    source_language: str
    target_language: str
    transcription_time_ms: float
    translation_time_ms: float
    total_time_ms: float


class WebSocketMessage(BaseModel):
    type: Literal["transcription", "translation", "error", "status"]
    data: dict
