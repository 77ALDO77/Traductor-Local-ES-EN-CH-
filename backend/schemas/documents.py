"""
Schemas para el módulo de traducción de documentos.
"""

from pydantic import BaseModel, Field
from typing import Literal, Optional
from enum import Enum


class Language(str, Enum):
    ENGLISH = "English"
    SPANISH = "Spanish"
    CHINESE = "Chinese"


class FileType(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"


class DocumentUploadResponse(BaseModel):
    filename: str
    file_type: FileType
    file_size: int
    total_chunks: int
    preview_text: str = Field(..., description="Primeros 500 caracteres del documento")


class DocumentTranslationRequest(BaseModel):
    filename: str
    source_language: Language
    target_language: Language


class ChunkTranslation(BaseModel):
    chunk_index: int
    original: str
    translated: str


class DocumentTranslationProgress(BaseModel):
    status: Literal["processing", "completed", "error"]
    filename: str
    current_chunk: int
    total_chunks: int
    progress_percent: float
    message: Optional[str] = None


class DocumentTranslationResponse(BaseModel):
    original_filename: str
    translated_filename: str
    source_language: Language
    target_language: Language
    total_chunks: int
    processing_time_ms: float
    download_url: str
