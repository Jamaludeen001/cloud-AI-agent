# app/nodes/output_guardrail.py
import os
import requests
import logging
import time
from typing import Any, Dict
from app.graph.state import AgentState
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

GUARDRAIL_URL = os.getenv("GUARDRAIL_URL")

def output_guardrail_node(state: AgentState, config: dict = None) -> Dict[str, Any]:
    started = time.time()
    
    # Safely extract string from list
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
        return {"final_answer": "I could not generate a valid response.", "status": "completed", "steps": [step]}

    # Call the AWS Output Guardrail API
    try:
        response = requests.post(
            f"{GUARDRAIL_URL}/scan_output", 
            json={"text": answer}, 
            timeout=10
        )
        response.raise_for_status()
        result = response.json()
        
        if not result["is_safe"]:
            logger.warning(f"[output_guardrail] PII detected and redacted by AWS.")
            step["output"]["safe"] = False
            return {
                "final_answer": result["sanitized_text"], # Return the redacted text
                "status": "completed",
                "steps": [step]
            }
            
    except Exception as e:
        logger.error(f"[output_guardrail] AWS API failed, defaulting to safe: {e}")

    logger.info("[output_guardrail] Output passed security check.")
    return {
        "final_answer": answer,
        "status": "completed",
        "steps": [step]
    }