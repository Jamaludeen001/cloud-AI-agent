import os
from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

os.environ["HF_HOME"] = "/app/hf_cache"

app = FastAPI(title="Qwen Embedding API")

print("Loading Qwen Embedder...")
model = SentenceTransformer("Qwen/Qwen3-Embedding-0.6B", device="cpu")
print("✅ Model loaded.")

class EmbedRequest(BaseModel):
    texts: list[str]

class EmbedResponse(BaseModel):
    embeddings: list[list[float]]

@app.post("/embed", response_model=EmbedResponse)
def embed_text(request: EmbedRequest):
    embeddings = model.encode(request.texts, normalize_embeddings=True)
    return EmbedResponse(embeddings=embeddings.tolist())

@app.get("/health")
def health():
    return {"status": "ok"}