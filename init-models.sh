#!/bin/bash
set -e

echo "🚀 Iniciando BoC_Translator - Configuración Offline"

echo "📦 Construyendo imágenes Docker..."
docker compose build

echo "▶️  Iniciando servicios..."
docker compose up -d

echo "⏳ Esperando a que Ollama esté disponible..."
until docker exec boc_translator_ollama_v1 ollama list > /dev/null 2>&1; do
    echo "   Esperando Ollama..."
    sleep 5
done

echo "✅ Ollama listo"

echo "📥 Verificando modelo Qwen2.5:3b..."
if ! docker exec boc_translator_ollama_v1 ollama list | grep -q "qwen2.5:3b"; then
    echo "   Descargando Qwen2.5:3b (~4GB)..."
    docker exec boc_translator_ollama_v1 ollama pull qwen2.5:3b
    echo "✅ Qwen2.5:3b descargado"
else
    echo "✅ Qwen2.5:3b ya existe"
fi

echo "🎤 El modelo Whisper se descargará en el primer uso del micrófono"

echo ""
echo "✅ BoC_Translator configurado correctamente"
echo ""
echo "🌐 Accede a la aplicación en: http://localhost:7000"
echo ""
echo "📊 Comandos útiles:"
echo "   Ver logs:      docker compose logs -f"
echo "   Reiniciar:     docker compose restart"
echo "   Detener:       docker compose down"
echo "   Estado:        docker compose ps"
