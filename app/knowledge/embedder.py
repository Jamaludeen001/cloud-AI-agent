# ingest/embedder.py
"""
Embedding and reranking models.

Optimizations:
  • Batch encoding (batch_size=16)
  • torch.no_grad() — no gradient tracking
  • Hybrid-CPU tuning: 4 threads (2 P-cores × 2 HT) instead of 10
  • OMP/MKL threads aligned with torch

Notes:
  • Vectors are L2-normalized so cosine similarity == inner product.
  • Both models are loaded lazily on first use (Embedder / Reranker construction).
"""
import os

# These MUST be set before torch/numpy import
os.environ.setdefault("HF_HOME", "D:/hf_cache")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")

import logging
from typing import List

import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from transformers import AutoModelForCausalLM, AutoTokenizer

logger = logging.getLogger(__name__)


# ── Hybrid CPU tuning (i5-1235U: 2 P-cores + 8 E-cores) ──
_THREADS = int(os.environ.get("SLM_TORCH_THREADS", "4"))
torch.set_num_threads(_THREADS)
torch.set_num_interop_threads(2)

logger.info("[embedder] torch threads=%d interop=2", _THREADS)


# ── Config ──
EMBEDDING_MODEL_NAME = "Qwen/Qwen3-Embedding-0.6B"
RERANKER_MODEL_NAME  = "Qwen/Qwen3-Reranker-0.6B"

EMBED_BATCH_SIZE     = 16          # ← key optimization
EMBED_MAX_LENGTH     = 512         # truncate chunks to ~512 tokens
RERANK_MAX_LENGTH    = 512


def _get_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


# ══════════════════════════════════════════════════════════
#  Embedder
# ══════════════════════════════════════════════════════════
class Embedder:
    """
    Sentence-embedding model with batched inference.

    Thread-safe after construction. Loading is expensive (~10s) — reuse
    the same instance across requests.
    """

    def __init__(self, model_name: str = EMBEDDING_MODEL_NAME):
        self.device = _get_device()
        logger.info("Loading embedding model: %s (device=%s)", model_name, self.device)

        self.model = SentenceTransformer(model_name, device=self.device)
        self.model.eval()
        self.model.max_seq_length = EMBED_MAX_LENGTH

        self.dim = self.model.get_sentence_embedding_dimension()
        logger.info("Embedder ready. Dimension: %d", self.dim)

    def embed(self, texts: List[str]) -> np.ndarray:
        """
        Encode a list of texts to embeddings.

        Returns a numpy array of shape (len(texts), self.dim),
        L2-normalized (so cosine similarity == dot product).
        """
        if not texts:
            return np.zeros((0, self.dim), dtype="float32")

        texts = [str(t) if t is not None else "" for t in texts]

        with torch.no_grad():
            embeddings = self.model.encode(
                texts,
                batch_size           = EMBED_BATCH_SIZE,
                show_progress_bar    = False,
                convert_to_numpy     = True,
                normalize_embeddings = True,
            )

        return embeddings.astype("float32")

    def embed_query(self, query: str) -> np.ndarray:
        """Embed a single query. Returns shape (self.dim,)."""
        with torch.no_grad():
            vec = self.model.encode(
                [query],
                batch_size           = 1,
                show_progress_bar    = False,
                convert_to_numpy     = True,
                normalize_embeddings = True,
            )
        return vec[0].astype("float32")


# ══════════════════════════════════════════════════════════
#  Reranker
# ══════════════════════════════════════════════════════════
class Reranker:
    """
    Cross-encoder reranker using Qwen3-Reranker.

    Scores (query, passage) pairs with a single forward pass each.
    Batching is possible in principle but Qwen3-Reranker's chat template
    doesn't batch well, so we batch at the Python level only.
    """

    def __init__(self, model_name: str = RERANKER_MODEL_NAME):
        self.device = _get_device()
        logger.info("Loading reranker: %s (device=%s)", model_name, self.device)

        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            padding_side="left",
            trust_remote_code=True,
        )

        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.float32,
            trust_remote_code=True,
        ).to(self.device)
        self.model.eval()

        # Qwen3-Reranker uses yes/no logits to score relevance
        self.yes_token_id = self.tokenizer.convert_tokens_to_ids("yes")
        self.no_token_id  = self.tokenizer.convert_tokens_to_ids("no")

        logger.info("Reranker ready.")

    def predict(self, pairs: List[tuple]) -> List[float]:
        """
        Score a list of (query, passage) pairs.

        Returns a list of floats, one score per pair.
        Higher = more relevant.
        """
        if not pairs:
            return []

        scores = []
        with torch.no_grad():
            for query, passage in pairs:
                scores.append(self._score_pair(query, passage))
        return scores

    def _score_pair(self, query: str, passage: str) -> float:
        prompt = self._build_rerank_prompt(query, passage)

        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=RERANK_MAX_LENGTH,
            padding=False,
        ).to(self.device)

        outputs = self.model(**inputs)
        logits = outputs.logits[0, -1, :]     # last token's logits

        yes_logit = logits[self.yes_token_id].item()
        no_logit  = logits[self.no_token_id].item()

        # Softmax over {yes, no}
        exp_yes = np.exp(yes_logit)
        exp_no  = np.exp(no_logit)
        score   = exp_yes / (exp_yes + exp_no)

        return float(score)

    def _build_rerank_prompt(self, query: str, passage: str) -> str:
        """Build Qwen3-Reranker prompt."""
        return (
            "<|im_start|>system\n"
            "Judge whether the Document meets the requirements based on the Query "
            'and the Instruct provided. Note that the answer can only be "yes" or "no".'
            "<|im_end|>\n"
            "<|im_start|>user\n"
            f"<Instruct>: Given a web search query, retrieve relevant passages that answer the query.\n"
            f"<Query>: {query}\n"
            f"<Document>: {passage}"
            "<|im_end|>\n"
            "<|im_start|>assistant\n"
        )