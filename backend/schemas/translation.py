"""
Schemas para el módulo de traducción de texto.
"""

from pydantic import BaseModel, Field
from typing import Literal
from enum import Enum


class Language(str, Enum):
    ENGLISH = "English"
    SPANISH = "Spanish"
    CHINESE = "Chinese"


class TranslationRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000, description="Texto a traducir")
    source_language: Language = Field(..., description="Idioma de origen")
    target_language: Language = Field(..., description="Idioma de destino")
    
    class Config:
        json_schema_extra = {
            "example": {
                "text": "Hello, world!",
                "source_language": "English",
                "target_language": "Spanish"
            }
        }


class TranslationResponse(BaseModel):
    original_text: str
    translated_text: str
    source_language: Language
    target_language: Language
    model_used: str
    processing_time_ms: float | None = None
