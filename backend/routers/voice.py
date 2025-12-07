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
                source_language=detected_lang,
                target_language=target_language
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
        
        while True:
            # Recibir mensaje
            message = await websocket.receive_json()
            msg_type = message.get("type")
            
            if msg_type == "config":
                # Actualizar configuración
                target_language = message.get("target_language", "Spanish")
                await websocket.send_json({
                    "type": "status",
                    "data": {"message": f"Idioma destino: {target_language}"}
                })
                
            elif msg_type == "audio":
                # Procesar audio
                try:
                    audio_b64 = message.get("data")
                    sample_rate = message.get("sample_rate", 16000)
                    target_lang = message.get("target_language", target_language)
                    
                    # Decodificar base64
                    audio_bytes = base64.b64decode(audio_b64)
                    
                    # Transcribir
                    text, detected_lang, trans_time = await voice_service.transcribe_audio(
                        audio_data=audio_bytes,
                        sample_rate=sample_rate
                    )
                    
                    if not text:
                        await websocket.send_json({
                            "type": "status",
                            "data": {"message": "No se detectó voz"}
                        })
                        continue
                    
                    # Enviar transcripción
                    await websocket.send_json({
                        "type": "transcription",
                        "data": {
                            "text": text,
                            "language": detected_lang,
                            "time_ms": round(trans_time, 2)
                        }
                    })
                    
                    # Traducir si es necesario
                    if detected_lang != target_lang:
                        result = await translation_service.translate(
                            text=text,
                            source_language=detected_lang,
                            target_language=target_lang
                        )
                        
                        await websocket.send_json({
                            "type": "translation",
                            "data": {
                                "original": text,
                                "translated": result["translated_text"],
                                "source_language": detected_lang,
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
                                "source_language": detected_lang,
                                "target_language": target_lang,
                                "time_ms": 0
                            }
                        })
                        
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
