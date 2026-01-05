"""
Servicio avanzado para traducción de PDFs preservando formato exacto.
Usa PyMuPDF (fitz) para extracción y manipulación directa del PDF.
"""

import fitz  # PyMuPDF
import logging
from pathlib import Path
from typing import Callable, List, Tuple
import asyncio

logger = logging.getLogger(__name__)


class PDFTranslationService:
    """Servicio especializado para traducción de PDFs con preservación exacta de formato."""
    
    def __init__(self, translation_callback):
        """
        Args:
            translation_callback: Función async que traduce texto (text, source_lang, target_lang) -> str
        """
        self.translation_callback = translation_callback
        self.semaphore = asyncio.Semaphore(3)
    
    def extract_text_blocks(self, pdf_path: Path) -> List[Tuple[int, fitz.Rect, str, dict]]:
        """
        Extrae bloques de texto del PDF con sus posiciones y estilos exactos.
        
        Returns:
            Lista de (page_num, rect, text, style_info)
        """
        doc = fitz.open(pdf_path)
        text_blocks = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Extraer bloques de texto con información de posición
            blocks = page.get_text("dict")["blocks"]
            
            for block in blocks:
                if block["type"] == 0:  # Bloque de texto
                    for line in block.get("lines", []):
                        # Concatenar spans en la línea
                        line_text = ""
                        first_span = None
                        
                        for span in line.get("spans", []):
                            if first_span is None:
                                first_span = span
                            line_text += span["text"]
                        
                        if line_text.strip() and first_span:
                            # Guardar información de estilo del primer span
                            style_info = {
                                "font": first_span.get("font", ""),
                                "size": first_span.get("size", 12),
                                "color": first_span.get("color", 0),
                                "flags": first_span.get("flags", 0),
                            }
                            
                            rect = fitz.Rect(line["bbox"])
                            text_blocks.append((page_num, rect, line_text.strip(), style_info))
        
        doc.close()
        return text_blocks
    
    async def translate_text_blocks(
        self, 
        text_blocks: List[Tuple[int, fitz.Rect, str, dict]],
        source_lang: str,
        target_lang: str,
        progress_callback: Callable[[int, int, str], None] = None
    ) -> List[Tuple[int, fitz.Rect, str, dict]]:
        """
        Traduce los bloques de texto preservando metadata.
        
        Returns:
            Lista de (page_num, rect, translated_text, style_info)
        """
        total = len(text_blocks)
        translated_blocks = []
        
        # Procesar en batches pequeños
        batch_size = 5
        
        for i in range(0, total, batch_size):
            batch = text_blocks[i:i + batch_size]
            
            # Extraer solo los textos
            texts = [block[2] for block in batch]
            
            # Traducir en paralelo
            tasks = [
                self.translation_callback(text, source_lang, target_lang)
                for text in texts
            ]
            translated_texts = await asyncio.gather(*tasks)
            
            # Reconstruir bloques con traducciones
            for j, (page_num, rect, _, style_info) in enumerate(batch):
                translated_blocks.append((
                    page_num,
                    rect,
                    translated_texts[j],
                    style_info
                ))
            
            if progress_callback:
                progress_callback(
                    min(i + batch_size, total),
                    total,
                    f"Traduciendo bloque {min(i + batch_size, total)} de {total}..."
                )
        
        return translated_blocks
    
    def create_translated_pdf(
        self,
        original_pdf_path: Path,
        translated_blocks: List[Tuple[int, fitz.Rect, str, dict]],
        output_path: Path
    ) -> Path:
        """
        Crea un nuevo PDF con los textos traducidos manteniendo el layout original.
        
        Estrategia:
        1. Copia el PDF original como base (mantiene imágenes, gráficos, formato)
        2. Redacta (blanquea) las áreas de texto original
        3. Inserta el texto traducido en las mismas posiciones con el mismo estilo
        """
        # Abrir el PDF original
        doc = fitz.open(original_pdf_path)
        
        # Organizar bloques por página
        blocks_by_page = {}
        for page_num, rect, text, style in translated_blocks:
            if page_num not in blocks_by_page:
                blocks_by_page[page_num] = []
            blocks_by_page[page_num].append((rect, text, style))
        
        # Procesar cada página
        for page_num, blocks in blocks_by_page.items():
            page = doc[page_num]
            
            for rect, text, style in blocks:
                # ESTRATEGIA MEJORADA: Redacción transparente
                # En lugar de pintar un recuadro blanco (que tapa fondos azules de tablas),
                # simplemente eliminamos el texto y dejamos que se vea el fondo original.
                page.add_redact_annot(rect, fill=None)  # fill=None = transparente
            
            # Aplicar redacciones
            page.apply_redactions()
            
            # Insertar textos traducidos
            # Definir fuente segura (Liberation Sans)
            font_path = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
            has_font = Path(font_path).exists()
            
            # Insertar textos traducidos
            for rect, text, style in blocks:
                # Calcular tamaño de fuente
                font_size = style["size"]
                
                # Intentar insertar
                try:
                    # Configuración base
                    kwargs = {
                        "fontsize": font_size,
                        "color": (0, 0, 0),
                        "align": fitz.TEXT_ALIGN_LEFT
                    }
                    
                    if has_font:
                        kwargs["fontfile"] = font_path
                        kwargs["fontname"] = "Liberation"
                    else:
                        kwargs["fontname"] = "helv"
                    
                    # 1. Intentar con tamaño original
                    rc = page.insert_textbox(rect, text, **kwargs)
                    
                    # 2. Si no cabe, reducir tamaño progresivamente
                    if rc < 0:
                        for scale in [0.9, 0.8, 0.7, 0.6, 0.5]:
                            kwargs["fontsize"] = font_size * scale
                            rc = page.insert_textbox(rect, text, **kwargs)
                            if rc >= 0:
                                break
                    
                    # 3. Si aún no cabe, loggear warning (pero ya hicimos lo posible)
                    if rc < 0:
                        logger.warning(f"Texto truncado en página {page_num}: {text[:30]}...")
                
                except Exception as e:
                    logger.warning(f"Error insertando texto en página {page_num}: {e}")
                    # Fallback de emergencia
                    try:
                        page.insert_textbox(
                            rect,
                            text[:50],
                            fontsize=8,
                            fontname="helv",
                            color=(0,0,0)
                        )
                    except:
                        pass
        
        # Guardar el PDF traducido
        doc.save(output_path, garbage=4, deflate=True, clean=True)
        doc.close()
        
        return output_path
    
    async def translate_pdf(
        self,
        input_path: Path,
        output_path: Path,
        source_lang: str,
        target_lang: str,
        progress_callback: Callable[[int, int, str], None] = None
    ) -> Path:
        """
        Método principal: Traduce un PDF preservando formato exacto.
        
        Args:
            input_path: Ruta del PDF original
            output_path: Ruta del PDF traducido
            source_lang: Idioma origen
            target_lang: Idioma destino
            progress_callback: Callback de progreso
            
        Returns:
            Path del PDF traducido
        """
        try:
            # Paso 1: Extraer bloques de texto
            if progress_callback:
                progress_callback(0, 100, "Extrayendo texto del PDF...")
            
            text_blocks = self.extract_text_blocks(input_path)
            
            if not text_blocks:
                logger.warning("No se encontró texto para traducir en el PDF")
                # Copiar el PDF original
                import shutil
                shutil.copy(input_path, output_path)
                return output_path
            
            # Paso 2: Traducir bloques
            if progress_callback:
                progress_callback(10, 100, "Traduciendo contenido...")
            
            translated_blocks = await self.translate_text_blocks(
                text_blocks,
                source_lang,
                target_lang,
                lambda curr, total, msg: progress_callback(
                    10 + int((curr / total) * 80),
                    100,
                    msg
                ) if progress_callback else None
            )
            
            # Paso 3: Crear PDF traducido
            if progress_callback:
                progress_callback(90, 100, "Generando PDF final...")
            
            result = self.create_translated_pdf(
                input_path,
                translated_blocks,
                output_path
            )
            
            if progress_callback:
                progress_callback(100, 100, "Traducción completada")
            
            return result
            
        except Exception as e:
            logger.error(f"Error en traducción de PDF: {e}")
            raise
