# app/services/extractor.py
import logging
from langchain_core.messages import HumanMessage, SystemMessage
from app.services.llm_factory import get_llm
from app.schemas import DocumentMetadata

logger = logging.getLogger(__name__)

EXTRACTOR_PROMPT = """
You are an enterprise document classifier. 
Read the following text from a financial document and extract the requested JSON metadata.

Rules:
1. Identify the document type accurately (invoice, loan_application, credit_report, kyc, or unknown).
2. Extract the customer's full name.
3. Extract the document ID (e.g., invoice #, loan ID).
4. Provide a 1-sentence summary.
"""

def extract_metadata_with_ai(document_text: str) -> dict:
    """Uses Gemini to strictly extract metadata from the document text."""
    llm = get_llm().with_structured_output(DocumentMetadata)
    
    # We only need the first 2000 chars to identify the document type and name
    sample_text = document_text[:2000]
    
    try:
        result: DocumentMetadata = llm.invoke([
            SystemMessage(content=EXTRACTOR_PROMPT),
            HumanMessage(content=f"Document Text:\n{sample_text}")
        ])
        
        logger.info(f"[extractor] AI extracted: {result.model_dump()}")
        return result.model_dump()
    except Exception as e:
        logger.error(f"[extractor] Failed to extract metadata: {e}")
        return {
            "doc_type": "unknown",
            "customer_name": "Unknown",
            "document_id": "Unknown",
            "summary": "Extraction failed."
        }