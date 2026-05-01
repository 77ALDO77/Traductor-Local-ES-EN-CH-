# 🏦 BoC Translator - Offline Secure Translation System

![Python](https://img.shields.io/badge/Python-3.10-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green)
![Ollama](https://img.shields.io/badge/LLM-Qwen2.5-orange)
![Whisper](https://img.shields.io/badge/ASR-Faster--Whisper-purple)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Security](https://img.shields.io/badge/Security-100%25%20Offline-red)

Sistema de traducción empresarial de **Alta Fidelidad** diseñado para entornos de máxima seguridad. Funciona **100% Offline** (sin internet), garantizando que ningún dato confidencial salga de la infraestructura local del Bank of China.

---

## 🚀 Características Principales

### 💬 Traducción de Texto Seguro (Chat)
- Motor de traducción impulsado por **Qwen 2.5 (7B)** ejecutándose localmente vía Ollama
- Sin límites de caracteres y sin conexión a APIs externas
- Traducción bidireccional instantánea
- Interfaz conversacional intuitiva

### 📄 Traducción de Documentos "High Fidelity"
Traduce archivos manteniendo su **formato original exacto** (tablas, imágenes, negritas, colores, estilos).

**Formatos Soportados:**
- 📝 `.docx` (Microsoft Word)
- 📊 `.xlsx` (Microsoft Excel)
- 📕 `.pdf` (Portable Document Format)

**Estrategia de Preservación:**
- **Word/Excel:** Modificación *in-place* de las estructuras XML internas para preservar estilos
- **PDF:** Conversión inteligente `PDF → Word → Traducción → PDF` para mantener el diseño visual
- **Garbage Collector:** Limpieza automática de archivos temporales cada 10 minutos

### 🎙️ Traducción de Voz en Tiempo Real
Sistema de reconocimiento de voz (ASR) de baja latencia con capacidades avanzadas.

**Características:**
- Motor: `Faster-Whisper` (implementación optimizada CTranslate2)
- Modelo: `medium` (int8) para balance perfecto entre precisión y velocidad en CPU
- Detección automática de idioma
- Filtrado de ruido (VAD - Voice Activity Detection)
- Traducción instantánea del audio transcrito
- Soporte para múltiples idiomas

---

## 🛠️ Stack Tecnológico

| Categoría | Tecnología |
|-----------|------------|
| **Backend** | Python 3.10, FastAPI, Uvicorn |
| **Frontend** | HTML5, JavaScript (Vanilla), TailwindCSS |
| **LLM** | Ollama (Qwen 2.5 - 7B) |
| **Audio Processing** | Faster-Whisper, FFmpeg |
| **Document Processing** | python-docx, openpyxl, pdf2docx, docx2pdf |
| **Package Manager** | UV (entornos virtuales rápidos) |

---

## 📋 Requisitos Previos

Antes de instalar, asegúrate de tener:

- 🐍 **Python 3.10** instalado
- 🤖 **Ollama** instalado y ejecutándose ([Descargar Ollama](https://ollama.com/))
- 🎬 **FFmpeg** instalado y agregado al PATH del sistema
- 📦 **UV** instalado (`pip install uv`)

---

## ⚙️ Instalación y Configuración

### 1️⃣ Clonar el Repositorio

```bash
git clone https://github.com/77ALDO77/Traductor-Local-ES-EN-CH-.git
cd Traductor-Local-ES-EN-CH-
```

### 2️⃣ Configurar el Entorno (usando UV)

El proyecto usa `uv` para gestionar dependencias y fijar Python 3.10.

```bash
# Crear entorno virtual y sincronizar dependencias
uv sync
```

### 3️⃣ Descargar el Modelo LLM

Asegúrate de que Ollama esté corriendo y descarga el modelo Qwen:

```bash
ollama pull qwen2.5:7b
```

### 4️⃣ Instalar FFmpeg

#### Windows
```powershell
# PowerShell como Administrador
winget install Gyan.FFmpeg

# REINICIA tu terminal después de este paso
```

#### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install ffmpeg
```

#### macOS
```bash
brew install ffmpeg
```

### 5️⃣ Verificar Instalación

```bash
# Verificar Python
python --version

# Verificar Ollama
ollama list

# Verificar FFmpeg
ffmpeg -version
```

---

## ▶️ Ejecución

Para iniciar el servidor de desarrollo:

```bash
uv run main.py
```

El servidor iniciará en: **http://localhost:8000**

### 🎯 Primer Uso

⚠️ **Nota Importante:** La primera vez que accedas a la sección de **Voz**, el sistema descargará automáticamente el modelo `faster-whisper-medium` (~1.5 GB). Este proceso ocurre **solo una vez** y se almacena en caché local.

---

## 📂 Estructura del Proyecto

```
BoC-Translator/
├── backend/
│   ├── routers/              # Endpoints (Texto, Documentos, Voz)
│   │   ├── chat.py
│   │   ├── documents.py
│   │   └── voice.py
│   ├── services/             # Lógica de negocio
│   │   ├── llm_service.py    # Integración con Ollama
│   │   ├── whisper_service.py # ASR con Faster-Whisper
│   │   └── document_parser.py # Procesamiento de documentos
│   └── schemas/              # Modelos Pydantic
│       └── translation.py
│
├── static/                   # Assets frontend
│   ├── css/
│   ├── js/
│   └── images/
│
├── templates/                # Vistas HTML (Jinja2)
│   ├── index.html
│   ├── chat.html
│   ├── documents.html
│   └── voice.html
│
├── uploads/                  # Almacenamiento temporal (Auto-limpiable)
├── models/                   # Caché local de modelos de audio
├── main.py                   # Punto de entrada de la aplicación
├── pyproject.toml            # Configuración de dependencias (UV)
├── .gitignore
└── README.md
```

---

## 🔌 Endpoints API

### 📝 Traducción de Texto

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `POST` | `/api/translate/text` | Traducir texto simple |
| `POST` | `/api/translate/chat` | Chat conversacional con historial |

### 📄 Traducción de Documentos

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `POST` | `/api/translate/document` | Subir y traducir documento |
| `GET` | `/api/translate/download/{file_id}` | Descargar documento traducido |

### 🎙️ Traducción de Voz

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `POST` | `/api/translate/voice` | Transcribir y traducir audio |
| `GET` | `/api/voice/status` | Estado del servicio ASR |

---

## 🎯 Guía de Uso

### 💬 Traducción de Texto

1. Accede a la sección **Chat**
2. Selecciona idioma origen y destino
3. Escribe o pega tu texto
4. Haz clic en **Traducir**
5. Copia el resultado o continúa la conversación

### 📄 Traducción de Documentos

1. Accede a la sección **Documentos**
2. Arrastra tu archivo o haz clic para seleccionar
3. Selecciona idiomas de traducción
4. Espera el procesamiento (el tiempo varía según el tamaño)
5. Descarga el archivo traducido con formato preservado

### 🎙️ Traducción de Voz

1. Accede a la sección **Voz**
2. Permite permisos de micrófono
3. Selecciona idioma destino
4. Haz clic en **Grabar** y habla claramente
5. Detén la grabación
6. Obtén transcripción y traducción instantáneas

---

## 🔒 Seguridad y Privacidad

### ✅ Garantías de Seguridad

- 🔐 **100% Offline**: Sin conexión a internet requerida después de la instalación
- 🏢 **Datos Locales**: Toda la información permanece en la infraestructura local
- 🗑️ **Auto-limpieza**: Eliminación automática de archivos temporales cada 10 minutos
- 🚫 **Sin Telemetría**: Ningún dato se envía a servidores externos
- 🔒 **Sin Logging Externo**: Los logs permanecen en el servidor local

### 🛡️ Configuración de Seguridad

Todas las librerías (Hugging Face, Ollama) están configuradas para:
- Trabajar con caché local
- No enviar métricas
- No realizar llamadas externas
- Operar completamente offline

---

## ⚡ Optimización y Rendimiento

### 💻 Requisitos de Hardware Recomendados

| Componente | Mínimo | Recomendado |
|------------|--------|-------------|
| **CPU** | Intel i5 (8ª gen) | Intel i9 / AMD Ryzen 9 |
| **RAM** | 8 GB | 16 GB+ |
| **Almacenamiento** | 20 GB libres | 50 GB+ SSD |
| **GPU** | No requerida | Opcional (acelera ASR) |

### 🚀 Optimizaciones Implementadas

- **Cuantización int8**: Reducción de memoria sin pérdida significativa de precisión
- **CTranslate2**: Motor optimizado para inferencia rápida
- **Procesamiento en lotes**: Para documentos largos
- **Caché de modelos**: Carga única en memoria
- **VAD (Voice Activity Detection)**: Reduce procesamiento innecesario

---

## 🧰 Comandos Esenciales

```bash
# Iniciar servidor de desarrollo
uv run main.py

# Verificar dependencias
uv sync

# Limpiar caché de modelos
rm -rf models/

# Ver logs en tiempo real
tail -f logs/app.log

# Verificar estado de Ollama
ollama ps

# Listar modelos descargados
ollama list
```

---

## 🧪 Testing

```bash
# Ejecutar tests unitarios
uv run pytest

# Tests con cobertura
uv run pytest --cov=backend

# Tests de integración
uv run pytest tests/integration/
```

---

## ⚠️ Solución de Problemas

### Problema: Ollama no responde

```bash
# Reiniciar servicio de Ollama
ollama serve

# Verificar que el modelo esté descargado
ollama list
```

### Problema: FFmpeg no encontrado

```bash
# Windows: Verificar PATH
echo $env:PATH

# Linux/Mac: Verificar instalación
which ffmpeg
```

### Problema: Error de numpy

```bash
# Reinstalar con versión compatible
uv pip install "numpy<2.0"
```

### Problema: Modelo de Whisper no descarga

```bash
# Descargar manualmente
python -c "from faster_whisper import WhisperModel; WhisperModel('medium')"
```

---

## 🗺️ Roadmap

- [ ] Soporte para más idiomas (árabe, japonés, coreano)
- [ ] Traducción de imágenes con OCR
- [ ] API REST completa con autenticación JWT
- [ ] Dashboard de métricas de uso
- [ ] Soporte para archivos `.pptx` (PowerPoint)
- [ ] Modo batch para múltiples documentos
- [ ] Integración con bases de datos corporativas
- [ ] Exportación de glosarios personalizados
- [ ] Sistema de caché para traducciones frecuentes
- [ ] Dockerización para despliegue simplificado

---

## 🤝 Contribuciones

Las contribuciones son bienvenidas para mejorar este sistema empresarial.

### 📝 Guías de Contribución

1. Haz fork del proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Asegúrate de que los tests pasen (`uv run pytest`)
4. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
5. Push a la rama (`git push origin feature/AmazingFeature`)
6. Abre un Pull Request

### 🔍 Áreas de Mejora

- Optimización de velocidad de traducción
- Mejora de precisión en documentos técnicos
- Soporte para más formatos de archivo
- Mejoras en la UI/UX
- Documentación adicional

---

## 📚 Documentación Adicional

- [Guía de Instalación Detallada](docs/installation.md)
- [Configuración Avanzada](docs/configuration.md)
- [API Reference](docs/api.md)
- [Troubleshooting Guide](docs/troubleshooting.md)
- [Security Best Practices](docs/security.md)

---

## 📞 Soporte

Para reportar bugs o solicitar nuevas funcionalidades:

- 🐛 [Abrir Issue en GitHub](https://github.com/77ALDO77/Traductor-Local-ES-EN-CH-/issues)
- 📧 Email: tu-email@ejemplo.com
- 💼 Proyecto: Bank of China - Software Engineering

---

## 🙏 Agradecimientos

- 🎓 Proyecto: Ingeniería de Software - Bank of China

---

## ⭐ Dale una Estrella

Si este proyecto te resulta útil para tu organización, **considera darle una estrella en GitHub**!

[![GitHub stars](https://img.shields.io/github/stars/77ALDO77/Traductor-Local-ES-EN-CH-?style=social)](https://github.com/77ALDO77/Traductor-Local-ES-EN-CH-/stargazers)

---

## 📝 Licencia

Este proyecto está bajo la **MIT License**.

```
MIT License

Copyright (c) 2025

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

<div align="center">

**🔒 Sistema Desarrollado para Entornos de Máxima Seguridad**

*Traducción empresarial sin comprometer la seguridad de tus datos*

</div>