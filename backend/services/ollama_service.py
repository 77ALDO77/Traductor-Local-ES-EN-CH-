"""
Servicio de integración con Ollama para traducciones.
"""

from ollama import AsyncClient, ResponseError
import time


class OllamaTranslationService:
    def __init__(self, host: str = "http://localhost:11434", model: str = "qwen2.5:7b"):
        self.host = host
        self.model = model
        self.client = AsyncClient(host=host)
    
    def _build_translation_prompt(self, text: str, source_lang: str, target_lang: str) -> str:
        """Construye el prompt optimizado para traducción."""
        
        # Mapeo de nombres de idiomas para el prompt
        lang_names = {
            "English": "English",
            "Spanish": "Spanish", 
            "Chinese": "Simplified Chinese"
        }
        
        source = lang_names.get(source_lang, source_lang)
        target = lang_names.get(target_lang, target_lang)
        
        # Reglas base
        rules = [
            "1. Provide ONLY the translation text.",
            "2. Do NOT add notes, explanations, or quotes.",
            "3. Maintain the original tone and formatting."
        ]

        # Regla condicional: Solo mencionar chino si es el destino
        if target_lang == "Chinese":
            rules.append("4. Use Simplified Chinese characters (简体中文).")

        rules_text = "\n".join(rules)

        return f"""System: You are a professional translator engine.
Task: Translate the content from {source} to {target}.

Rules:
{rules_text}

Content to translate:
{text}

Translation:"""
    
    async def translate(self, text: str, source_language: str, target_language: str) -> dict:
        """
        Traduce texto usando el modelo Qwen.
        
        Args:
            text: Texto a traducir
            source_language: Idioma de origen
            target_language: Idioma de destino
            
        Returns:
            dict con el texto traducido y metadata
        """
        
        if source_language == target_language:
            return {
                "translated_text": text,
                "processing_time_ms": 0
            }
        
        prompt = self._build_translation_prompt(text, source_language, target_language)
        
        start_time = time.time()
        
        try:
            response = await self.client.chat(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": f"You are a translation engine. You ONLY output {target_language} text. Never explain, never add notes."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                options={
                    "temperature": 0.3,
                    "top_p": 0.9,
                    "num_predict": 2048
                }
            )
            
            end_time = time.time()
            processing_time = (end_time - start_time) * 1000
            
            translated_text = response.message.content.strip()
            
            # Limpiar posibles prefijos que el modelo pueda agregar
            prefixes_to_remove = [
                "Translation:", 
                "Translated text:", 
                "Here is the translation:",
                "Here's the translation:",
                f"{target_language}:",
            ]
            for prefix in prefixes_to_remove:
                if translated_text.lower().startswith(prefix.lower()):
                    translated_text = translated_text[len(prefix):].strip()
            
            # Remover comillas envolventes si existen
            if (translated_text.startswith('"') and translated_text.endswith('"')) or \
               (translated_text.startswith("'") and translated_text.endswith("'")):
                translated_text = translated_text[1:-1]
            
            return {
                "translated_text": translated_text,
                "processing_time_ms": round(processing_time, 2)
            }
            
        except ResponseError as e:
            raise Exception(f"Error del modelo Ollama: {e.error}")
        except Exception as e:
            raise Exception(f"Error en la traducción: {str(e)}")


# Instancia global del servicio
translation_service = OllamaTranslationService()
