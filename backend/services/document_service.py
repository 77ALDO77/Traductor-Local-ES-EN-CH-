"""
Servicio para procesamiento de documentos con preservación de formato.
Estrategia: Traducción IN-PLACE manteniendo estilos, imágenes y layout.
Ahora con conversión DOCX -> PDF al final si el origen fue PDF.
"""

import os
import asyncio
from pathlib import Path
from typing import Callable
import subprocess

import logging

from docx import Document
from docx.text.paragraph import Paragraph
from openpyxl import load_workbook
import re
from pdf2docx import Converter
from docx2pdf import convert as docx_to_pdf_convert

from backend.services.ollama_service import translation_service
from backend.services.pdf_translation_service import PDFTranslationService


logger = logging.getLogger(__name__)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Configuración de batching
BATCH_SIZE = 5
MIN_TEXT_LENGTH = 2
MAX_CONCURRENT = 4  # Ajustado a OLLAMA_NUM_PARALLEL para evitar cuellos de botella


class DocumentService:
    """Servicio para traducción de documentos preservando formato."""
    
    def __init__(self):
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        
        # Callback para el servicio de PDF
        async def pdf_translate_callback(text: str, source_lang: str, target_lang: str) -> str:
            result = await translation_service.translate(
                text=text,
                source_lang=source_lang,
                target_lang=target_lang
            )
            return result["translated_text"]
        
        self.pdf_service = PDFTranslationService(pdf_translate_callback)
    
    @staticmethod
    def get_file_type(filename: str) -> str:
        """Obtiene el tipo de archivo por extensión."""
        ext = filename.lower().split('.')[-1]
        if ext == 'pdf':
            return 'pdf'
        elif ext in ['docx', 'doc']:
            return 'docx'
        elif ext in ['xlsx', 'xls']:
            return 'xlsx'
        else:
            raise ValueError(f"Tipo de archivo no soportado: {ext}")
    
    def convert_pdf_to_docx(self, pdf_path: Path, output_path: Path) -> Path:
        """
        Convierte PDF a DOCX preservando layout visual.
        Usa pdf2docx que mantiene imágenes, tablas y formato.
        """
        try:
            cv = Converter(str(pdf_path))
            cv.convert(str(output_path), start=0, end=None)
            cv.close()
            return output_path
        except Exception as e:
            logger.error(f"Error convirtiendo PDF a DOCX: {e}")
            raise
    
    def convert_docx_to_pdf(self, docx_path: Path, output_path: Path) -> Path:
        """
        Convierte DOCX a PDF usando LibreOffice (compatible con Linux).
        Preserva el layout, imágenes y formato del documento.
        """
        try:
            # Usar LibreOffice headless para conversión en Linux
            cmd = [
                "soffice",
                "--headless",
                "--convert-to",
                "pdf",
                str(docx_path),
                "--outdir",
                str(output_path.parent)
            ]
            
            subprocess.run(
                cmd, 
                check=True, 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.PIPE
            )
            
            # LibreOffice guarda con el mismo nombre base pero extensión .pdf
            # Si docx_path es 'archivo.temp.docx', genera 'archivo.temp.pdf'
            expected_output = docx_path.with_suffix('.pdf')
            
            if expected_output.exists():
                if expected_output != output_path:
                    if output_path.exists():
                        os.remove(output_path)
                    os.rename(expected_output, output_path)
            else:
                # Intento de fallback o error
                raise FileNotFoundError(f"LibreOffice no generó el archivo esperado: {expected_output}")
                
            return output_path
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if e.stderr else "Error desconocido de LibreOffice"
            logger.error(f"Error de LibreOffice: {error_msg}")
            raise RuntimeError(f"Fallo en conversión PDF: {error_msg}")
        except Exception as e:
            logger.error(f"Error convirtiendo DOCX a PDF: {e}")
            raise
    
    async def _translate_with_semaphore(
        self, 
        text: str, 
        source_lang: str, 
        target_lang: str
    ) -> str:
        """Traduce texto con control de concurrencia."""
        async with self.semaphore:
            result = await translation_service.translate(
                text=text,
                source_lang=source_lang,
                target_lang=target_lang
            )
            return result["translated_text"]
    
    async def _translate_batch(
        self,
        texts: list[str],
        source_lang: str,
        target_lang: str
    ) -> list[str]:
        """Traduce un batch de textos en paralelo."""
        tasks = [
            self._translate_with_semaphore(text, source_lang, target_lang)
            for text in texts
        ]
        return await asyncio.gather(*tasks)
    
    def _should_translate(self, text: str) -> bool:
        """Determina si un texto debe ser traducido."""
        if not text:
            return False
        stripped = text.strip()
        if len(stripped) < MIN_TEXT_LENGTH:
            return False
        if stripped.replace(' ', '').replace('.', '').replace(',', '').isdigit():
            return False
        
        # No traducir líneas que son principalmente puntos/guiones (TOC leaders)
        # Ej: "Introduction ......................... 5"
        non_leader_chars = stripped.replace('.', '').replace('-', '').replace('_', '').replace(' ', '')
        if len(non_leader_chars) < len(stripped) * 0.3:  # Más del 70% son leaders
            return False
            
        return True
    
    def _replace_paragraph_text_preserve_format(
        self, 
        paragraph: Paragraph, 
        new_text: str
    ) -> None:
        """
        Reemplaza el texto de un párrafo preservando el formato de los runs.
        Estrategia: Poner todo el texto nuevo en el primer run, vaciar los demás.
        """
        if not paragraph.runs:
            paragraph.text = new_text
            return
        
        first_run = paragraph.runs[0]
        first_run.text = new_text
        
        # FIX: Evitar Mojibake (texto griego/símbolos) causado por fuentes "Symbol" del PDF.
        # pdf2docx a veces asigna la fuente Symbol al texto extraído, lo que hace que 
        # el texto ASCII (traducido o no) se vea como caracteres griegos.
        if first_run.font.name:
            font_name_lower = first_run.font.name.lower()
            if 'symbol' in font_name_lower or 'dingbats' in font_name_lower or 'wingdings' in font_name_lower:
                first_run.font.name = 'Arial'
        
        for run in paragraph.runs[1:]:
            run.text = ""
    



    def _extract_text_structure(self, text: str) -> tuple[str, str, str]:
        """
        Separa el texto en (prefijo, contenido, sufijo) para preservar formato.
        - Prefijo: Viñetas, numeración, espacios iniciales.
        - Contenido: El texto real a traducir.
        - Sufijo: Líneas de puntos de índice, números de página, espacios finales.
        """
        if not text:
            return "", "", ""
            
        # 1. Detectar TOC leaders (ej: "...... 12")
        # Regex: secuencia de puntos seguida opcionalmente de espacio y números al final
        toc_pattern = r'(\s*[\.\-_]{3,}\s*\d+|\s*[\.\-_]{3,})\s*$'
        suffix = ""
        content = text
        
        toc_match = re.search(toc_pattern, text)
        if toc_match:
            suffix = toc_match.group(0)
            content = text[:toc_match.start()]
            
        # 2. Detectar Prefijos (Viñetas, Números, Identación)
        # Regex: 
        # - Espacios iniciales
        # - Viñetas comunes (•, -, *, etc)
        # - Numeración (1., 1.1, A., a))
        prefix = ""
        
        # Patrones comunes de inicio de lista
        list_pattern = r'^(\s*(?:[•\-\*·◦‣]|\d+[\.\)]|[a-zA-Z][\.\)])\s+)'
        # Patrón de solo espacios
        space_pattern = r'^(\s+)'
        
        match = re.match(list_pattern, content)
        if match:
            prefix = match.group(1)
            content = content[match.end():]
        else:
            match_space = re.match(space_pattern, content)
            if match_space:
                prefix = match_space.group(1)
                content = content[match_space.end():]
                
        return prefix, content, suffix

    def _reassemble_text(self, prefix: str, translated_content: str, suffix: str, original_content_len: int = 0) -> str:
        """
        Reconstruye el texto preservando la estructura original.
        Ajusta la longitud de los 'leaders' (puntos) en el sufijo para evitar saltos de línea en índices.
        """
        # Limpieza básica
        clean_content = translated_content.strip()
        
        # Lógica de ajuste de puntos para TOC
        # Si el sufijo parece ser un leader (puntos seguidos de numero o nada)
        # Regex: espacios opcionales, 3+ puntos/guiones, espacios opcionales, digito final opcional
        if original_content_len > 0 and re.match(r'^\s*[\._-]{3,}', suffix):
            # Calcular diferencia de longitud
            diff = len(clean_content) - original_content_len
            
            # Solo ajustamos si hubo cambio significativo
            if diff != 0:
                # Separar los puntos del resto del sufijo (ej: numeros de pagina)
                # Grupo 1: Espacio inicial, Grupo 2: Puntos, Grupo 3: Resto
                match_dots = re.match(r'^(\s*)([\._-]+)(\s*.*)$', suffix, re.DOTALL)
                if match_dots:
                    pre_space = match_dots.group(1)
                    dots = match_dots.group(2)
                    rest = match_dots.group(3)
                    
                    current_dots_count = len(dots)
                    char = dots[0] # El caracter usado (punto, guion, etc)
                    
                    # Heurística: Si texto crece, quitar puntos. Si decrece, poner puntos.
                    # Factor 1.2 compensa ancho variable de caracteres
                    dots_adjustment = int(diff * 1.2)
                    
                    new_count = current_dots_count - dots_adjustment
                    
                    # Seguridad: Mínimo 3 puntos y Máximo 200 (evitar loops raros)
                    new_count = max(3, min(new_count, 200))
                    
                    new_dots = char * new_count
                    suffix = f"{pre_space}{new_dots}{rest}"

        return f"{prefix}{clean_content}{suffix}"

    # ... existing methods ...

    async def translate_docx_preserving_format(
        self,
        input_path: Path,
        output_path: Path,
        source_lang: str,
        target_lang: str,
        progress_callback: Callable[[int, int, str], None] = None
    ) -> None:
        """
        Traduce un documento DOCX preservando formato, imágenes y estilos.
        Itera sobre párrafos y tablas, traduciendo in-place.
        """
        doc = Document(input_path)
        
        # Recopilar todos los elementos traducibles
        translatable_items = []
        original_structures = [] # Guardar metadatos de estructura
        
        def process_paragraph(para):
            if self._should_translate(para.text):
                prefix, content, suffix = self._extract_text_structure(para.text)
                if self._should_translate(content): # Verificar de nuevo solo el contenido
                    translatable_items.append(("paragraph", para))
                    original_structures.append((prefix, content, suffix))

        # Párrafos del cuerpo principal
        for para in doc.paragraphs:
            process_paragraph(para)
        
        # Tablas del cuerpo principal
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for para in cell.paragraphs:
                        process_paragraph(para)
        
        # Headers y Footers
        for section in doc.sections:
            if section.header:
                for para in section.header.paragraphs:
                    process_paragraph(para)
            if section.footer:
                for para in section.footer.paragraphs:
                    process_paragraph(para)
        
        total_items = len(translatable_items)
        
        if total_items == 0:
            doc.save(output_path)
            return
        
        # Procesar en batches
        for batch_start in range(0, total_items, BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, total_items)
            
            # Obtener el chunk actual de items y sus estructuras
            batch_items = translatable_items[batch_start:batch_end]
            batch_structures = original_structures[batch_start:batch_end]
            
            # Solo mandamos traducir el CONTENIDO limpio (sin bullets ni números)
            texts_to_translate = [struct[1] for struct in batch_structures]
            
            translated_contents = await self._translate_batch(
                texts_to_translate, source_lang, target_lang
            )
            
            for i, (item_type, item) in enumerate(batch_items):
                prefix, _, suffix = batch_structures[i]
                translated_content = translated_contents[i]
                
                # Reensamblar con la estructura original
                # Pasamos la longitud original para el ajuste inteligente de puntos (TOC fix)
                original_content = batch_structures[i][1]
                final_text = self._reassemble_text(
                    prefix, 
                    translated_content, 
                    suffix, 
                    original_content_len=len(original_content)
                )
                
                if item_type == "paragraph":
                    self._replace_paragraph_text_preserve_format(
                        item, final_text
                    )
            
            if progress_callback:
                progress_callback(
                    batch_end,
                    total_items,
                    f"Traduciendo elemento {batch_end} de {total_items}..."
                )
        
        doc.save(output_path)
    
    async def translate_xlsx_preserving_format(
        self,
        input_path: Path,
        output_path: Path,
        source_lang: str,
        target_lang: str,
        progress_callback: Callable[[int, int, str], None] = None
    ) -> None:
        """
        Traduce un archivo XLSX preservando formato, estilos y fórmulas.
        """
        wb = load_workbook(input_path)
        
        translatable_cells = []
        
        for sheet_name in wb.sheetnames:
            sheet = wb[sheet_name]
            for row in sheet.iter_rows():
                for cell in row:
                    if cell.value and isinstance(cell.value, str):
                        if self._should_translate(cell.value):
                            translatable_cells.append(cell)
        
        total_cells = len(translatable_cells)
        
        if total_cells == 0:
            wb.save(output_path)
            wb.close()
            return
        
        for batch_start in range(0, total_cells, BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, total_cells)
            batch_cells = translatable_cells[batch_start:batch_end]
            
            texts_to_translate = [cell.value for cell in batch_cells]
            translated_texts = await self._translate_batch(
                texts_to_translate, source_lang, target_lang
            )
            
            for i, cell in enumerate(batch_cells):
                cell.value = translated_texts[i]
            
            if progress_callback:
                progress_callback(
                    batch_end,
                    total_cells,
                    f"Traduciendo celda {batch_end} de {total_cells}..."
                )
        
        wb.save(output_path)
        wb.close()
    
    async def translate_document_preserving_format(
        self,
        input_path: Path,
        output_path: Path,
        source_lang: str,
        target_lang: str,
        progress_callback: Callable[[int, int, str], None] = None
    ) -> tuple[Path, str]:
        """
        Método principal: Traduce cualquier documento preservando formato.
        
        - PDF: Convierte a DOCX, traduce, convierte de vuelta a PDF
        - DOCX: Traduce in-place preservando formato
        - XLSX: Traduce celdas preservando estilos
        
        Args:
            input_path: Ruta del archivo original
            output_path: Ruta base del archivo traducido (sin extensión)
            source_lang: Idioma origen
            target_lang: Idioma destino
            progress_callback: Función callback(current, total, message)
            
        Returns:
            Tupla (output_path, original_format) del archivo traducido
        """
        file_type = self.get_file_type(input_path.name)
        
        if file_type == "pdf":
            # ENFOQUE DEFINITIVO: Traducción directa sobre PDF con fuente Liberation Sans
            # Esto preserva el layout exacto, imágenes y número de páginas.
            final_output_pdf = output_path.with_suffix('.pdf')
            
            await self.pdf_service.translate_pdf(
                input_path,
                final_output_pdf,
                source_lang,
                target_lang,
                progress_callback
            )
            
            return final_output_pdf, "pdf"
            
        elif file_type == "docx":
            final_output_docx = output_path.with_suffix('.docx')
            
            await self.translate_docx_preserving_format(
                input_path,
                final_output_docx,
                source_lang,
                target_lang,
                progress_callback
            )
            
            return final_output_docx, "docx"
            
        elif file_type == "xlsx":
            final_output_xlsx = output_path.with_suffix('.xlsx')
            
            await self.translate_xlsx_preserving_format(
                input_path,
                final_output_xlsx,
                source_lang,
                target_lang,
                progress_callback
            )
            
            return final_output_xlsx, "xlsx"
        
        raise ValueError(f"Tipo de archivo no soportado: {file_type}")
    
    def get_document_stats(self, file_path: Path) -> dict:
        """Obtiene estadísticas del documento para preview."""
        file_type = self.get_file_type(file_path.name)
        stats = {
            "file_type": file_type,
            "translatable_items": 0,
            "preview_text": ""
        }
        
        try:
            if file_type == "pdf":
                # Usar el mismo servicio de extracción que la traducción para consistencia
                text_blocks = self.pdf_service.extract_text_blocks(file_path)
                
                # Filtrar bloques traducibles
                valid_blocks = [
                    block[2] for block in text_blocks 
                    if block[2] and len(block[2].strip()) > MIN_TEXT_LENGTH
                ]
                
                stats["translatable_items"] = len(valid_blocks)
                stats["preview_text"] = "\n".join(valid_blocks[:8])[:2000]
                
            elif file_type == "docx":
                doc = Document(file_path)
                texts = [p.text for p in doc.paragraphs if self._should_translate(p.text)]
                for table in doc.tables:
                    for row in table.rows:
                        for cell in row.cells:
                            for para in cell.paragraphs:
                                if self._should_translate(para.text):
                                    texts.append(para.text)
                stats["translatable_items"] = len(texts)
                stats["preview_text"] = "\n".join(texts[:8])[:2000]
                
            elif file_type == "xlsx":
                wb = load_workbook(file_path, read_only=True)
                texts = []
                for sheet in wb.sheetnames:
                    for row in wb[sheet].iter_rows(values_only=True):
                        for cell in row:
                            if cell and isinstance(cell, str) and self._should_translate(cell):
                                texts.append(cell)
                wb.close()
                stats["translatable_items"] = len(texts)
                stats["preview_text"] = "\n".join(texts[:10])[:2000]
                
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {e}")
            stats["error"] = str(e)
        
        return stats


# Instancia global
document_service = DocumentService()
