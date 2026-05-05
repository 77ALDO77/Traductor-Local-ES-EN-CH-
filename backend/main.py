"""
BoC_Translator - Backend Principal
Banco de China - Sistema de Traducción Offline
"""

import os
import asyncio
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from openai import AsyncOpenAI

# Importar routers
from backend.routers import translation, documents, voice, admin

# Configurar logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuración desde variables de entorno (para Docker)
LLM_HOST = os.getenv("LLM_HOST", "http://localhost:8000")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-1.5B-Instruct")
UPLOAD_DIR = Path("uploads")

# Configuración de limpieza
CLEANUP_INTERVAL_MINUTES = int(os.getenv("CLEANUP_INTERVAL_MINUTES", "10"))
FILE_RETENTION_MINUTES = int(os.getenv("FILE_RETENTION_MINUTES", "30"))


async def cleanup_old_files():
    """Tarea en background que elimina archivos antiguos en uploads/."""
    while True:
        try:
            await asyncio.sleep(CLEANUP_INTERVAL_MINUTES * 60)
            
            now = datetime.now()
            cutoff_time = now - timedelta(minutes=FILE_RETENTION_MINUTES)
            
            if not UPLOAD_DIR.exists():
                continue
            
            deleted_count = 0
            
            for file_path in UPLOAD_DIR.glob("*"):
                if not file_path.is_file():
                    continue
                
                file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                
                if file_mtime < cutoff_time:
                    try:
                        os.remove(file_path)
                        deleted_count += 1
                        logger.info(f"🧹 Archivo eliminado: {file_path.name}")
                    except Exception as e:
                        logger.error(f"Error al eliminar {file_path.name}: {e}")
            
            if deleted_count > 0:
                logger.info(f"🧹 Limpieza completada: {deleted_count} archivos eliminados")
                
        except Exception as e:
            logger.error(f"Error en la tarea de limpieza: {e}")
            continue


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle management del servidor."""
    logger.info("🚀 Iniciando BoC_Translator...")
    logger.info(f"   LLM Host: {LLM_HOST}")
    logger.info(f"   Modelo LLM: {MODEL_NAME}")
    
    # Verificar conexión con vLLM
    try:
        client = AsyncOpenAI(base_url=f"{LLM_HOST}/v1", api_key="not-needed")
        models = await client.models.list()
        model_ids = [m.id for m in models.data]
        
        if MODEL_NAME not in model_ids:
            logger.warning(f"⚠️  ADVERTENCIA: Modelo '{MODEL_NAME}' no encontrado en vLLM.")
            logger.warning(f"   Verifica que vLLM esté corriendo con el modelo correcto.")
        else:
            logger.info(f"✅ Modelo '{MODEL_NAME}' encontrado y listo.")
        
        logger.info("✅ Conexión con vLLM establecida.")
    except Exception as e:
        logger.error(f"❌ Error conectando con vLLM: {e}")
        logger.error("   Verifica que el contenedor 'vllm' esté corriendo.")
    
    # Crear carpetas necesarias
    UPLOAD_DIR.mkdir(exist_ok=True)
    Path("models").mkdir(exist_ok=True)
    logger.info(f"📁 Carpeta de uploads: {UPLOAD_DIR.absolute()}")
    
    # Iniciar tarea de limpieza
    cleanup_task = asyncio.create_task(cleanup_old_files())
    logger.info(f"🧹 Limpieza automática cada {CLEANUP_INTERVAL_MINUTES} minutos")
    logger.info(f"   Retención de archivos: {FILE_RETENTION_MINUTES} minutos")
    
    # Info sobre modelo de voz
    logger.info("🎤 Modelo Faster-Whisper (medium/int8) se cargará en primer uso")
    
    yield
    
    # Cleanup
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    
    logger.info("👋 Cerrando BoC_Translator...")


app = FastAPI(
    title="BoC_Translator API",
    description="Sistema de Traducción Offline para Banco de China",
    version="1.0.0",
    lifespan=lifespan
)


# Registrar routers
app.include_router(translation.router)
app.include_router(documents.router)
app.include_router(voice.router)
app.include_router(admin.router)


@app.get("/health")
async def health_check():
    """Health Check del sistema."""
    from backend.services.voice_service import voice_service
    
    health_status = {
        "fastapi": "healthy",
        "llm": "unknown",
        "model_llm": MODEL_NAME,
        "model_voice": "Faster-Whisper (medium)",
        "voice_loaded": voice_service.model_loaded,
        "environment": "docker" if os.path.exists("/.dockerenv") else "local"
    }
    
    try:
        client = AsyncOpenAI(base_url=f"{LLM_HOST}/v1", api_key="not-needed")
        models = await client.models.list()
        health_status["llm"] = "healthy"
        
        model_ids = [m.id for m in models.data]
        if MODEL_NAME in model_ids:
            health_status["llm_status"] = "available"
        else:
            health_status["llm_status"] = "not_found"
            
    except Exception as e:
        health_status["llm"] = "unhealthy"
        health_status["error"] = str(e)
        return JSONResponse(status_code=503, content=health_status)
    
    return health_status


@app.get("/api/cleanup/status")
async def cleanup_status():
    """Estado de la carpeta de uploads."""
    file_count = 0
    total_size = 0
    
    if UPLOAD_DIR.exists():
        for file_path in UPLOAD_DIR.glob("*"):
            if file_path.is_file():
                file_count += 1
                total_size += file_path.stat().st_size
    
    return {
        "uploads_folder": str(UPLOAD_DIR.absolute()),
        "file_count": file_count,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "cleanup_interval_minutes": CLEANUP_INTERVAL_MINUTES,
        "retention_minutes": FILE_RETENTION_MINUTES
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
