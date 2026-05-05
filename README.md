# 🏦 BoC Translator - Offline Secure Translation System

![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.123-green)
![vLLM](https://img.shields.io/badge/LLM-vLLM--Qwen2.5-orange)
![React](https://img.shields.io/badge/Frontend-React--18-61dafb)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Security](https://img.shields.io/badge/Security-100%25%20Offline-red)

Sistema de traducción empresarial de **Alta Fidelidad** diseñado para entornos de máxima seguridad. Funciona **100% Offline** (sin internet), garantizando que ningún dato confidencial salga de la infraestructura local del Bank of China.

**Idiomas soportados:** Inglés ↔ Español ↔ Chino Simplificado

---

## 🚀 Características Principales

### 💬 Traducción de Texto Seguro (Chat)
- Motor de traducción impulsado por **Qwen2.5-1.5B-Instruct** ejecutándose localmente vía **vLLM** (API compatible con OpenAI)
- Sin límites de caracteres y sin conexión a APIs externas
- Traducción bidireccional instantánea entre los 3 idiomas soportados
- Interfaz conversacional intuitiva (React SPA)

### 📄 Traducción de Documentos "High Fidelity"
Traduce archivos manteniendo su **formato original exacto** (tablas, imágenes, negritas, colores, estilos).

**Formatos Soportados:**
- 📝 `.docx` (Microsoft Word)
- 📊 `.xlsx` (Microsoft Excel)
- 📕 `.pdf` (Portable Document Format)

**Estrategia de Preservación:**
- **Word/Excel:** Modificación *in-place* de las estructuras XML internas para preservar estilos
- **PDF:** Conversión inteligente `PDF → Word → Traducción → PDF` para mantener el diseño visual
- **Garbage Collector:** Limpieza automática de archivos temporales (configurable, 60 min en Docker)

### 🎙️ Traducción de Voz
> ⚠️ **Servicio desactivado** temporalmente por mantenimiento de hardware. El endpoint y la UI existen pero devuelven error.

---

## 🛠️ Stack Tecnológico

| Categoría | Tecnología |
|-----------|------------|
| **Backend** | Python 3.11, FastAPI, Uvicorn |
| **Frontend** | React 18, TypeScript, Vite, TailwindCSS |
| **LLM** | vLLM (Qwen/Qwen2.5-1.5B-Instruct, API OpenAI-compatible) |
| **Reverse Proxy** | Nginx (HTTPS con certificados auto-firmados) |
| **Document Processing** | python-docx, openpyxl, pdf2docx, PyMuPDF, reportlab |
| **Package Manager** | UV (backend), npm (frontend) |

---

## 📋 Requisitos Previos

### Para Docker (recomendado — stack completo)
- 🐳 **Docker + Docker Compose** instalados
- 🎮 **GPU NVIDIA** con drivers actualizados (vLLM requiere GPU)

### Para desarrollo local (backend solamente)
- 🐍 **Python 3.11** instalado
- 📦 **UV** instalado
- 🤖 **vLLM** corriendo con el modelo `Qwen/Qwen2.5-1.5B-Instruct` (requiere GPU)

> **Nota:** El README original mencionaba Ollama — esa información está desactualizada. El backend usa **vLLM** con la API compatible de OpenAI.

---

## ⚙️ Instalación y Configuración

### Opción A: Docker (Stack Completo — Recomendado)

Incluye backend + vLLM + nginx con React SPA + HTTPS.

```bash
# 1. Clonar el repositorio
git clone https://github.com/77ALDO77/Traductor-Local-ES-EN-CH-.git
cd Traductor-Local-ES-EN-CH-

# 2. Construir y levantar todos los servicios
docker compose up -d

# 3. Acceder a la aplicación
# HTTPS: https://localhost (certificado auto-firmado)
# HTTP redirige automáticamente a HTTPS
```

**Servicios que se inician:**

| Servicio | Puerto | Descripción |
|----------|--------|-------------|
| nginx | 80 → 443 | Frontend React SPA + HTTPS + proxy a backend |
| backend | 8000 | FastAPI (accesible vía nginx) |
| vLLM | 8001 | Modelo LLM (interno, accedido por backend) |

**Comandos útiles:**

```bash
docker compose logs -f            # ver logs de todos los servicios
docker compose logs -f backend    # ver solo logs del backend
docker compose restart            # reiniciar servicios
docker compose down               # detener todo
```

**Credenciales de admin (auditoría):**
- Usuario: `admin_boc`
- Contraseña: `seguridad_boc_2026`

### Opción B: Desarrollo Local (Backend Solamente)

Solo el backend FastAPI. Requiere vLLM corriendo por separado.

```bash
# 1. Clonar el repositorio
git clone https://github.com/77ALDO77/Traductor-Local-ES-EN-CH-.git
cd Traductor-Local-ES-EN-CH-

# 2. Sincronizar dependencias
uv sync

# 3. Configurar vLLM (debe estar corriendo antes de iniciar el backend)
# Ejemplo: vllm serve Qwen/Qwen2.5-1.5B-Instruct --port 8001

# 4. Iniciar el backend apuntando a tu instancia de vLLM
LLM_HOST=http://localhost:8001 uv run main.py
```

> **Importante:** El default de `LLM_HOST` es `http://localhost:8000`, que es el mismo puerto del backend. **Siempre configura `LLM_HOST`** al puerto donde corre vLLM.

**Frontend en desarrollo local:**

```bash
cd frontend
npm install
npm run dev       # Vite dev server en http://localhost:5173
```

---

## 📂 Estructura del Proyecto

```
Traductor-Local-ES-EN-CH-/
├── main.py                      # FastAPI app, entry point
├── pyproject.toml               # Backend dependencies (uv)
├── uv.lock                      # Lockfile exacto
├── docker-compose.yml           # Stack: backend + vLLM + nginx
├── Dockerfile                   # Backend container (Python 3.11-slim)
│
├── backend/
│   ├── routers/
│   │   ├── translation.py       # POST /api/translate/text, GET /api/translate/languages
│   │   ├── documents.py         # POST /api/translate/document, GET /api/translate/download/{id}
│   │   ├── voice.py             # Voice endpoints (DISABLED)
│   │   └── admin.py             # Admin audit (HTTP Basic Auth)
│   ├── services/
│   │   ├── llm_service.py       # vLLM via AsyncOpenAI (translation_service singleton)
│   │   ├── document_service.py  # DOCX/XLSX/PDF translation (document_service singleton)
│   │   ├── pdf_translation_service.py  # PDF-specific logic
│   │   ├── audit_service.py     # CSV audit log (audit_service singleton)
│   │   └── voice_service.py     # DUMMY — raises on all calls
│   ├── schemas/                 # Pydantic models
│   ├── auth.py                  # HTTP Basic Auth
│   └── utils.py                 # secure_wipe_and_delete()
│
├── frontend/                    # React 18 + TypeScript + Vite
│   ├── src/
│   │   ├── pages/               # Dashboard, Documents, Voice, Login, AdminAudit
│   │   └── components/          # Sidebar, MainLayout
│   ├── package.json
│   └── dist/                    # Build output (served by nginx in Docker)
│
├── nginx/
│   ├── nginx.conf               # HTTPS + SPA routing + API proxy
│   └── certs/                   # Self-signed TLS certificates
│
└── trad.html                    # Standalone translator page
```

---

## 🔌 Endpoints API

### 📝 Traducción de Texto

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `POST` | `/api/translate/text` | Traducir texto simple |
| `GET` | `/api/translate/languages` | Lista de idiomas soportados |

### 📄 Traducción de Documentos

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `POST` | `/api/translate/document` | Subir y traducir documento |
| `GET` | `/api/translate/download/{file_id}` | Descargar documento traducido |

### 🛡️ Admin (requiere HTTP Basic Auth)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/admin/audit` | Descargar log de auditoría CSV |
| `GET` | `/admin/audit/stats` | Estadísticas de uso |
| `POST` | `/admin/cleanup` | Forzar limpieza de uploads |

### 🔍 Health & Status

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/health` | Estado del sistema (FastAPI + vLLM) |
| `GET` | `/api/cleanup/status` | Estado de la carpeta uploads |

---

## 🔒 Seguridad y Privacidad

### ✅ Garantías de Seguridad

- 🔐 **100% Offline**: Sin conexión a internet requerida después de la instalación
- 🏢 **Datos Locales**: Toda la información permanece en la infraestructura local
- 🗑️ **Auto-limpieza**: Eliminación automática de archivos temporales (configurable)
- 🚫 **Sin Telemetría**: Ningún dato se envía a servidores externos
- 🔒 **HTTPS forzado** en producción (nginx con certificados auto-firmados)
- 🔑 **Admin protegido** con HTTP Basic Auth

### 🛡️ Configuración de Seguridad

Todas las librerías (Hugging Face, vLLM) están configuradas para:
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
| **GPU** | **Requerida (NVIDIA)** | GPU con 4GB+ VRAM |

### 🚀 Optimizaciones Implementadas

- **vLLM**: Motor de inferencia optimizado con PagedAttention
- **Modelo ligero**: Qwen2.5-1.5B para balance entre velocidad y calidad
- **Reintentos automáticos**: Lógica de retry con backoff exponencial en traducciones
- **Caché de modelos**: Carga única en memoria
- **Procesamiento en lotes**: Para documentos largos

---

## 🧰 Comandos Esenciales

```bash
# Docker — Stack completo
docker compose up -d              # iniciar todo
docker compose logs -f            # ver logs
docker compose logs -f backend    # ver logs del backend
docker compose down               # detener todo

# Local dev — Backend
uv sync                           # instalar dependencias
LLM_HOST=http://localhost:8001 uv run main.py   # iniciar backend

# Local dev — Frontend
cd frontend && npm run dev        # Vite dev server
cd frontend && npm run build      # build para producción
cd frontend && npm run lint       # ESLint

# Health check
curl http://localhost:8000/health
```

---

## ⚠️ Solución de Problemas

### Problema: vLLM no responde

```bash
# Docker: verificar que el contenedor está corriendo
docker compose ps

# Ver logs de vLLM
docker compose logs vllm

# Local: verificar que vLLM está corriendo en el puerto correcto
curl http://localhost:8001/v1/models
```

### Problema: Modelo no encontrado en vLLM

```bash
# Verificar que el nombre del modelo coincide
# Docker usa: Qwen/Qwen2.5-1.5B-Instruct
# Variable de entorno: MODEL_NAME
```

### Problema: Error de numpy

```bash
# Reinstalar con versión compatible
uv pip install "numpy<2.0"
```

### Problema: Certificado HTTPS no confiable (Docker)

El certificado es auto-firmado. Acepta la advertencia del navegador o agrega el certificado (`nginx/certs/server.crt`) a tu almacén de confianza.

---

## 🗺️ Roadmap

- [ ] Soporte para más idiomas (árabe, japonés, coreano)
- [ ] Traducción de imágenes con OCR
- [ ] Dashboard de métricas de uso
- [ ] Soporte para archivos `.pptx` (PowerPoint)
- [ ] Modo batch para múltiples documentos
- [ ] Integración con bases de datos corporativas
- [ ] Exportación de glosarios personalizados
- [ ] Sistema de caché para traducciones frecuentes
- [ ] Reactivar servicio de voz (Faster-Whisper)

---

## 📞 Soporte

Para reportar bugs o solicitar nuevas funcionalidades:

- 🐛 [Abrir Issue en GitHub](https://github.com/77ALDO77/Traductor-Local-ES-EN-CH-/issues)
- 💼 Proyecto: Bank of China - Software Engineering

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
