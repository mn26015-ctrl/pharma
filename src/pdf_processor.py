"""
PDF Processing Module
Extracts text, splits into chunks, deduplicates
"""

import io
import re
import hashlib
from typing import List, Tuple


def extract_text_from_pdf(file_bytes: bytes) -> Tuple[str, int]:
    """Extract text from PDF bytes. Returns (full_text, page_count)"""
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            pages = []
            for page in pdf.pages:
                text = page.extract_text() or ""
                pages.append(text)
            return "\n\n".join(pages), len(pdf.pages)
    except ImportError:
        pass

    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        pages = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
        return "\n\n".join(pages), len(reader.pages)
    except Exception:
        pass

    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        pages = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
        return "\n\n".join(pages), len(reader.pages)
    except Exception as e:
        raise ValueError(f"Could not extract PDF text: {e}")


def clean_text(text: str) -> str:
    """Clean extracted text"""
    # Remove excessive whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    # Remove page numbers and headers (simple heuristic)
    text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)
    # Remove very short lines that are likely artifacts
    lines = [l for l in text.split('\n') if len(l.strip()) > 3 or not l.strip()]
    return '\n'.join(lines).strip()


def split_into_chunks(text: str, chunk_size: int = 1500, overlap: int = 200) -> List[str]:
    """
    Split text into overlapping chunks for processing.
    chunk_size in characters (≈375 tokens), overlap for context continuity.
    """
    # Try to split on paragraph boundaries
    paragraphs = re.split(r'\n{2,}', text)
    chunks = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current) + len(para) + 2 <= chunk_size:
            current = (current + "\n\n" + para).strip()
        else:
            if current:
                chunks.append(current)
                # Overlap: keep last overlap chars of previous chunk
                words = current.split()
                overlap_text = " ".join(words[-max(1, overlap // 6):])
                current = (overlap_text + "\n\n" + para).strip()
            else:
                # Para itself is too long, split by sentence
                sentences = re.split(r'(?<=[.!?])\s+', para)
                for sent in sentences:
                    if len(current) + len(sent) + 1 <= chunk_size:
                        current = (current + " " + sent).strip()
                    else:
                        if current:
                            chunks.append(current)
                        current = sent

    if current:
        chunks.append(current)

    # Filter out very short chunks
    chunks = [c for c in chunks if len(c.strip()) > 100]
    return chunks


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token"""
    return len(text) // 4


def file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
