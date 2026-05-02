#!/bin/bash
set -e

echo "🚀 Iniciando BoC_Translator - Configuración Offline"

echo "📦 Construyendo imágenes Docker..."
docker compose build

echo "▶️  Iniciando servicios..."
docker compose up -d

echo "⏳ Esperando a que vLLM esté disponible..."
MAX_WAIT=300
ELAPSED=0
until curl -sf http://localhost:8001/v1/models > /dev/null 2>&1; do
    ELAPSED=$((ELAPSED + 5))
    if [ $ELAPSED -ge $MAX_WAIT ]; then
        echo "❌ Timeout esperando vLLM (${MAX_WAIT}s). Revisa: docker compose logs vllm"
        exit 1
    fi
    echo "   Esperando vLLM (${ELAPSED}s)..."
    sleep 5
done

echo "✅ vLLM listo"
echo "   Modelos disponibles:"
curl -s http://localhost:8001/v1/models | python3 -m json.tool 2>/dev/null || echo "   (no se pudo parsear)"

echo ""
echo "🎤 El modelo Whisper se descargará en el primer uso del micrófono"
echo ""
echo "✅ BoC_Translator configurado correctamente"
echo ""
echo "🌐 Accede a la aplicación en: https://localhost"
echo ""
echo "📊 Comandos útiles:"
echo "   Ver logs:      docker compose logs -f"
echo "   Reiniciar:     docker compose restart"
echo "   Detener:       docker compose down"
echo "   Estado:        docker compose ps"
