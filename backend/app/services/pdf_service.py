# -*- coding: utf-8 -*-
"""PDF parsing service"""
import fitz  # PyMuPDF
import os
import sys
import subprocess
import tempfile
import re
from typing import List, Dict, Tuple
from app.config import get_settings

settings = get_settings()


class PDFService:
    """PDF processing service"""

    def __init__(self):
        self.upload_dir = settings.upload_dir
        os.makedirs(self.upload_dir, exist_ok=True)

    def _is_scanned_pdf(self, file_path: str) -> bool:
        """Check if PDF is scanned (image-based, no extractable text)"""
        doc = fitz.open(file_path)
        total_pages = len(doc)
        # Check first 5 pages
        check_pages = min(5, total_pages)
        total_text = ""
        for i in range(check_pages):
            total_text += doc[i].get_text().strip()
        doc.close()
        # If almost no text, it's likely a scanned PDF
        return len(total_text) < 50

    def _run_mineru_ocr(self, file_path: str, start_page: int = 0, end_page: int = 0) -> str:
        """Run MinerU CLI OCR on PDF and return extracted markdown text.

        Uses the pipeline backend with OCR method for Chinese scanned PDFs.
        Falls back to PyMuPDF text extraction if MinerU fails.
        """
        venv_python = sys.executable
        venv_scripts = os.path.dirname(venv_python)
        mineru_exe = os.path.join(venv_scripts, "mineru.exe")
        if not os.path.exists(mineru_exe):
            mineru_exe = os.path.join(venv_scripts, "mineru")

        output_dir = tempfile.mkdtemp(prefix="mineru_ocr_")

        cmd = [
            mineru_exe,
            "-p", file_path,
            "-o", output_dir,
            "-m", "ocr",
            "-b", "pipeline",
            "-l", "ch",
            "-f", "false",   # disable formula parsing (no math in TCM questions)
            "-t", "false",   # disable table parsing (avoids loading table model)
        ]
        if start_page > 0 or end_page > 0:
            cmd.extend(["-s", str(start_page), "-e", str(end_page)])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
                encoding="utf-8",
                errors="replace"
            )
            if result.returncode != 0:
                print(f"MinerU OCR failed: {result.stderr[-500:]}")
                return ""

            # Find the markdown output file
            md_text = ""
            for root, dirs, files in os.walk(output_dir):
                for f in files:
                    if f.endswith(".md"):
                        md_path = os.path.join(root, f)
                        with open(md_path, "r", encoding="utf-8") as mf:
                            md_text += mf.read() + "\n"

            # Clean up temp directory
            import shutil
            shutil.rmtree(output_dir, ignore_errors=True)

            return md_text

        except subprocess.TimeoutExpired:
            print("MinerU OCR timed out after 600s")
            return ""
        except Exception as e:
            print(f"MinerU OCR error: {e}")
            return ""

    def extract_text(self, file_path: str) -> Tuple[str, int]:
        """Extract all text from PDF and return (text, total_pages).
        Automatically detects scanned PDFs and uses OCR if needed.
        """
        doc = fitz.open(file_path)
        total_pages = len(doc)
        doc.close()

        # Check if scanned PDF
        if self._is_scanned_pdf(file_path):
            print(f"Detected scanned PDF, using MinerU OCR: {file_path}")
            ocr_text = self._run_mineru_ocr(file_path)
            if ocr_text:
                # Add page markers based on markdown page breaks
                return ocr_text, total_pages
            print("OCR failed, falling back to PyMuPDF (will return empty text)")

        # Normal text extraction
        doc = fitz.open(file_path)
        full_text = ""
        for page_num in range(total_pages):
            page = doc[page_num]
            text = page.get_text()
            full_text += f"\n--- Page {page_num + 1} ---\n{text}"
        doc.close()
        return full_text, total_pages

    def extract_text_by_pages(self, file_path: str, chunk_size: int = 5) -> List[Dict]:
        """Extract text by page chunks.
        For scanned PDFs, runs MinerU OCR per chunk to avoid timeout.
        """
        doc = fitz.open(file_path)
        total_pages = len(doc)
        doc.close()

        is_scanned = self._is_scanned_pdf(file_path)

        if is_scanned:
            print(f"Scanned PDF detected, chunking with OCR: {file_path}")
            chunks = []
            for i in range(0, total_pages, chunk_size):
                start_page = i
                end_page = min(i + chunk_size - 1, total_pages - 1)
                ocr_text = self._run_mineru_ocr(file_path, start_page, end_page)
                chunks.append({
                    "start_page": start_page + 1,
                    "end_page": end_page + 1,
                    "text": ocr_text if ocr_text else f"\n--- Page {start_page+1} ---\n[OCR failed]"
                })
            return chunks

        # Normal text extraction
        doc = fitz.open(file_path)
        chunks = []
        for i in range(0, len(doc), chunk_size):
            chunk_text = ""
            start_page = i + 1
            end_page = min(i + chunk_size, len(doc))
            for page_num in range(i, end_page):
                page = doc[page_num]
                chunk_text += f"\n--- Page {page_num + 1} ---\n{page.get_text()}"
            chunks.append({
                "start_page": start_page,
                "end_page": end_page,
                "text": chunk_text
            })
        doc.close()
        return chunks

    def save_upload(self, filename: str, content: bytes) -> str:
        """Save uploaded file"""
        file_path = os.path.join(self.upload_dir, filename)
        with open(file_path, "wb") as f:
            f.write(content)
        return file_path

    def get_file_info(self, file_path: str) -> Dict:
        """Get PDF file info"""
        doc = fitz.open(file_path)
        info = {
            "page_count": len(doc),
            "title": doc.metadata.get("title", ""),
            "author": doc.metadata.get("author", ""),
            "is_scanned": self._is_scanned_pdf(file_path),
        }
        doc.close()
        return info
