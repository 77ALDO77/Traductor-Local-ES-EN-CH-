from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import ctranslate2
import transformers
import os
import time
import tempfile
import shutil
import io
import subprocess
import soundfile as sf
from typing import List, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from faster_whisper import WhisperModel
import gc

app = FastAPI()

# Configuración por variables de entorno (GPU en dev)
MODEL_DIR = os.getenv("MODEL_DIR", "model_nllb")
NMT_DEVICE = os.getenv("NMT_DEVICE", "cuda")  # cuda | cpu
NMT_COMPUTE_TYPE = os.getenv("NMT_COMPUTE_TYPE", "float16")  # float16 recomendado en GPU
MAX_BATCH_SIZE = int(os.getenv("MAX_BATCH_SIZE", "32"))

# Cargar traductor (CTranslate2)
translator = ctranslate2.Translator(
    MODEL_DIR,
    device=NMT_DEVICE,
    compute_type=NMT_COMPUTE_TYPE
)

# Cargar tokenizer local si existe, si no usar HF como fallback (solo dev)
TOKENIZER_DIR = os.path.join(MODEL_DIR, "tokenizer")
if os.path.isdir(TOKENIZER_DIR):
    tokenizer = transformers.AutoTokenizer.from_pretrained(TOKENIZER_DIR, use_fast=True)
else:
    # Nota: para 100% offline, asegúrate de que TOKENIZER_DIR exista en la imagen
    tokenizer = transformers.AutoTokenizer.from_pretrained(
        "facebook/nllb-200-distilled-600M", use_fast=True
    )

class TranslationRequest(BaseModel):
    text: str
    source_lang: str  # Códigos FLORES-200 (ej: 'eng_Latn', 'spa_Latn')
    target_lang: str
    # Permitir texto largo (segmentación interna)

# Mapeo simple de nombres comunes a códigos FLORES-200
LANG_MAP = {
    "Spanish": "spa_Latn",
    "English": "eng_Latn",
    "Chinese": "zho_Hans",
    "French": "fra_Latn",
    # ... agrega más según necesites
}

def _segment_text(text: str) -> List[str]:
    """Segmenta en oraciones de forma simple. Para chino, segmentación por signos específicos."""
    # Segmentación ligera: separar por saltos de línea y puntos.
    # Se puede mejorar con sacremoses o spacy si se requiere.
    if not text:
        return []
    # Normalización mínima
    parts = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Dividir por puntos/preguntas/exclamaciones conservando el caracter
        buf = ""
        for ch in line:
            buf += ch
            if ch in ".!?。！？":
                if buf.strip():
                    parts.append(buf.strip())
                buf = ""
        if buf.strip():
            parts.append(buf.strip())
    return parts


def _prepare_inputs(sentences: List[str], src_code: str) -> List[List[str]]:
    inputs = []
    # Set the source language for the tokenizer
    if hasattr(tokenizer, "src_lang"):
        tokenizer.src_lang = src_code
        
    for s in sentences:
        # Encode without src_lang kwarg
        tokenized = tokenizer.convert_ids_to_tokens(tokenizer.encode(s))
        inputs.append(tokenized)
    return inputs


@app.post("/translate")
async def translate(request: TranslationRequest):
    start = time.time()

    src_code = LANG_MAP.get(request.source_lang, request.source_lang)
    tgt_code = LANG_MAP.get(request.target_lang, request.target_lang)

    if not src_code or not tgt_code:
        # Fallback simple si no encuentra el código exacto
        src_code = "eng_Latn"
        tgt_code = "spa_Latn"

    # Segmentar texto
    sentences = _segment_text(request.text)
    if not sentences:
        return {"translated_text": "", "time_ms": (time.time() - start) * 1000}

    # Preparar lotes
    inputs = _prepare_inputs(sentences, src_code)

    translated_segments: List[str] = []
    # Procesar en batches
    for i in range(0, len(inputs), MAX_BATCH_SIZE):
        batch = inputs[i:i + MAX_BATCH_SIZE]
        results = translator.translate_batch(
            batch,
            # Forzar idioma destino con prefijo
            target_prefix=[[tgt_code] for _ in batch],
            beam_size=1,  # baja latencia
            max_decoding_length=512
        )
        for res in results:
            target_tokens = res.hypotheses[0]
            decoded = tokenizer.decode(tokenizer.convert_tokens_to_ids(target_tokens))
            translated_segments.append(decoded)

    translated_text = " ".join(translated_segments)

    return {
        "translated_text": translated_text,
        "time_ms": (time.time() - start) * 1000
    }


# --- Whisper Implementation ---

WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "medium")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cuda")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "float16")

whisper_model = None

def get_whisper_model():
    global whisper_model
    if whisper_model is None:
        print(f"Loading Whisper Model: {WHISPER_MODEL_SIZE} on {WHISPER_DEVICE}...")
        whisper_model = WhisperModel(
            WHISPER_MODEL_SIZE, 
            device=WHISPER_DEVICE, 
            compute_type=WHISPER_COMPUTE_TYPE,
            download_root="models_whisper"
        )
    return whisper_model

def convert_to_wav(input_path: str) -> str:
    """Converts audio to 16kHz mono WAV using ffmpeg CLI."""
    output_path = input_path + ".wav"
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", input_path, "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", output_path],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg conversion failed: {e}")
        # Fallback: return original path and hope for the best
        return input_path

@app.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    language: Optional[str] = Form(None)
):
    start = time.time()
    tmp_path = None
    wav_path = None
    try:
        model = get_whisper_model()
        
        # Save temp file
        # Use .webm suffix if uploaded file is webm, helps ffmpeg probe
        original_ext = ".webm" 
        if file.filename:
             ext = os.path.splitext(file.filename)[1]
             if ext: original_ext = ext
             
        with tempfile.NamedTemporaryFile(suffix=original_ext, delete=False) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name
        
        # Convert to WAV explicitly using system ffmpeg
        # This bypasses PyAV's direct handling of WebM which is causing issues
        wav_path = convert_to_wav(tmp_path)
        
        # Pass WAV to whisper
        segments, info = model.transcribe(
            wav_path, 
            language=language,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500)
        )
        
        text = " ".join([s.text for s in segments]).strip()
        
        return {
            "text": text,
            "language": info.language,
            "processing_time": (time.time() - start) * 1000
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# --- System & Helper Endpoints ---

def _get_gpu_status():
    """Obtiene estado de GPU usando nvidia-smi."""
    try:
        # Query total and used memory
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total,memory.used,utilization.gpu", "--format=csv,nounits,noheader"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if lines:
                total, used, util = lines[0].split(',')
                return {
                    "vram_total_mb": int(total),
                    "vram_used_mb": int(used),
                    "gpu_util_percent": int(util)
                }
    except Exception as e:
        print(f"Error reading GPU stats: {e}")
    return None

@app.get("/status")
def get_status():
    """Retorna estado del sistema y modelos cargados."""
    gpu_stats = _get_gpu_status()
    
    # RAM usage (simple approximation using psutil if available or /proc/meminfo)
    ram_stats = {"percent": 0, "used_gb": 0, "total_gb": 0}
    try:
        import psutil
        mem = psutil.virtual_memory()
        ram_stats = {
            "percent": mem.percent,
            "used_gb": round(mem.used / (1024**3), 2),
            "total_gb": round(mem.total / (1024**3), 2)
        }
    except ImportError:
        pass

    return {
        "gpu": gpu_stats,
        "ram": ram_stats,
        "loaded_models": {
            "nllb": True, # Always loaded in this architecture
            "whisper": whisper_model is not None
        }
    }

@app.post("/cleanup")
def cleanup_resources():
    """Fuerza la liberación de memoria (GC)."""
    global whisper_model
    
    # Force GC
    gc.collect()
    
    # CTranslate2 manages its own memory. We rely on GC.
    
    return {"status": "cleaned", "message": "Memory cleanup triggered (GC)"}

@app.post("/transcribe_chunk")
async def transcribe_chunk(
    audio_data: bytes = File(...),
    sample_rate: int = Form(16000),
    language: Optional[str] = Form(None)
):
    start = time.time()
    try:
        model = get_whisper_model()
        
        # Convert bytes to wav temp file for faster-whisper
        # (faster-whisper accepts file path or file-like object, but file path is often safer for formats)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
            # If it's raw bytes/float32, we might need soundfile to write it properly if it's not a container format
            # Assuming 'audio_data' comes as container format (e.g. webm chunk) or raw pcm?
            # The previous implementation in backend used sf.read on the bytes.
            # Let's assume it handles what soundfile can handle.
            
            try:
                # Try reading as container
                data, sr = sf.read(io.BytesIO(audio_data))
                sf.write(tmp_path, data, sample_rate)
            except Exception:
                # Fallback: maybe just write bytes directly if it is a valid file
                with open(tmp_path, 'wb') as f:
                    f.write(audio_data)

        segments, info = model.transcribe(
            tmp_path,
            language=language,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500)
        )
        
        text = " ".join([s.text for s in segments]).strip()
        
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
            
        return {
            "text": text,
            "language": info.language,
            "processing_time": (time.time() - start) * 1000
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error transcribing chunk: {e}")
        raise HTTPException(status_code=500, detail=str(e))