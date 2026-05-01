"""
Servicio avanzado para traducción de PDFs preservando formato exacto.
Usa PyMuPDF (fitz) para extracción y manipulación directa del PDF.
"""

import fitz  # PyMuPDF
import logging
import re
import math
from pathlib import Path
from typing import Callable, List, Tuple, Optional
import asyncio

logger = logging.getLogger(__name__)

# Máximo de reintentos por bloque fallido
MAX_RETRIES = 3

# --- Text cleaning helpers ---

def _clean_pdf_text(text: str) -> str:
    """Limpia artefactos comunes de extracción de PDF."""
    if not text:
        return text

    # Reemplazar soft hyphens (U+00AD) — invisibles en PDF pero rompen palabras
    text = text.replace("\u00ad", "")

    # Eliminar caracteres de control excepto newline y tab
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)

    # Normalizar espacios: multiple spaces → single space
    text = re.sub(r"[ \t]+", " ", text)

    # Corregir guiones de corte de palabra al final de línea
    # Ej: "desarro-\nllo" → "desarrollo"  (hyphen at end of line merged)
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)

    # Si el texto solo tiene puntuación/números, devolverlo limpio
    text = text.strip()

    return text


def _group_lines_into_paragraphs(
    blocks: List[Tuple[int, fitz.Rect, str, dict]]
) -> List[Tuple[int, fitz.Rect, str, dict]]:
    """
    Agrupa líneas en párrafos respetando columnas (posición X).
    Usa tracking de múltiples párrafos activos (uno por región horizontal)
    para manejar layouts multi-columna correctamente.
    """
    if len(blocks) < 2:
        return blocks

    # Ordenar por página, Y, luego X para procesar en orden de lectura
    blocks.sort(key=lambda b: (b[0], b[1].y0, b[1].x0))

    completed: List[Tuple[int, fitz.Rect, str, dict]] = []
    # Párrafos activos: [page, accumulated_rect, texts, style, last_line_rect]
    active: list = []

    for page_num, rect, text, style in blocks:
        # Buscar el párrafo activo con solapamiento horizontal más cercano
        best_idx = -1
        for idx, para in enumerate(active):
            p_page, p_rect, p_texts, p_style, p_last_rect = para
            if p_page != page_num:
                continue

            # Dos líneas son del mismo párrafo si:
            # a) Tienen bordes izquierdos alineados (< fsize * 2 de diferencia), O
            # b) Sus rangos X se solapan significativamente (> 20%)
            x0_diff = abs(p_last_rect.x0 - rect.x0)
            x_overlap = min(p_last_rect.x1, rect.x1) - max(p_last_rect.x0, rect.x0)
            max_w = max(abs(p_last_rect.x1 - p_last_rect.x0), abs(rect.x1 - rect.x0), 1)

            same_column = x0_diff < (fsize * 2) or (x_overlap / max_w >= 0.20)
            if not same_column:
                continue

            # Proximidad vertical
            fsize = max(style.get("size", 12), p_style.get("size", 12))
            gap = rect.y0 - p_rect.y1
            if gap < 0 or gap >= fsize * 1.25:
                continue

            best_idx = idx
            break

        if best_idx >= 0:
            # Merge con párrafo activo existente
            para = active[best_idx]
            para[1].y1 = max(para[1].y1, rect.y1)
            para[1].x0 = min(para[1].x0, rect.x0)
            para[1].x1 = max(para[1].x1, rect.x1)
            para[2].append(text)
            para[4] = fitz.Rect(rect)  # actualizar última línea
        else:
            # Cerrar párrafos activos que quedaron muy atrás (gap > 3x font_size)
            fsize = style.get("size", 12)
            still_active = []
            for para in active:
                p_page, p_rect, p_texts, p_style, p_last = para
                if p_page != page_num or (rect.y0 - p_rect.y1) <= fsize * 3:
                    still_active.append(para)
                else:
                    completed.append(
                        (p_page, fitz.Rect(p_rect), " ".join(p_texts), p_style)
                    )
            active = still_active

            # Iniciar nuevo párrafo activo
            active.append([page_num, fitz.Rect(rect), [text], style, fitz.Rect(rect)])

    # Cerrar todos los párrafos activos restantes
    for para in active:
        p_page, p_rect, p_texts, p_style, p_last = para
        completed.append((p_page, fitz.Rect(p_rect), " ".join(p_texts), p_style))

    # Reordenar resultado por página, Y, X
    completed.sort(key=lambda b: (b[0], b[1].y0, b[1].x0))
    return completed


# --- Font size estimation ---

def _estimate_font_size(
    text: str,
    rect_width: float,
    rect_height: float,
    base_size: float = 12.0,
    is_chinese_target: bool = False,
) -> float:
    """
    Estima el tamaño de fuente necesario para que el texto quepa en el rect.
    Factor de ancho: ~0.6 para latín, ~0.9 para CJK (caracteres más anchos).
    Retorna tamaño ajustado, mínimo 6pt.
    """
    if not text or rect_width <= 0 or rect_height <= 0:
        return base_size

    char_factor = 0.85 if is_chinese_target else 0.55
    max_chars_per_line = rect_width / (base_size * char_factor)
    num_lines_needed = math.ceil(len(text) / max(1, max_chars_per_line))
    max_lines_fit = rect_height / (base_size * 1.35)

    if num_lines_needed <= max_lines_fit:
        return base_size

    # Necesitamos reducir: calcular tamaño para que quepa
    target_height = rect_height / num_lines_needed
    estimated_size = target_height / 1.35
    return max(6.0, min(base_size, estimated_size))


class PDFTranslationService:
    """Servicio especializado para traducción de PDFs con preservación exacta de formato."""

    def __init__(self, translation_callback):
        """
        Args:
            translation_callback: Función async que traduce texto (text, source_lang, target_lang) -> str
        """
        self.translation_callback = translation_callback
        self.semaphore = asyncio.Semaphore(3)

    def extract_text_blocks(
        self, pdf_path: Path, group_paragraphs: bool = True
    ) -> List[Tuple[int, fitz.Rect, str, dict]]:
        """
        Extrae bloques de texto del PDF con posiciones y estilos.
        Si group_paragraphs=True, agrupa líneas cercanas en párrafos.
        """
        doc = fitz.open(pdf_path)
        raw_lines = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            blocks = page.get_text("dict")["blocks"]

            for block in blocks:
                if block["type"] != 0:
                    continue
                for line in block.get("lines", []):
                    line_text = ""
                    first_span = None

                    for span in line.get("spans", []):
                        if first_span is None:
                            first_span = span
                        line_text += span["text"]

                    line_text = _clean_pdf_text(line_text)
                    if line_text and first_span:
                        style_info = {
                            "font": first_span.get("font", ""),
                            "size": first_span.get("size", 12),
                            "color": first_span.get("color", 0),
                            "flags": first_span.get("flags", 0),
                        }
                        rect = fitz.Rect(line["bbox"])
                        raw_lines.append((page_num, rect, line_text, style_info))

        doc.close()

        if group_paragraphs:
            return _group_lines_into_paragraphs(raw_lines)

        return raw_lines

    async def _translate_single_block(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        retries: int = MAX_RETRIES,
    ) -> str:
        """Traduce un bloque de texto con reintentos y backoff exponencial."""
        last_error = None
        for attempt in range(retries):
            try:
                async with self.semaphore:
                    return await self.translation_callback(text, source_lang, target_lang)
            except Exception as e:
                last_error = e
                if attempt < retries - 1:
                    delay = 2 ** attempt
                    logger.warning(
                        f"Reintento {attempt + 1}/{retries} para bloque '{text[:40]}...': {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"Fallo definitivo tras {retries} intentos para bloque '{text[:40]}...': {e}"
                    )
        raise last_error  # type: ignore[misc]

    async def translate_text_blocks(
        self,
        text_blocks: List[Tuple[int, fitz.Rect, str, dict]],
        source_lang: str,
        target_lang: str,
        progress_callback: Callable[[int, int, str], None] = None,
    ) -> List[Tuple[int, fitz.Rect, str, dict]]:
        """
        Traduce bloques de texto preservando metadata.
        Maneja fallos individuales sin afectar al resto del batch.
        Respeta cancelación vía CancelledError.
        """
        total = len(text_blocks)
        translated_blocks: List[Tuple[int, fitz.Rect, str, dict]] = []
        batch_size = 5

        for i in range(0, total, batch_size):
            # Checkpoint de cancelación
            if asyncio.current_task() is not None and asyncio.current_task().cancelled():  # type: ignore[union-attr]
                raise asyncio.CancelledError()

            batch = text_blocks[i : i + batch_size]
            texts = [block[2] for block in batch]

            # Traducir en paralelo, capturando excepciones individuales
            tasks = [
                self._translate_single_block(text, source_lang, target_lang)
                for text in texts
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Reconstruir bloques — los que fallaron mantienen el texto original
            for j, (page_num, rect, original_text, style_info) in enumerate(batch):
                result = results[j]
                if isinstance(result, Exception):
                    logger.error(
                        f"Bloque no traducido (pág {page_num}): {str(result)[:100]}"
                    )
                    translated_blocks.append((page_num, rect, original_text, style_info))
                else:
                    translated_blocks.append((page_num, rect, result, style_info))

            if progress_callback:
                progress_callback(
                    min(i + batch_size, total),
                    total,
                    f"Traduciendo bloque {min(i + batch_size, total)} de {total}...",
                )

            # Ceder control para permitir cancelación entre batches
            await asyncio.sleep(0)

        return translated_blocks

    def create_translated_pdf(
        self,
        original_pdf_path: Path,
        translated_blocks: List[Tuple[int, fitz.Rect, str, dict]],
        output_path: Path,
        target_lang: str = "Spanish",
    ) -> Path:
        """
        Crea un nuevo PDF con los textos traducidos manteniendo el layout original.
        Usa estimación inteligente de tamaño de fuente para minimizar re-escalados.
        """
        doc = fitz.open(original_pdf_path)

        target_lower = target_lang.lower()
        is_chinese = (
            "chinese" in target_lower
            or "chino" in target_lower
            or target_lower in ["zh", "cn", "zh-cn"]
        )

        if is_chinese:
            font_path = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
            font_name = "notocjk"
        else:
            font_path = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
            font_name = "liberation"

        has_font = Path(font_path).exists()

        # Organizar bloques por página
        blocks_by_page: dict[int, List[Tuple[fitz.Rect, str, dict]]] = {}
        for page_num, rect, text, style in translated_blocks:
            blocks_by_page.setdefault(page_num, []).append((rect, text, style))

        for page_num, blocks in blocks_by_page.items():
            page = doc[page_num]

            # Fase 1: Redactar (borrar texto original con fondo transparente)
            for rect, _text, _style in blocks:
                page.add_redact_annot(rect, fill=None)

            page.apply_redactions()

            # Fase 2: Insertar textos traducidos
            for rect, text, style in blocks:
                font_size = style.get("size", 12)

                # Escalamiento inteligente
                adjusted_size = _estimate_font_size(
                    text,
                    rect.width,
                    rect.height,
                    font_size,
                    is_chinese_target=is_chinese,
                )

                kwargs: dict = {
                    "fontsize": adjusted_size,
                    "color": (0, 0, 0),
                    "align": fitz.TEXT_ALIGN_LEFT,
                }

                if has_font:
                    kwargs["fontfile"] = font_path
                    kwargs["fontname"] = font_name
                else:
                    kwargs["fontname"] = "helv"

                try:
                    rc = page.insert_textbox(rect, text, **kwargs)

                    # Si falla con tamaño estimado, intentar escalas progresivas
                    if rc < 0:
                        for scale in [0.85, 0.72, 0.60]:
                            kwargs["fontsize"] = font_size * scale
                            rc = page.insert_textbox(rect, text, **kwargs)
                            if rc >= 0:
                                break

                    if rc < 0:
                        logger.warning(
                            f"Texto truncado pág {page_num}: '{text[:40]}...' "
                            f"(rect={rect.width:.0f}x{rect.height:.0f}, "
                            f"base_font={font_size}, adjusted={adjusted_size:.1f})"
                        )

                except Exception as e:
                    logger.warning(f"Error insertando texto pág {page_num}: {e}")
                    try:
                        page.insert_textbox(
                            rect, text[:50], fontsize=8, fontname="helv", color=(0, 0, 0)
                        )
                    except Exception:
                        pass

        doc.save(output_path, garbage=4, deflate=True, clean=True)
        doc.close()

        return output_path

    async def translate_pdf(
        self,
        input_path: Path,
        output_path: Path,
        source_lang: str,
        target_lang: str,
        progress_callback: Callable[[int, int, str], None] = None,
    ) -> Path:
        """Método principal: Traduce un PDF preservando formato exacto."""
        try:
            if progress_callback:
                progress_callback(0, 100, "Extrayendo texto del PDF...")

            text_blocks = self.extract_text_blocks(input_path, group_paragraphs=True)

            if not text_blocks:
                logger.warning("No se encontró texto para traducir en el PDF")
                import shutil

                shutil.copy(input_path, output_path)
                return output_path

            if progress_callback:
                progress_callback(
                    5, 100, f"Agrupados {len(text_blocks)} párrafos para traducir"
                )

            translated_blocks = await self.translate_text_blocks(
                text_blocks,
                source_lang,
                target_lang,
                lambda curr, total, msg: progress_callback(
                    5 + int((curr / total) * 85), 100, msg
                )
                if progress_callback
                else None,
            )

            if progress_callback:
                progress_callback(90, 100, "Generando PDF final...")

            result = self.create_translated_pdf(
                input_path, translated_blocks, output_path, target_lang
            )

            if progress_callback:
                progress_callback(100, 100, "Traducción completada")

            return result

        except asyncio.CancelledError:
            logger.info("Traducción de PDF cancelada por el usuario")
            raise
        except Exception as e:
            logger.error(f"Error en traducción de PDF: {e}")
            raise
