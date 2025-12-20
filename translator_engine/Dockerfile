# Usamos una imagen base de NVIDIA que ya tiene CUDA y CUDNN preinstalados
# Esto es OBLIGATORIO para que ctranslate2 pueda ver tu GPU
FROM nvidia/cuda:12.2.2-cudnn8-runtime-ubuntu22.04

WORKDIR /app

# 1. Instalar Python 3.10 y pip (La imagen de NVIDIA viene "pelada" sin Python)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 2. Hacemos un alias para que 'python' ejecute 'python3'
RUN ln -s /usr/bin/python3 /usr/bin/python

# 3. Instalar librerías
# IMPORTANTE: Fijamos ctranslate2==4.4.0 porque es la versión más estable para CUDNN 8
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    ctranslate2==4.4.0 \
    sentencepiece \
    transformers \
    huggingface_hub \
    faster-whisper \
    soundfile \
    python-multipart

COPY . .

# 4. Descargar el modelo
# Usamos una ruta fuera de /app para que el volumen de desarrollo no la oculte
RUN mkdir -p /models/nllb

ENV MODEL_DIR=/models/nllb \
    NMT_DEVICE=cuda \
    NMT_COMPUTE_TYPE=float16 \
    MAX_BATCH_SIZE=32
RUN python downloader.py

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9000"]