from huggingface_hub import snapshot_download
import os

# Repos para modelo CT2 y tokenizer (para operación offline)
ct2_repo = "JustFrederik/nllb-200-distilled-600M-ct2-int8"
tok_repo = "facebook/nllb-200-distilled-600M"

MODEL_DIR = os.getenv("MODEL_DIR", "model_nllb")
TOKENIZER_DIR = os.path.join(MODEL_DIR, "tokenizer")

print(f"Descargando modelo CT2: {ct2_repo} → {MODEL_DIR}")
snapshot_download(repo_id=ct2_repo, local_dir=MODEL_DIR)

print(f"Descargando tokenizer (SOLO CONFIG): {tok_repo} → {TOKENIZER_DIR}")
# [OPTIMIZACIÓN] Usar allow_patterns para descargar solo ~5MB en lugar de 2.5GB
snapshot_download(
    repo_id=tok_repo, 
    local_dir=TOKENIZER_DIR,
    allow_patterns=["*.json", "*.model", "*.txt"]
)

print("Descarga completada.")