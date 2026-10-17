# app/services/ingest.py
import logging
from typing import Any, Dict

from llama_index.core import Document, VectorStoreIndex, Settings
from llama_index.core.node_parser import SentenceSplitter

# Keep your custom cleaner and fetcher
from app.knowledge.fetcher import fetch_api_text, fetch_from_paste
from app.knowledge.cleaner import clean_text

logger = logging.getLogger(__name__)

# Configure LlamaIndex Chunking
Settings.node_parser = SentenceSplitter(chunk_size=512, chunk_overlap=50)

def _ingest_text(raw: str, label: str) -> Dict[str, Any]:
    # 1. Clean the text using your custom cleaner
    cleaned = clean_text(raw, strip_html=True, drop_noise=True)
    if not cleaned.strip():
        raise ValueError("No usable text after cleaning.")

    # 2. LlamaIndex handles the chunking and embedding internally
    # (It uses the Qwen embedder we configured in app/tools.py)
    doc = Document(text=cleaned, metadata={"source": label})
    llama_index = VectorStoreIndex.from_documents([doc])

    logger.info("[ingest] %s indexed with LlamaIndex", label)

    return {
        "llama_index": llama_index, 
        "source_label": label,
        "chunks": [], # FAISS is gone, but we keep this key for the API schema
        "stats": {"index_type": "LlamaIndex"}
    }

def ingest_text(text: str, text_limit: int, label: str) -> Dict[str, Any]:
    raw = fetch_from_paste(text, text_limit)
    return _ingest_text(raw, label)

def ingest_url(url: str, text_limit: int) -> Dict[str, Any]:
    raw = fetch_api_text(url, text_limit)
    return _ingest_text(raw, label=url)