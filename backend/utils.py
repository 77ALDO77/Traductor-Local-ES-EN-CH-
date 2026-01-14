import os
from pathlib import Path

def secure_wipe_and_delete(file_path: Path):
    """Sobrescribe el archivo con bytes aleatorios antes de borrarlo."""
    try:
        if file_path.exists():
            size = file_path.stat().st_size
            with open(file_path, "ba+", buffering=0) as f:
                f.write(os.urandom(size))
            os.remove(file_path)
    except Exception as e:
        print(f"Error secure wipe {file_path}: {e}")
