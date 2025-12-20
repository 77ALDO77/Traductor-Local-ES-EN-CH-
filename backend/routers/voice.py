"""
Router para endpoints de traducción por voz.
Incluye WebSocket para streaming en tiempo real.
"""

import io
import time
import json
import base64
import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.responses import JSONResponse
import numpy as np
import soundfile as sf

from backend.schemas.voice import (
    VoiceTranslationResponse,
    Language
)
from backend.services.voice_service import voice_service
from backend.services.ollama_service import translation_service


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["Voice"])


@router.get("/status")
async def voice_status():
    """Verifica el estado del servicio de voz."""
    model_info = voice_service.get_model_info()
    return {
        "model_loaded": model_info["loaded"],
        "model_name": f"Faster-Whisper ({model_info['model_size']})",
        "device": model_info["device"],
        "compute_type": model_info["compute_type"],
        "supported_languages": model_info["supported_languages"]
    }

@router.post("/load-model")
async def load_voice_model():
    """Pre-carga el modelo de voz (opcional, se carga automáticamente en primer uso)."""
    try:
        success = voice_service.load_model()
        if success:
            return {"status": "success", "message": "Modelo SenseVoice cargado correctamente"}
        else:
            raise HTTPException(status_code=503, detail="Error cargando el modelo")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    target_language: str = Form("Spanish")
):
    """
    Transcribe audio y traduce al idioma destino.
    Acepta archivos WAV, MP3, etc.
    """
    start_time = time.time()
    
    try:
        # Leer audio
        audio_bytes = await audio.read()
        
        # Transcribir
        text, detected_lang, transcription_time = await voice_service.transcribe_audio(
            audio_data=audio_bytes
        )
        
        if not text:
            return JSONResponse(
                status_code=400,
                content={"error": "No se detectó voz en el audio"}
            )
        
        # Traducir si es necesario
        translation_time = 0
        translated_text = text
        
        if detected_lang != target_language:
            trans_start = time.time()
            result = await translation_service.translate(
                text=text,
                source_lang=detected_lang,
                target_lang=target_language
            )
            translated_text = result["translated_text"]
            translation_time = (time.time() - trans_start) * 1000
        
        total_time = (time.time() - start_time) * 1000
        
        return VoiceTranslationResponse(
            original_text=text,
            translated_text=translated_text,
            source_language=detected_lang,
            target_language=target_language,
            transcription_time_ms=round(transcription_time, 2),
            translation_time_ms=round(translation_time, 2),
            total_time_ms=round(total_time, 2)
        )
        
    except Exception as e:
        logger.error(f"Error en transcripción: {e}")
        raise HTTPException(status_code=500, detail=str(e))


NAME_TO_ISO = {
    "English": "en",
    "Spanish": "es",
    "Chinese": "zh",
}


@router.websocket("/ws")
async def voice_websocket(websocket: WebSocket):
    """
    WebSocket para transcripción y traducción en tiempo real.
    
    Protocolo:
    - Cliente envía: {"type": "audio", "data": "<base64>", "sample_rate": 16000, "target_language": "Spanish"}
    - Cliente envía: {"type": "config", "target_language": "Spanish"}
    - Servidor responde: {"type": "transcription", "data": {"text": "...", "language": "..."}}
    - Servidor responde: {"type": "translation", "data": {"text": "...", "source": "...", "target": "..."}}
    - Servidor responde: {"type": "error", "data": {"message": "..."}}
    """
    await websocket.accept()
    logger.info("🔌 WebSocket conectado")
    
    # Idiomas por defecto (usuario selecciona en el front)
    source_language = "Spanish"
    target_language = "Spanish"
    
    try:
        # Pre-cargar modelo si no está cargado
        if not voice_service.model_loaded:
            await websocket.send_json({
                "type": "status",
                "data": {"message": "Cargando modelo de voz..."}
            })
            voice_service.load_model()
            await websocket.send_json({
                "type": "status",
                "data": {"message": "Modelo cargado. Listo para transcribir."}
            })
        
        # Buffer de audio para la sesión actual
        audio_buffer = bytearray()
        # Guardar el primer chunk (header WebM) para reusarlo al resetear buffer
        header_chunk = b""
        
        while True:
            # Recibir mensaje
            message = await websocket.receive_json()
            msg_type = message.get("type")
            
            if msg_type == "config":
                # Actualizar configuración
                source_language = message.get("source_language", source_language)
                target_language = message.get("target_language", target_language)
                await websocket.send_json({
                    "type": "status",
                    "data": {"message": f"Origen: {source_language} | Destino: {target_language}"}
                })
                # Limpiar buffer al cambiar config? No necesariamente, pero un reset es útil.
                # audio_buffer = bytearray() 

                
            elif msg_type == "audio":
                # Procesar audio
                try:
                    audio_b64 = message.get("data")
                    sample_rate = message.get("sample_rate", 16000)
                    # Permitir override por mensaje, con fallback al estado
                    src_lang = message.get("source_language", source_language)
                    target_lang = message.get("target_language", target_language)
                    
                    # Decodificar base64
                    audio_bytes = base64.b64decode(audio_b64)
                    
                    if not header_chunk:
                        header_chunk = audio_bytes
                    
                    # Acumular en el buffer
                    audio_buffer.extend(audio_bytes)
                    
                    # Transcribir el buffer completo acumulado hasta ahora
                    # Mapear a código ISO para forzar idioma en Whisper
                    iso = NAME_TO_ISO.get(src_lang, None)
                    if iso and len(iso) != 2:
                        iso = None
                    text, detected_lang, trans_time = await voice_service.transcribe_audio(
                        audio_data=bytes(audio_buffer),
                        sample_rate=sample_rate,
                        forced_language=iso
                    )
                    
                    if not text:
                        await websocket.send_json({
                            "type": "status",
                            "data": {"message": "No se detectó voz"}
                        })

                        continue
                    
                    # Filtro de alucinaciones conocidas de Whisper
                    HALLUCINATIONS = [
                        "¡Gracias por ver el vídeo!",
                        "Thanks for watching!",
                        "Gracias por ver el video",
                        "Suscríbete al canal",
                        "Subtitles by",
                    ]
                    
                    text_lower = text.lower().strip()
                    is_hallucination = False
                    for h in HALLUCINATIONS:
                        if h.lower() in text_lower:
                             # Si es *solo* la alucinación o domina el texto, ignorar
                             if len(text) < len(h) + 10:
                                 is_hallucination = True
                                 break
                    
                    if is_hallucination:
                        continue

                    # Enviar transcripción
                    await websocket.send_json({
                        "type": "transcription",
                        "data": {
                            "text": text,
                            # Mostrar el idioma de origen seleccionado (no autodetección)
                            "language": src_lang,
                            "time_ms": round(trans_time, 2)
                        }
                    })
                    
                    # Traducir si es necesario según origen/destino provistos
                    if src_lang != target_lang:
                        result = await translation_service.translate(
                            text=text,
                            source_lang=src_lang,
                            target_lang=target_lang
                        )
                        
                        await websocket.send_json({
                            "type": "translation",
                            "data": {
                                "original": text,
                                "translated": result["translated_text"],
                                "source_language": src_lang,
                                "target_language": target_lang,
                                "time_ms": result.get("processing_time_ms", 0)
                            }
                        })
                    else:
                        # Mismo idioma, no traducir
                        await websocket.send_json({
                            "type": "translation",
                            "data": {
                                "original": text,
                                "translated": text,
                                "source_language": src_lang,
                                "target_language": target_lang,
                                "time_ms": 0
                            }
                        })

                    # 4. Verificar fin de frase para "segmentar" la conversación
                    # Si el texto termina en puntuación fuerte y tiene cierta longitud, asumimos fin de idea.
                    # Esto permite limpiar el buffer (para velocidad) y crear nueva burbuja en UI.
                    stripped_text = text.strip()
                    if len(stripped_text) > 5 and stripped_text[-1] in ".!?。！？":
                        # Enviar señal de fin de segmento
                        await websocket.send_json({"type": "segment_end"})
                        
                        # Resetear buffer pero MANTENER el header
                        audio_buffer = bytearray(header_chunk)
                        
                except Exception as e:
                    logger.error(f"Error procesando audio: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "data": {"message": str(e)}
                    })
            
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                
    except WebSocketDisconnect:
        logger.info("🔌 WebSocket desconectado")
    except Exception as e:
        logger.error(f"Error en WebSocket: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "data": {"message": str(e)}
            })
        except:
            pass
