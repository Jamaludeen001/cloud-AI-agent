# build_qdrant_db.py
import os
import re
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Point to your cache
os.environ["HF_HOME"] = "D:/hf_cache"

from llama_index.core import (
    SimpleDirectoryReader, VectorStoreIndex, StorageContext, Settings
)
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PayloadSchemaType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 1. Configure Qwen Embedder
Settings.embed_model = HuggingFaceEmbedding(
    model_name="Qwen/Qwen3-Embedding-0.6B",
    device="cpu"
)
Settings.node_parser = Settings.node_parser.from_defaults(chunk_size=512, chunk_overlap=50)

# 2. Connect to Qdrant Cloud
client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY")
)
COLLECTION_NAME = "invoices"

# ── Create collection if it doesn't exist ──
if not client.collection_exists(COLLECTION_NAME):
    logger.info(f"Creating new collection: {COLLECTION_NAME}")
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
    )
else:
    logger.info(f"Collection {COLLECTION_NAME} already exists. Appending new files.")

# ── THE FIX: Create Payload Indexes for Metadata Filtering ──
logger.info("Creating payload indexes for customer_name and invoice_number...")
client.create_payload_index(
    collection_name=COLLECTION_NAME,
    field_name="customer_name",
    field_schema=PayloadSchemaType.KEYWORD,
)
client.create_payload_index(
    collection_name=COLLECTION_NAME,
    field_name="invoice_number",
    field_schema=PayloadSchemaType.KEYWORD,
)

vector_store = QdrantVectorStore(client=client, collection_name=COLLECTION_NAME)

# 3. Load and Parse PDFs dynamically
DATA_DIR = r"D:\RAG AGENT\test_data"  # Fixed the \t issue here
logger.info(f"Loading documents from {DATA_DIR}...")

def extract_metadata(file_path: str) -> dict:
    filename = Path(file_path).name
    clean_name = filename.replace("_", " ")
    match = re.match(r"invoice\s+(.+)\s+(\d+)\.pdf", clean_name, re.IGNORECASE)
    
    if match:
        return {
            "customer_name": " ".join(match.group(1).split()).strip(),
            "invoice_number": match.group(2).strip(),
            "source_file": filename
        }
    return {"source_file": filename}

# ── Get list of files ALREADY in the database ──
logger.info("Checking database for existing files...")
existing_files = set()
scroll_results = client.scroll(
    collection_name=COLLECTION_NAME,
    limit=10000,
    with_payload=["source_file"],
    with_vectors=False
)[0]

for point in scroll_results:
    if "source_file" in point.payload:
        existing_files.add(point.payload["source_file"])

logger.info(f"Found {len(existing_files)} files already in the database.")

# 4. Process ONLY new files
documents = []
for filepath in Path(DATA_DIR).glob("*.pdf"):
    filename = filepath.name
    
    # If the file is already in Qdrant, skip it!
    if filename in existing_files:
        continue
        
    logger.info(f"Processing new file: {filename}")
    try:
        reader = SimpleDirectoryReader(input_files=[str(filepath)])
        docs = reader.load_data()
        
        metadata = extract_metadata(str(filepath))
        for doc in docs:
            doc.metadata.update(metadata)
            documents.append(doc)
    except Exception as e:
        logger.error(f"Failed to read {filename}: {e}")

if not documents:
    logger.info("✅ No new files to process. Database is up to date!")
else:
    logger.info(f"Embedding {len(documents)} new chunks into Qdrant...")
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    VectorStoreIndex.from_documents(documents, storage_context=storage_context)
    logger.info("✅ Incremental update complete!")