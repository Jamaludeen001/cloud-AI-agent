# app/tools.py
import os
from dotenv import load_dotenv
load_dotenv()

# Point to your exact cache folder
os.environ["HF_HOME"] = "D:/hf_cache"

import logging
from typing import Optional
from langchain_core.tools import tool
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from llama_index.core import VectorStoreIndex, Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore

logger = logging.getLogger(__name__)

# ── 1. Load ONLY the Embedder ──
Settings.embed_model = HuggingFaceEmbedding(
    model_name="Qwen/Qwen3-Embedding-0.6B",
    device="cpu"
)

# ── 2. Connect to Qdrant Cloud ──
client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY")
)
vector_store = QdrantVectorStore(client=client, collection_name="invoices")
qdrant_index = VectorStoreIndex.from_vector_store(vector_store=vector_store)

@tool
def search_documents(
    query: str, 
    customer_name: Optional[str] = None, 
    invoice_number: Optional[str] = None
) -> str:
    """
    Search the invoices for facts and details.
    You must provide at least ONE of the following filters: customer_name OR invoice_number.
    """
    logger.info(f"[tool] Qdrant search: '{query}' | Customer: {customer_name} | Invoice: {invoice_number}")
    
    must_filters = []
    if customer_name:
        must_filters.append(
            FieldCondition(key="customer_name", match=MatchValue(value=str(customer_name).strip()))
        )
    if invoice_number:
        must_filters.append(
            FieldCondition(key="invoice_number", match=MatchValue(value=str(invoice_number).strip()))
        )
        
    metadata_filter = Filter(must=must_filters) if must_filters else None
    
    # Notice: NO RERANKER HERE
    retriever = qdrant_index.as_retriever(
        similarity_top_k=3,
        vector_store_kwargs={"qdrant_filters": metadata_filter}
    )
    
    nodes = retriever.retrieve(query)
    
    if not nodes:
        return f"No documents found matching your criteria (Customer: {customer_name}, Invoice: {invoice_number})."
        
    return "\n\n".join([f"[{i+1}] {node.text}" for i, node in enumerate(nodes)])

@tool
def calculate_math(expression: str) -> str:
    """Evaluate a mathematical expression."""
    try:
        return str(eval(expression))
    except Exception as e:
        return f"Error: {e}"

TOOLS = [search_documents, calculate_math]