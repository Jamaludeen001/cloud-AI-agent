# app/tools.py
import os
import requests
from dotenv import load_dotenv
load_dotenv()

import logging
from typing import Optional, List
from langchain_core.tools import tool
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from llama_index.core import VectorStoreIndex, Settings
from llama_index.core.embeddings import BaseEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore

logger = logging.getLogger(__name__)

EMBEDDER_URL = "http://qwen-e-LoadB-40IFScOlvagH-1351019476.us-east-1.elb.amazonaws.com"

class CloudQwenEmbedding(BaseEmbedding):
    def _get_text_embedding(self, text: str) -> List[float]:
        print(f"SENDING TO Embedder: '{text[:30]}...'")
        response = requests.post(f"{EMBEDDER_URL}/embed", json={"texts": [text]}, timeout=30)
        print(f"✅ RECEIVED FROM Embedder: Status {response.status_code}")
        response.raise_for_status()
        return response.json()["embeddings"][0]

    def _get_query_embedding(self, query: str) -> List[float]:
        return self._get_text_embedding(query)

    async def _aget_query_embedding(self, query: str) -> List[float]:
        return self._get_query_embedding(query)

Settings.embed_model = CloudQwenEmbedding()

client = QdrantClient(url=os.getenv("QDRANT_URL"), api_key=os.getenv("QDRANT_API_KEY"))

# Matches your exact database collection name
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
    logger.info(f"[tool] Qdrant search: '{query}' | Cust: {customer_name} | Inv: {invoice_number}")
    
    must_filters = []
    if customer_name:
        must_filters.append(FieldCondition(key="customer_name", match=MatchValue(value=str(customer_name).strip())))
    if invoice_number:
        must_filters.append(FieldCondition(key="invoice_number", match=MatchValue(value=str(invoice_number).strip())))
        
    metadata_filter = Filter(must=must_filters) if must_filters else None
    
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