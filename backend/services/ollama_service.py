"""
Servicio de integración con Ollama para traducciones.
"""

import os
import time
import asyncio
import logging
import httpx
from ollama import AsyncClient, ResponseError

logger = logging.getLogger(__name__)


# Configuración desde variables de entorno
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen2.5:3b")


class FastTranslationService:
    async def translate(self, text: str, source_lang: str, target_lang: str):
        """
        Traduce usando el servicio NMT local (translator_engine).

        Maneja errores de red/JSON y normaliza la respuesta para el backend
        (convierte "time_ms" -> "processing_time_ms").
        """
        url = "http://translator_engine:9000/translate"
        payload = {
            "text": text,
            "source_lang": source_lang,
            "target_lang": target_lang,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload)

            if resp.status_code // 100 != 2:
                content_snippet = (resp.text or "").strip()[:300]
                raise Exception(
                    f"translator_engine devolvió {resp.status_code}: {content_snippet}"
                )

            try:
                data = resp.json()
            except Exception:
                content_snippet = (resp.text or "").strip()[:300]
                raise Exception(
                    f"Respuesta no-JSON desde translator_engine: {content_snippet}"
                )

            translated = data.get("translated_text", "")
            time_ms = data.get("time_ms")

            return {
                "translated_text": translated,
                "processing_time_ms": round(float(time_ms), 2)
                if isinstance(time_ms, (int, float))
                else 0.0,
            }


class OllamaTranslationService:
    def __init__(self, host: str = OLLAMA_HOST, model: str = MODEL_NAME):
        self.host = host
        self.model = model
        self.client = AsyncClient(host=host)

    def set_model(self, model_name: str):
        self.model = model_name

    def get_model(self) -> str:
        return self.model

    async def check_model_available(self) -> bool:
        try:
            models = await self.client.list()
            model_names = [m.model for m in models.models]
            return self.model in model_names
        except Exception:
            return False

    async def list_available_models(self) -> list[dict]:
        try:
            models = await self.client.list()
            return [
                {"name": m.model, "size": m.size if hasattr(m, "size") else 0,
                 "modified_at": m.modified_at if hasattr(m, "modified_at") else ""}
                for m in models.models
            ]
        except Exception:
            return []



    async def translate(self, text: str, source_lang: str, target_lang: str, max_retries: int = 3):
        """
        Traduce texto usando el modelo Qwen vía Ollama con reintentos.

        Returns:
            dict con el texto traducido y metadata
        """

        if source_lang == target_lang:
            return {
                "translated_text": text,
                "processing_time_ms": 0.0,
            }

        # Construcción de reglas para el System Prompt
        lang_names = {
            "English": "English",
            "Spanish": "Spanish",
            "Chinese": "Simplified Chinese",
        }

        # Detección robusta de Chino
        target_lower = target_lang.lower()
        if "chinese" in target_lower or "chino" in target_lower or "mandarin" in target_lower or target_lower in ["zh", "cn", "zh-cn"]:
            target_lang_prompt = "Simplified Chinese"
            is_chinese = True
        else:
            target_lang_prompt = lang_names.get(target_lang, target_lang)
            is_chinese = False

        source_prompt = lang_names.get(source_lang, source_lang)
        
        rules = [
            f"1. TRANSLATE strictly from {source_prompt} to {target_lang_prompt}.",
            "2. Do NOT simply copy the input text.",
            "3. Maintain original paragraph structure.",
            "4. Return ONLY the translated result.",
            "5. Do NOT output the rules or any explanation."
        ]

        if is_chinese:
            rules.append("6. Use Simplified Chinese characters (简体中文) ONLY.")

        rules_text = "\n".join(rules)

        system_content = (
            f"You are a professional translator from {source_prompt} to {target_lang_prompt}.\n"
            f"Your goal is to provide a natural and accurate translation.\n\n"
            f"STRICT RULES:\n{rules_text}\n\n"
            f"If the input is just numbers or punctuation, copy it exactly.\n"
            f"Do not include 'Here is the translation' or any headers."
        )

        start_time = time.time()
        await asyncio.sleep(0.1)
        print(f"DEBUG: Translating '{text[:50]}...' ({source_lang}->{target_lang})", flush=True)

        last_error = None
        for attempt in range(max_retries):
            try:
                response = await self.client.chat(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": text},
                    ],
                    options={
                        "temperature": 0.1,
                        "top_p": 0.9,
                        "num_predict": 1024,
                        "repeat_penalty": 1.1,
                    },
                )

                processing_time = (time.time() - start_time) * 1000
                translated_text = response.message.content.strip()
                print(f"DEBUG: Result: '{translated_text[:50]}...'", flush=True)

                prefixes_to_remove = [
                    "Translation:",
                    "Translated text:",
                    "Here is the translation:",
                    "Here's the translation:",
                    f"{target_lang}:",
                ]

                for prefix in prefixes_to_remove:
                    if translated_text.lower().startswith(prefix.lower()):
                        translated_text = translated_text[len(prefix):].strip()

                if (
                    translated_text.startswith(("\"", "'"))
                    and translated_text.endswith(("\"", "'"))
                ):
                    translated_text = translated_text[1:-1]

                return {
                    "translated_text": translated_text,
                    "processing_time_ms": round(processing_time, 2),
                }

            except ResponseError as e:
                error_msg = str(e.error).lower() if hasattr(e, "error") else str(e).lower()
                last_error = e
                # No reintentar si el modelo no existe
                if "not found" in error_msg or "404" in error_msg:
                    raise Exception(f"Error del modelo Ollama: {e.error}")
            except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError) as e:
                last_error = e
            except Exception as e:
                error_str = str(e).lower()
                last_error = e
                # No reintentar errores de modelo no encontrado
                if "not found" in error_str or "404" in error_str:
                    raise Exception(f"Error en la traducción: {str(e)}")

            if attempt < max_retries - 1:
                delay = 2 ** attempt
                logger.warning(
                    f"Reintento {attempt + 1}/{max_retries} traducción "
                    f"'{text[:40]}...': {last_error}"
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"Fallo definitivo tras {max_retries} intentos: {last_error}"
                )

        raise Exception(f"Error en la traducción (agotados {max_retries} reintentos): {str(last_error)}")


# Instancia global (usamos Ollama para máxima calidad en documentos)
# Optimizada para uso concurrente con OLLAMA_NUM_PARALLEL
translation_service = OllamaTranslationService()
