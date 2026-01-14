# Dockerfile FINAL - Corregido y Optimizado
FROM python:3.11-slim

LABEL maintainer="BoC Translator Team"
LABEL description="Backend de traducción offline para Banco de China"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# 1. Instalar dependencias del sistema
# Agrego libreoffice, ffmpeg, curl y fuentes CJK para soporte completo
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    libgomp1 \
    libreoffice \
    libreoffice-java-common \
    default-jre \
    dos2unix \
    fonts-liberation \
    fonts-noto-cjk \
    fonts-noto-cjk-extra \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 2. INSTALAR UV (Método Infalible: Copy from image)
# Copiamos el ejecutable directamente de la imagen oficial a la carpeta global
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# 3. Copiar archivos de dependencias
COPY pyproject.toml uv.lock ./

# 4. Instalar dependencias
# --frozen: usa las versiones exactas del lockfile
# Configurar timeout de UV para redes lentas
ENV UV_HTTP_TIMEOUT=500

RUN uv sync --frozen --no-dev

# 5. Copiar el código
COPY backend ./backend
COPY static ./static
COPY templates ./templates
COPY main.py ./

# 6. Crear carpetas y asignar permisos
RUN mkdir -p uploads models && \
    chmod -R 777 uploads models

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# 7. Crear usuario seguro
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Añadir el entorno virtual al PATH para que appuser lo use por defecto
ENV PATH="/app/.venv/bin:$PATH"

USER appuser

# Comando de inicio
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]