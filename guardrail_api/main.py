import time
from fastapi import FastAPI
from pydantic import BaseModel
from llm_guard.input_scanners import PromptInjection, Toxicity
from llm_guard.input_scanners.prompt_injection import MatchType

app = FastAPI(title="Guardrail API")

print("Loading Guardrail models...")
injection_scanner = PromptInjection(threshold=0.5, match_type=MatchType.FULL)
toxicity_scanner = Toxicity(threshold=0.7)
print("✅ Models loaded.")

class ScanRequest(BaseModel):
    text: str

class ScanResponse(BaseModel):
    is_safe: bool
    reason: str = ""

@app.post("/scan", response_model=ScanResponse)
def scan_text(request: ScanRequest):
    # 1. Check Injection
    _, is_valid_inj, risk_inj = injection_scanner.scan(request.text)
    if not is_valid_inj:
        return ScanResponse(is_safe=False, reason="Prompt injection detected")
        
    # 2. Check Toxicity
    _, is_valid_tox, risk_tox = toxicity_scanner.scan(request.text)
    if not is_valid_tox:
        return ScanResponse(is_safe=False, reason="Toxic content detected")
        
    return ScanResponse(is_safe=True)

@app.get("/health")
def health():
    return {"status": "ok"}