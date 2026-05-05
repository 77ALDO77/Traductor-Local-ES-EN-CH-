"""
Servicio de integración con vLLM para traducciones (OpenAI-compatible API).
"""
import os
import time
import asyncio
import logging
from openai import AsyncOpenAI, APIError, APIStatusError
import httpx

logger = logging.getLogger(__name__)

LLM_HOST = os.getenv("LLM_HOST", "http://localhost:8000")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-1.5B-Instruct")


class LLMTranslationService:
    def __init__(self, host: str = LLM_HOST, model: str = MODEL_NAME):
        self.host = host
        self.model = model
        self.client = AsyncOpenAI(base_url=f"{host}/v1", api_key="not-needed")

    def set_model(self, model_name: str):
        self.model = model_name

    def get_model(self) -> str:
        return self.model

    async def check_model_available(self) -> bool:
        try:
            models = await self.client.models.list()
            model_ids = [m.id for m in models.data]
            return self.model in model_ids
        except Exception:
            return False

    async def list_available_models(self) -> list[dict]:
        try:
            models = await self.client.models.list()
            return [
                {
                    "name": m.id,
                    "created": m.created,
                    "owned_by": m.owned_by,
                }
                for m in models.data
            ]
        except Exception:
            return []

    async def translate(self, text: str, source_lang: str, target_lang: str, max_retries: int = 3):
        """
        Traduce texto usando el modelo LLM vía vLLM con reintentos.

        Returns:
            dict con el texto traducido y metadata
        """

        if source_lang == target_lang:
            return {
                "translated_text": text,
                "processing_time_ms": 0.0,
            }

        lang_names = {
            "English": "English",
            "Spanish": "Spanish",
            "Chinese": "Simplified Chinese",
        }

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
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": text},
                    ],
                    temperature=0.1,
                    top_p=0.9,
                    max_tokens=1024,
                    frequency_penalty=0.1,
                )

                processing_time = (time.time() - start_time) * 1000
                translated_text = response.choices[0].message.content
                if translated_text is None:
                    translated_text = ""
                translated_text = translated_text.strip()
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

            except APIStatusError as e:
                error_msg = str(e.body).lower() if e.body else str(e).lower()
                last_error = e
                if "not found" in error_msg or "404" in str(e.status_code):
                    raise Exception(f"Error del modelo vLLM: {e.message}")
            except APIError as e:
                last_error = e
            except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError) as e:
                last_error = e
            except Exception as e:
                error_str = str(e).lower()
                last_error = e
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


# Instancia global
translation_service = LLMTranslationService()
