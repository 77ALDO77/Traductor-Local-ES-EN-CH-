"""
Servicio para procesamiento de documentos con preservación de formato.
Estrategia: Traducción IN-PLACE manteniendo estilos, imágenes y layout.
Ahora con conversión DOCX -> PDF al final si el origen fue PDF.
"""

import os
import asyncio
from pathlib import Path
from typing import Callable
import logging

from docx import Document
from docx.text.paragraph import Paragraph
from openpyxl import load_workbook
from pdf2docx import Converter
from docx2pdf import convert as docx_to_pdf_convert

from backend.services.ollama_service import translation_service


logger = logging.getLogger(__name__)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Configuración de batching
BATCH_SIZE = 5
MIN_TEXT_LENGTH = 2
MAX_CONCURRENT = 3


class DocumentService:
    """Servicio para traducción de documentos preservando formato."""
    
    def __init__(self):
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    
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
        Convierte DOCX a PDF usando docx2pdf.
        Preserva el layout, imágenes y formato del documento.
        """
        try:
            # docx2pdf.convert toma el archivo input y opcionalmente especifica output
            docx_to_pdf_convert(str(docx_path), str(output_path))
            return output_path
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
                source_language=source_lang,
                target_language=target_lang
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
        
        for run in paragraph.runs[1:]:
            run.text = ""
    
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
        
        # Párrafos del cuerpo principal
        for para in doc.paragraphs:
            if self._should_translate(para.text):
                translatable_items.append(("paragraph", para))
        
        # Tablas del cuerpo principal
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for para in cell.paragraphs:
                        if self._should_translate(para.text):
                            translatable_items.append(("paragraph", para))
        
        # Headers y Footers
        for section in doc.sections:
            if section.header:
                for para in section.header.paragraphs:
                    if self._should_translate(para.text):
                        translatable_items.append(("paragraph", para))
            if section.footer:
                for para in section.footer.paragraphs:
                    if self._should_translate(para.text):
                        translatable_items.append(("paragraph", para))
        
        total_items = len(translatable_items)
        
        if total_items == 0:
            doc.save(output_path)
            return
        
        # Procesar en batches
        for batch_start in range(0, total_items, BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, total_items)
            batch_items = translatable_items[batch_start:batch_end]
            
            texts_to_translate = [item[1].text for item in batch_items]
            translated_texts = await self._translate_batch(
                texts_to_translate, source_lang, target_lang
            )
            
            for i, (item_type, item) in enumerate(batch_items):
                if item_type == "paragraph":
                    self._replace_paragraph_text_preserve_format(
                        item, translated_texts[i]
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
            # 1. Convertir PDF a DOCX
            temp_docx_path = input_path.with_suffix('.temp.docx')
            
            if progress_callback:
                progress_callback(0, 100, "Convirtiendo PDF a DOCX...")
            
            self.convert_pdf_to_docx(input_path, temp_docx_path)
            
            # 2. Traducir el DOCX temporal
            temp_translated_docx = output_path.with_stem(
                output_path.stem + "_translated"
            ).with_suffix('.temp_translated.docx')
            
            await self.translate_docx_preserving_format(
                temp_docx_path,
                temp_translated_docx,
                source_lang,
                target_lang,
                progress_callback
            )
            
            # 3. Convertir DOCX traducido de vuelta a PDF
            final_output_pdf = output_path.with_suffix('.pdf')
            
            if progress_callback:
                progress_callback(90, 100, "Convirtiendo a PDF final...")
            
            self.convert_docx_to_pdf(temp_translated_docx, final_output_pdf)
            
            # 4. Limpiar temporales
            if temp_docx_path.exists():
                os.remove(temp_docx_path)
            if temp_translated_docx.exists():
                os.remove(temp_translated_docx)
            
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
                temp_path = file_path.with_suffix('.preview.docx')
                self.convert_pdf_to_docx(file_path, temp_path)
                doc = Document(temp_path)
                texts = [p.text for p in doc.paragraphs if self._should_translate(p.text)]
                stats["translatable_items"] = len(texts)
                stats["preview_text"] = "\n".join(texts[:3])[:500]
                os.remove(temp_path)
                
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
                stats["preview_text"] = "\n".join(texts[:3])[:500]
                
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
                stats["preview_text"] = "\n".join(texts[:5])[:500]
                
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {e}")
            stats["error"] = str(e)
        
        return stats


# Instancia global
document_service = DocumentService()
