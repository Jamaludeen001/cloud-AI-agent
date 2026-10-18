# app/nodes/output_guardrail.py
import logging
import time
from typing import Any, Dict
from app.graph.state import AgentState
from llm_guard.output_scanners import Sensitive

logger = logging.getLogger(__name__)

logger.info("Initializing Output Guardrails...")
pii_scanner = Sensitive(entity_types=["CREDIT_CARD", "EMAIL_ADDRESS", "PHONE_NUMBER"])
logger.info("✅ Output Guardrails ready.")

def output_guardrail_node(state: AgentState, config: dict = None) -> Dict[str, Any]:
    started = time.time()
    
    # Safely extract string from list if Gemini returns a list of content blocks
    raw_answer = state.get("draft_answer", "")
    
    if isinstance(raw_answer, list):
        answer = " ".join(
            str(c.get("text", "")) if isinstance(c, dict) else str(c)
            for c in raw_answer
        ).strip()
    else:
        answer = str(raw_answer or "").strip()
        
    step = {
        "name": "output_guardrail",
        "started_at": started,
        "ended_at": time.time(),
        "input": {"len": len(answer)},
        "output": {"safe": True},
    }

    if not answer:
        logger.warning("[output_guardrail] Empty response detected.")
        return {
            "final_answer": "I could not generate a valid response. Please try rephrasing your question.",
            "status": "completed",
            "steps": [step]
        }

    try:
        sanitized_answer, is_valid_pii, risk_pii = pii_scanner.scan("", answer)
        
        if not is_valid_pii:
            logger.warning(f"[output_guardrail] PII detected and redacted (Risk: {risk_pii:.2f})")
            step["output"]["safe"] = False
            return {
                "final_answer": sanitized_answer,
                "status": "completed",
                "steps": [step]
            }
            
    except Exception as e:
        logger.error(f"[output_guardrail] Scanner failed: {e}")

    logger.info("[output_guardrail] Output passed security check.")
    return {
        "final_answer": answer,
        "status": "completed",
        "steps": [step]
    }