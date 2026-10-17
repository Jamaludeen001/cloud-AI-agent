# app/knowledge/fetcher.py
"""
Fetch text content from URLs, files, and pasted text.

Wikimedia (and many other public APIs) reject library-default
User-Agents like `python-requests/2.x`. A descriptive User-Agent
identifying this project satisfies their robot policy.
"""
import json
import logging
from pathlib import Path
from typing import Any

import requests

from app.config import config

logger = logging.getLogger(__name__)


# ── Descriptive User-Agent (required by Wikimedia and many public APIs) ──
_USER_AGENT = (
    "APIChat-SLM/1.0 "
    "(educational project; contact: admin@example.com)"
)

_DEFAULT_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Accept":     "application/json, text/plain, text/html, */*",
}


# ══════════════════════════════════════════════════════════
#  Public entry points
# ══════════════════════════════════════════════════════════
def fetch_api_text(url: str, text_limit: int = 50_000) -> str:
    """Fetch text from a URL."""
    logger.info("Fetching: %s (limit=%d chars)", url, text_limit)

    try:
        resp = requests.get(
            url,
            headers = _DEFAULT_HEADERS,
            timeout = config.default_timeout * 2,
            stream  = True,
        )
        resp.raise_for_status()
    except requests.HTTPError as e:
        raise ValueError(f"API returned HTTP {resp.status_code}: {resp.reason}") from e
    except requests.RequestException as e:
        raise ValueError(f"Failed to fetch URL: {e}") from e

    content = resp.raw.read(config.max_bytes, decode_content=True)
    try:
        text = content.decode(resp.encoding or "utf-8", errors="replace")
    except Exception:
        text = content.decode("utf-8", errors="replace")

    content_type = resp.headers.get("Content-Type", "")

    # ── JSON response ──
    if "application/json" in content_type or text.strip().startswith("{"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Content-Type said JSON but decode failed; returning raw")
            return text[:text_limit]

        extracted = _extract_text_from_json(data)
        if not extracted.strip():
            raise ValueError("API returned JSON but no usable text was found.")
        return extracted[:text_limit]

    # ── Plain text / HTML ──
    if not text.strip():
        raise ValueError("No usable text in response.")
    return text[:text_limit]


def fetch_from_file(path: str, text_limit: int = 50_000) -> str:
    """Read text from a local file, routing by extension."""
    p = Path(path)
    if not p.exists():
        raise ValueError(f"File not found: {path}")

    suffix = p.suffix.lower()
    text = ""

    if suffix == ".pdf":
        text = _read_pdf(p)
    elif suffix in (".txt", ".md", ".log", ".csv", ".json", ".html", ".xml", ".yaml", ".yml"):
        text = p.read_text(encoding="utf-8", errors="replace")
    else:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            raise ValueError(f"Unsupported file type '{suffix}': {e}")

    if not text.strip():
        raise ValueError("File contained no usable text.")

    if _looks_like_binary(text):
        raise ValueError(
            f"File appears to be binary, not text. Extension: '{suffix}'. "
            f"If this is a PDF, ensure pdfplumber/pypdf/PyMuPDF are installed."
        )

    return text[:text_limit]


def fetch_from_paste(text: str, text_limit: int = 50_000) -> str:
    """Clean and truncate pasted text."""
    if not text or not text.strip():
        raise ValueError("No text provided.")
    return text.strip()[:text_limit]


# ══════════════════════════════════════════════════════════
#  Safety checks
# ══════════════════════════════════════════════════════════
def _looks_like_binary(text: str) -> bool:
    """Refuse text that's clearly binary, even if the extension says otherwise."""
    if not text:
        return False
    sample = text[:1000]
    non_printable = sum(
        1 for c in sample
        if not c.isprintable() and c not in "\n\r\t"
    )
    return (non_printable / max(len(sample), 1)) > 0.10


# ══════════════════════════════════════════════════════════
#  JSON text extraction (Wikipedia + generic)
# ══════════════════════════════════════════════════════════
def _extract_text_from_json(data: Any) -> str:
    """Recursively pull usable text out of a JSON response."""
    if isinstance(data, dict):
        query = data.get("query")
        if isinstance(query, dict):
            pages = query.get("pages", {})
            parts = []
            for page in pages.values():
                if isinstance(page, dict):
                    extract = page.get("extract")
                    if isinstance(extract, str) and extract.strip():
                        parts.append(extract.strip())
            if parts:
                return "\n\n".join(parts)

        parse = data.get("parse")
        if isinstance(parse, dict):
            text_field = parse.get("text")
            if isinstance(text_field, dict):
                raw = text_field.get("*")
                if isinstance(raw, str) and raw.strip():
                    return raw
            elif isinstance(text_field, str) and text_field.strip():
                return text_field

        parts = []
        for value in data.values():
            if isinstance(value, str) and len(value.strip()) > 20:
                parts.append(value.strip())
            elif isinstance(value, (dict, list)):
                nested = _extract_text_from_json(value)
                if nested.strip():
                    parts.append(nested)
        return "\n\n".join(parts)

    if isinstance(data, list):
        parts = [_extract_text_from_json(item) for item in data]
        return "\n\n".join(p for p in parts if p.strip())

    if isinstance(data, str) and len(data.strip()) > 20:
        return data.strip()

    return ""


# ══════════════════════════════════════════════════════════
#  PDF reader — three-library cascade
# ══════════════════════════════════════════════════════════
def _read_pdf(path: Path) -> str:
    """
    Extract text from a PDF.

    Strategy (in order):
      1. pdfplumber    — handles most PDFs
      2. pypdf         — fallback for simple PDFs
      3. PyMuPDF       — the heavy gun. Works when the other two fail
                         because it reconstructs text from glyph tables
                         even when Unicode mappings are broken.

    If all three fail, the PDF is genuinely scanned (image of text) and
    needs OCR.
    """
    errors = []

    # ── 1. pdfplumber ──
    try:
        import pdfplumber
        parts = []
        with pdfplumber.open(str(path)) as pdf:
            total = len(pdf.pages)
            for page_num, page in enumerate(pdf.pages, 1):
                try:
                    text = page.extract_text() or ""
                except Exception as e:
                    logger.warning("[pdf] pdfplumber page %d/%d failed: %s", page_num, total, e)
                    continue
                if text.strip():
                    parts.append(text.strip())
        if parts:
            logger.info("[pdf] pdfplumber extracted %d pages", len(parts))
            return "\n\n".join(parts)
        logger.info("[pdf] pdfplumber returned no text")
    except ImportError:
        errors.append("pdfplumber not installed")
    except Exception as e:
        errors.append(f"pdfplumber: {e}")
        logger.warning("[pdf] pdfplumber failed: %s", e)

    # ── 2. pypdf ──
    try:
        try:
            from pypdf import PdfReader
        except ImportError:
            from PyPDF2 import PdfReader

        reader = PdfReader(str(path))
        if getattr(reader, "is_encrypted", False):
            try:
                reader.decrypt("")
            except Exception:
                raise ValueError("PDF is encrypted")

        parts = []
        total = len(reader.pages)
        for page_num, page in enumerate(reader.pages, 1):
            try:
                text = page.extract_text() or ""
            except Exception as e:
                logger.warning("[pdf] pypdf page %d/%d failed: %s", page_num, total, e)
                continue
            if text.strip():
                parts.append(text.strip())
        if parts:
            logger.info("[pdf] pypdf extracted %d pages", len(parts))
            return "\n\n".join(parts)
        logger.info("[pdf] pypdf returned no text")
    except ImportError:
        errors.append("pypdf not installed")
    except Exception as e:
        errors.append(f"pypdf: {e}")
        logger.warning("[pdf] pypdf failed: %s", e)

    # ── 3. PyMuPDF (fitz) — the heavy gun ──
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(str(path))
        parts = []
        total = len(doc)
        for page_num in range(total):
            try:
                text = doc[page_num].get_text("text") or ""
            except Exception as e:
                logger.warning("[pdf] PyMuPDF page %d/%d failed: %s", page_num + 1, total, e)
                continue
            if text.strip():
                parts.append(text.strip())
        doc.close()
        if parts:
            logger.info("[pdf] PyMuPDF extracted %d pages", len(parts))
            return "\n\n".join(parts)
        errors.append("PyMuPDF returned no text")
        logger.info("[pdf] PyMuPDF returned no text")
    except ImportError:
        errors.append("PyMuPDF not installed")
    except Exception as e:
        errors.append(f"PyMuPDF: {e}")
        logger.warning("[pdf] PyMuPDF failed: %s", e)

    # ── All three failed ──
    raise ValueError(
        "PDF contained no extractable text after trying pdfplumber, "
        "pypdf, and PyMuPDF. This PDF is likely a scanned image and "
        "needs OCR. Install: pip install pytesseract pdf2image"
    )