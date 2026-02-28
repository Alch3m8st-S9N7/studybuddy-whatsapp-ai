import fitz  # PyMuPDF
import os
from typing import List, Tuple
from app.utils.logger import logger

class PDFProcessorService:
    def __init__(self, max_file_size_mb: int = 10, max_pages: int = 50):
        self.max_bytes = max_file_size_mb * 1024 * 1024
        self.max_pages = max_pages

    def validate_pdf(self, filepath: str) -> Tuple[bool, str]:
        """Validates if file exists, is under size limit, and is a valid PDF."""
        if not os.path.exists(filepath):
            return False, "File not found."
            
        file_size = os.path.getsize(filepath)
        if file_size > self.max_bytes:
            return False, f"File exceeds the {self.max_bytes // (1024 * 1024)}MB limit."

        # Quick check if it can be opened
        try:
            doc = fitz.open(filepath)
            
            if len(doc) > self.max_pages:
                doc.close()
                return False, f"PDF exceeds maximum allowed pages ({self.max_pages})."
                
            doc.close()
            return True, "Valid PDF"
        except Exception as e:
            logger.error(f"Invalid PDF {filepath}: {str(e)}")
            return False, "File is not a valid PDF or is corrupted."

    def extract_and_chunk_text(self, filepath: str, chunk_word_size: int = 500) -> List[str]:
        """
        Extracts text from PDF and splits it into chunks based on approximate word counts.
        Roughly 500 words is ~700-800 tokens.
        """
        try:
            doc = fitz.open(filepath)
            full_text = []

            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                # Simple extraction
                text = page.get_text("text")
                if text:
                    full_text.append(text)
            
            doc.close()
            
            combined_text = " ".join(full_text)
            # Basic cleanup
            combined_text = combined_text.replace("\n", " ").strip()
            # Remove multiple spaces
            combined_text = " ".join(combined_text.split())

            return self._chunk_text(combined_text, chunk_size=chunk_word_size)

        except Exception as e:
            logger.error(f"Error extracting text from {filepath}: {str(e)}")
            return []

    def _chunk_text(self, text: str, chunk_size: int) -> List[str]:
        """Splits an entire string into smaller chunks of approximately `chunk_size` words."""
        words = text.split(" ")
        chunks = []
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i + chunk_size])
            chunks.append(chunk)
            
        return chunks

    def delete_file(self, filepath: str):
        """Securely deletes a file after processing to avoid storing copy-righted materials."""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                logger.info(f"Deleted file processing {filepath}")
        except Exception as e:
            logger.error(f"Failed to delete {filepath}: {str(e)}")

pdf_processor = PDFProcessorService()
