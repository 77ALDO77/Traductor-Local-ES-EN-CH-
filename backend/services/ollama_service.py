"""
Servicio de integración con Ollama para traducciones.
"""

import os
import time
import httpx
from ollama import AsyncClient, ResponseError


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

    def _build_translation_prompt(
        self, text: str, source_lang: str, target_lang: str
    ) -> str:
        """Construye el prompt optimizado para traducción."""

        lang_names = {
            "English": "English",
            "Spanish": "Spanish",
            "Chinese": "Simplified Chinese",
        }

        source = lang_names.get(source_lang, source_lang)
        target = lang_names.get(target_lang, target_lang)

        rules = [
            f"1. TRANSLATE the text strictly from {source} to {target}.",
            "2. Do NOT simply copy the input text.",
            "3. Maintain original paragraph structure and line breaks.",
            "4. Return ONLY the translated result.",
        ]

        if target_lang == "Chinese":
            rules.append("5. Use Simplified Chinese characters (简体中文).")

        rules_text = "\n".join(rules)

        return f"""Task: Translate the following content.

Rules:
{rules_text}

Content:
{text}
"""

    async def translate(self, text: str, source_lang: str, target_lang: str):
        """
        Traduce texto usando el modelo Qwen vía Ollama.

        Returns:
            dict con el texto traducido y metadata
        """

        if source_lang == target_lang:
            return {
                "translated_text": text,
                "processing_time_ms": 0.0,
            }

        prompt = self._build_translation_prompt(text, source_lang, target_lang)
        start_time = time.time()

        try:
            response = await self.client.chat(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            f"You are a translator from {source_lang} to {target_lang}. "
                            f"You must translate the input. Do not repeat the source text."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                options={
                    "temperature": 0.3,
                    "top_p": 0.9,
                    "num_predict": 1024,
                    "repeat_penalty": 1.1,
                },
            )

            processing_time = (time.time() - start_time) * 1000
            translated_text = response.message.content.strip()

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
            raise Exception(f"Error del modelo Ollama: {e.error}")
        except Exception as e:
            raise Exception(f"Error en la traducción: {str(e)}")


# Instancia global (por defecto usa el motor Ollama para mayor calidad)
translation_service = OllamaTranslationService()
