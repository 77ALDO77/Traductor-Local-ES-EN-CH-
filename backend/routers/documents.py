"""
Router para endpoints de traducción de documentos.
Alta fidelidad: preserva formato, imágenes, estilos.
"""

import os
import time
from pathlib import Path
from typing import AsyncGenerator
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
import json
import asyncio

from backend.schemas.documents import (
    DocumentUploadResponse,
    Language,
    FileType
)
from backend.services.document_service import document_service, UPLOAD_DIR


router = APIRouter(prefix="/api/documents", tags=["Documents"])

# Almacenamiento temporal de documentos
uploaded_documents: dict[str, dict] = {}


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...)):
    """
    Sube un documento para traducción.
    Soporta: PDF, DOCX, XLSX
    """
    try:
        file_type = document_service.get_file_type(file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Validar tamaño (máx 20MB)
    contents = await file.read()
    file_size = len(contents)
    
    if file_size > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="El archivo excede el límite de 20MB")
    
    # Guardar archivo
    file_path = UPLOAD_DIR / file.filename
    with open(file_path, 'wb') as f:
        f.write(contents)
    
    # Obtener estadísticas
    try:
        stats = document_service.get_document_stats(file_path)
    except Exception as e:
        os.remove(file_path)
        raise HTTPException(status_code=400, detail=f"Error al analizar el documento: {str(e)}")
    
    # Guardar info
    uploaded_documents[file.filename] = {
        "path": file_path,
        "file_type": file_type,
        "stats": stats
    }
    
    preview = stats.get("preview_text", "")[:500]
    if len(stats.get("preview_text", "")) > 500:
        preview += "..."
    
    return DocumentUploadResponse(
        filename=file.filename,
        file_type=FileType(file_type),
        file_size=file_size,
        total_chunks=stats.get("translatable_items", 0),
        preview_text=preview
    )


@router.post("/translate/stream")
async def translate_document_stream(
    filename: str = Form(...),
    source_language: str = Form(...),
    target_language: str = Form(...)
):
    """
    Traduce un documento preservando formato con streaming de progreso.
    Los PDFs se entregan como PDFs, DOCX como DOCX, XLSX como XLSX.
    """
    if filename not in uploaded_documents:
        raise HTTPException(status_code=404, detail="Documento no encontrado. Sube el archivo primero.")
    
    doc_info = uploaded_documents[filename]
    input_path = doc_info["path"]
    file_type = doc_info["file_type"]
    
    async def generate_progress() -> AsyncGenerator[str, None]:
        start_time = time.time()
        progress_data = {"current": 0, "total": 100, "message": "Iniciando..."}
        output_path_result = None
        output_format = None
        
        def progress_callback(current: int, total: int, message: str):
            progress_data["current"] = current
            progress_data["total"] = total
            progress_data["message"] = message
        
        try:
            # Enviar progreso inicial
            yield f"data: {json.dumps({'status': 'processing', 'filename': filename, 'current_chunk': 0, 'total_chunks': 100, 'progress_percent': 0, 'message': 'Analizando documento...'})}\n\n"
            
            # Generar nombre base para salida
            base_name = Path(filename).stem
            output_path_base = UPLOAD_DIR / f"{base_name}_translated"
            
            last_progress = 0
            
            async def translate_with_progress():
                nonlocal output_path_result, output_format
                output_path_result, output_format = await document_service.translate_document_preserving_format(
                    input_path=input_path,
                    output_path=output_path_base,
                    source_lang=source_language,
                    target_lang=target_language,
                    progress_callback=progress_callback
                )
            
            # Ejecutar traducción
            task = asyncio.create_task(translate_with_progress())
            
            while not task.done():
                await asyncio.sleep(0.5)
                
                if progress_data["total"] > 0:
                    percent = round((progress_data["current"] / progress_data["total"]) * 100, 1)
                else:
                    percent = 0
                
                if percent != last_progress:
                    last_progress = percent
                    progress_msg = {
                        "status": "processing",
                        "filename": filename,
                        "current_chunk": progress_data["current"],
                        "total_chunks": progress_data["total"],
                        "progress_percent": percent,
                        "message": progress_data["message"]
                    }
                    yield f"data: {json.dumps(progress_msg)}\n\n"
            
            # Esperar y verificar resultado
            await task
            
            if not output_path_result:
                raise Exception("Error: La traducción no generó un archivo válido")
            
            end_time = time.time()
            processing_time = (end_time - start_time) * 1000
            
            output_filename = output_path_result.name
            
            # Enviar completado
            final_response = {
                "status": "completed",
                "filename": filename,
                "current_chunk": progress_data["total"],
                "total_chunks": progress_data["total"],
                "progress_percent": 100.0,
                "message": f"Traducción completada. Formato final: {output_format.upper()}",
                "translated_filename": output_filename,
                "download_url": f"/api/documents/download/{output_filename}",
                "processing_time_ms": round(processing_time, 2)
            }
            yield f"data: {json.dumps(final_response)}\n\n"
            
        except Exception as e:
            error_response = {
                "status": "error",
                "filename": filename,
                "current_chunk": progress_data["current"],
                "total_chunks": progress_data["total"],
                "progress_percent": 0,
                "message": f"Error: {str(e)}"
            }
            yield f"data: {json.dumps(error_response)}\n\n"
    
    return StreamingResponse(
        generate_progress(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.get("/download/{filename}")
async def download_translated_document(filename: str):
    """Descarga el documento traducido en su formato final."""
    file_path = UPLOAD_DIR / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    
    ext = filename.lower().split('.')[-1]
    media_types = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "txt": "text/plain"
    }
    media_type = media_types.get(ext, "application/octet-stream")
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=media_type
    )


@router.delete("/cleanup/{filename}")
async def cleanup_document(filename: str):
    """Elimina archivos temporales de un documento."""
    if filename in uploaded_documents:
        original_path = uploaded_documents[filename]["path"]
        if original_path.exists():
            os.remove(original_path)
        del uploaded_documents[filename]
    
    # Eliminar traducido si existe
    base_name = Path(filename).stem
    for ext in ['.pdf', '.docx', '.xlsx', '.txt']:
        translated_path = UPLOAD_DIR / f"{base_name}_translated{ext}"
        if translated_path.exists():
            os.remove(translated_path)
    
    return {"message": "Archivos eliminados"}
