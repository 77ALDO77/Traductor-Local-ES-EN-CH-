import csv
import io
from fastapi import APIRouter, Depends, HTTPException
from backend.auth import verify_admin
from backend.services.audit_service import AUDIT_FILE
from backend.services.llm_service import translation_service
import httpx
import os

router = APIRouter(prefix="/api/admin", tags=["Admin"])

@router.get("/audit-logs")
async def get_audit_logs(username: str = Depends(verify_admin)):
    """
    Retorna los logs de auditoría en formato JSON.
    Solo accesible para administradores.
    """
    if not AUDIT_FILE.exists():
        return []
        
    logs = []
    try:
        with open(AUDIT_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                logs.append(row)
        # Retornar los más recientes primero
        return list(reversed(logs))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error leyendo logs: {str(e)}")

@router.get("/files")
async def list_files(username: str = Depends(verify_admin)):
    """Lista archivos residuales en el directorio de subidas."""
    try:
        from backend.services.document_service import UPLOAD_DIR
        files = []
        for f in UPLOAD_DIR.iterdir():
            if f.is_file() and f.name != ".gitkeep": # Ignorar directorios como 'audit'
                stats = f.stat()
                files.append({
                    "name": f.name,
                    "size": stats.st_size,
                    "created": stats.st_ctime
                })
        return sorted(files, key=lambda x: x['created'], reverse=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/files/{filename}")
async def delete_file(filename: str, username: str = Depends(verify_admin)):
    """Elimina y 'wipea' un archivo residual manualmente."""
    try:
        from backend.services.document_service import UPLOAD_DIR
        from backend.utils import secure_wipe_and_delete
        from backend.services.audit_service import audit_service
        
        file_path = UPLOAD_DIR / filename
        
        # Security check: prevent directory traversal
        if not file_path.resolve().is_relative_to(UPLOAD_DIR.resolve()):
             raise HTTPException(status_code=400, detail="Invalid path")

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Archivo no encontrado")
            
        secure_wipe_and_delete(file_path)
        audit_service.log_event("MANUAL_DELETE", filename, "WIPED", "Admin manual cleanup")
        
        return {"message": "Archivo eliminado de forma segura"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/files")
async def delete_all_files(username: str = Depends(verify_admin)):
    """Elimina todos los archivos residuales de forma segura."""
    try:
        from backend.services.document_service import UPLOAD_DIR
        from backend.utils import secure_wipe_and_delete
        from backend.services.audit_service import audit_service
        
        deleted_files = []
        errors = []
        
        for file_path in UPLOAD_DIR.iterdir():
            if file_path.is_file() and file_path.name != ".gitkeep":
                try:
                    secure_wipe_and_delete(file_path)
                    deleted_files.append(file_path.name)
                    audit_service.log_event("BULK_DELETE", file_path.name, "WIPED", "Admin bulk cleanup")
                except Exception as e:
                    errors.append(f"{file_path.name}: {str(e)}")
        
        return {
            "message": f"Eliminados {len(deleted_files)} archivo(s)",
            "deleted": deleted_files,
            "errors": errors
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Model Management ---

from pydantic import BaseModel

class ModelSelectRequest(BaseModel):
    model: str

@router.get("/models")
async def list_models(username: str = Depends(verify_admin)):
    """Lista todos los modelos disponibles en Ollama."""
    try:
        models = await translation_service.list_available_models()
        current = translation_service.get_model()
        return {
            "models": models,
            "current_model": current
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error consultando vLLM: {str(e)}")

@router.get("/models/current")
async def get_current_model(username: str = Depends(verify_admin)):
    """Retorna el modelo actualmente en uso."""
    try:
        model = translation_service.get_model()
        available = await translation_service.check_model_available()
        return {
            "model": model,
            "available": available,
            "warning": None if available else f"Modelo '{model}' no encontrado en vLLM"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/models/select")
async def select_model(request: ModelSelectRequest, username: str = Depends(verify_admin)):
    """Cambia el modelo activo para traducciones."""
    try:
        models = await translation_service.list_available_models()
        model_names = [m["name"] for m in models]

        if not model_names:
            raise HTTPException(status_code=503, detail="No hay modelos disponibles en vLLM")

        if request.model not in model_names:
            raise HTTPException(
                status_code=400,
                detail=f"Modelo '{request.model}' no disponible. Disponibles: {', '.join(model_names)}"
            )

        old_model = translation_service.get_model()
        translation_service.set_model(request.model)

        from backend.services.audit_service import audit_service
        audit_service.log_event(
            "MODEL_SWITCH",
            request.model,
            "SWITCHED",
            f"Previous: {old_model} -> New: {request.model}"
        )

        return {
            "status": "success",
            "previous_model": old_model,
            "current_model": request.model
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- System Monitor ---

TRANSLATOR_ENGINE_URL = os.getenv("TRANSLATOR_ENGINE_URL", "http://translator_engine:9000")
LLM_HOST = os.getenv("LLM_HOST", "http://localhost:8000")

@router.get("/system")
async def get_system_status(username: str = Depends(verify_admin)):
    """Obtiene estado agregado de CPU/RAM/GPU y modelos."""
    try:
        # Get Translator Engine Stats (Direct GPU access there)
        async with httpx.AsyncClient() as client:
            try:
                te_resp = await client.get(f"{TRANSLATOR_ENGINE_URL}/status", timeout=2.0)
                te_data = te_resp.json()
            except Exception:
                te_data = {"error": "Translator Engine offline"}

            # Get vLLM Stats (list running models)
            vllm_models = []
            try:
                vl_resp = await client.get(f"{LLM_HOST}/v1/models", timeout=2.0)
                if vl_resp.status_code == 200:
                    vllm_models = vl_resp.json().get("data", [])
            except Exception:
                pass

        return {
            "translator_engine": te_data,
            "llm": {
                "models": vllm_models,
                "count": len(vllm_models)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/system/optimize")
async def optimize_system(username: str = Depends(verify_admin)):
    """Libera recursos en todos los servicios."""
    results = {}
    async with httpx.AsyncClient() as client:
        # 1. Cleanup Translator Engine
        try:
            resp = await client.post(f"{TRANSLATOR_ENGINE_URL}/cleanup", timeout=5.0)
            results["translator_engine"] = resp.json()
        except Exception as e:
            results["translator_engine"] = {"error": str(e)}

        # 2. vLLM memory management is automatic
        results["llm"] = "Managed by vLLM"

    return results
