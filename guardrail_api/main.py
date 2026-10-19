# guardrail_api/main.py
import time
from fastapi import FastAPI
from pydantic import BaseModel
from llm_guard.input_scanners import PromptInjection, Toxicity
from llm_guard.input_scanners.prompt_injection import MatchType
from llm_guard.output_scanners import Sensitive

app = FastAPI(title="Guardrail API")

print("Loading Guardrail models...")
injection_scanner = PromptInjection(threshold=0.5, match_type=MatchType.FULL)
toxicity_scanner = Toxicity(threshold=0.7)
pii_scanner = Sensitive(entity_types=["CREDIT_CARD", "EMAIL_ADDRESS", "PHONE_NUMBER"])
print("✅ Models loaded.")

class ScanRequest(BaseModel):
    text: str

class ScanResponse(BaseModel):
    is_safe: bool
    reason: str = ""
    sanitized_text: str = ""

@app.post("/scan_input", response_model=ScanResponse)
def scan_input(request: ScanRequest):
    # 1. Check Injection
    _, is_valid_inj, risk_inj = injection_scanner.scan(request.text)
    if not is_valid_inj:
        return ScanResponse(is_safe=False, reason="Prompt injection detected")
        
    # 2. Check Toxicity
    _, is_valid_tox, risk_tox = toxicity_scanner.scan(request.text)
    if not is_valid_tox:
        return ScanResponse(is_safe=False, reason="Toxic content detected")
        
    return ScanResponse(is_safe=True)

@app.post("/scan_output", response_model=ScanResponse)
def scan_output(request: ScanRequest):
    # Scan for PII and Redact
    sanitized_text, is_valid_pii, risk_pii = pii_scanner.scan("", request.text)
    
    if not is_valid_pii:
        return ScanResponse(is_safe=False, reason="PII detected", sanitized_text=sanitized_text)
        
    return ScanResponse(is_safe=True, sanitized_text=request.text)

@app.get("/health")
def health():
    return {"status": "ok"}