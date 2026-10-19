# app/schemas.py
from pydantic import BaseModel, Field
from typing import Literal

class DocumentMetadata(BaseModel):
    doc_type: Literal["invoice", "loan_application", "credit_report", "kyc", "unknown"] = Field(
        description="The exact type of the document."
    )
    customer_name: str = Field(
        description="The full name of the primary customer or borrower."
    )
    document_id: str = Field(
        description="The invoice number, loan ID, or report ID."
    )
    summary: str = Field(
        description="A 1-sentence summary of what this document is about."
    )