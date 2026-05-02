"""
Router para endpoints de traducción de texto.
"""

from fastapi import APIRouter, HTTPException
from backend.schemas.translation import TranslationRequest, TranslationResponse, Language
from backend.services.llm_service import translation_service


router = APIRouter(prefix="/api/translate", tags=["Translation"])


@router.post("/text", response_model=TranslationResponse)
async def translate_text(request: TranslationRequest):
    """
    Traduce texto entre idiomas soportados.
    
    - **text**: Texto a traducir (máx. 5000 caracteres)
    - **source_language**: Idioma de origen (English, Spanish, Chinese)
    - **target_language**: Idioma de destino (English, Spanish, Chinese)
    """
    try:
        result = await translation_service.translate(
            text=request.text,
            source_lang=request.source_language.value,
            target_lang=request.target_language.value
        )
        
        return TranslationResponse(
            original_text=request.text,
            translated_text=result["translated_text"],
            source_language=request.source_language,
            target_language=request.target_language,
            model_used=translation_service.get_model(),
            processing_time_ms=result["processing_time_ms"]
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/languages")
async def get_supported_languages():
    """Retorna la lista de idiomas soportados."""
    return {
        "languages": [lang.value for lang in Language],
        "pairs": [
            {"source": "English", "target": "Spanish"},
            {"source": "English", "target": "Chinese"},
            {"source": "Spanish", "target": "English"},
            {"source": "Spanish", "target": "Chinese"},
            {"source": "Chinese", "target": "English"},
            {"source": "Chinese", "target": "Spanish"},
        ]
    }
