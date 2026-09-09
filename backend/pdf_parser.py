import fitz  # PyMuPDF
import os
from typing import List, Dict, Any

class PDFParser:
    """PDF parser leveraging PyMuPDF for structural text extraction and page grounding."""

    @staticmethod
    def get_page_count(pdf_path: str) -> int:
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        doc = fitz.open(pdf_path)
        count = len(doc)
        doc.close()
        return count

    @staticmethod
    def extract_pages(pdf_path: str) -> List[Dict[str, Any]]:
        """Extracts text page by page with explicit page numbers and metadata."""
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        doc = fitz.open(pdf_path)
        pages_data = []
        
        for i, page in enumerate(doc):
            page_num = i + 1
            text = page.get_text("text").strip()
            
            # Clean basic control chars but preserve formatting
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            cleaned_text = "\n".join(lines)
            
            pages_data.append({
                "page_number": page_num,
                "text": cleaned_text,
                "word_count": len(cleaned_text.split()),
                "is_empty": len(cleaned_text) == 0
            })
            
        doc.close()
        return pages_data

    @classmethod
    def chunk_pdf(cls, pdf_path: str, pages_per_chunk: int = 5) -> List[Dict[str, Any]]:
        """Groups pages into manageable chunks for LLM fact extraction."""
        pages = cls.extract_pages(pdf_path)
        filename = os.path.basename(pdf_path)
        chunks = []
        
        for i in range(0, len(pages), pages_per_chunk):
            chunk_pages = pages[i:i + pages_per_chunk]
            combined_text = ""
            page_numbers = []
            
            for p in chunk_pages:
                if not p["is_empty"]:
                    combined_text += f"\n--- [PAGE {p['page_number']}] ---\n" + p["text"]
                    page_numbers.append(p["page_number"])
                    
            if combined_text.strip():
                chunks.append({
                    "filename": filename,
                    "page_range": f"{page_numbers[0]}-{page_numbers[-1]}" if len(page_numbers) > 1 else str(page_numbers[0]),
                    "start_page": page_numbers[0] if page_numbers else i+1,
                    "end_page": page_numbers[-1] if page_numbers else i+1,
                    "text": combined_text
                })
                
        return chunks

if __name__ == "__main__":
    # Test script if any pdf exists
    print("PDFParser loaded successfully.")
