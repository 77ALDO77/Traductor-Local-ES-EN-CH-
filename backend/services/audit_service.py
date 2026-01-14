import csv
import os
import threading
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

# Configuración
UPLOAD_DIR = Path("uploads")
AUDIT_DIR = UPLOAD_DIR / "audit"
AUDIT_FILE = AUDIT_DIR / "audit_log.csv"

class AuditService:
    def __init__(self):
        self._lock = threading.Lock()
        self._ensure_audit_dir()

    def _ensure_audit_dir(self):
        """Assegura que el directorio de auditoría exista."""
        if not AUDIT_DIR.exists():
            AUDIT_DIR.mkdir(parents=True, exist_ok=True)
            # Crear archivo si no existe con cabeceras
            if not AUDIT_FILE.exists():
                with open(AUDIT_FILE, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Timestamp", "Action", "Filename", "Status", "Details"])

    def log_event(self, action: str, filename: str, status: str, details: str = ""):
        """Registra un evento en el log de auditoría de manera thread-safe."""
        timestamp = datetime.now(ZoneInfo("America/Lima")).isoformat()
        
        with self._lock:
            try:
                self._ensure_audit_dir() # Doble check por seguridad
                with open(AUDIT_FILE, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([timestamp, action, filename, status, details])
            except Exception as e:
                print(f"ERROR AUDIT LOG: {e}")

audit_service = AuditService()
