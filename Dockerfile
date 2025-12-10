# Dockerfile FINAL - Corregido para permisos de usuario
FROM python:3.11-slim

LABEL maintainer="BoC Translator Team"
LABEL description="Backend de traducción offline para Banco de China"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Instalar dependencias del sistema (FFMPEG es vital)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    libgomp1 \
    libreoffice \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

# INSTALAR UV (Forma segura para multi-usuario)
# Lo descargamos y lo movemos a /usr/local/bin para que 'appuser' pueda ejecutarlo
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    mv /root/.cargo/bin/uv /usr/local/bin/uv

WORKDIR /app

# Copiar archivos de dependencias
COPY pyproject.toml uv.lock ./

# Instalar dependencias (system-wide dentro del contenedor o en .venv)
# Usamos --frozen para respetar el lockfile
RUN uv sync --frozen --no-dev

# Copiar el código
COPY backend ./backend
COPY static ./static
COPY templates ./templates
COPY main.py ./

# Crear carpetas y asignar permisos
RUN mkdir -p uploads models && \
    chmod -R 777 uploads models

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# Crear usuario seguro
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Añadir el entorno virtual al PATH para que appuser lo use por defecto
ENV PATH="/app/.venv/bin:$PATH"

USER appuser

# Comando de inicio
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]