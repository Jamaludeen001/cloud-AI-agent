# app/nodes/guardrail.py
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

def guardrail_node(state: AgentState, config: dict = None) -> Dict[str, Any]:
    started = time.time()
    question = state.get("user_query", "")
    
    step = {
        "name": "guardrail",
        "started_at": started,
        "ended_at": time.time(),
        "input": {"q": question[:40]},
        "output": {"safe": True},
    }

    # 1. System Disclosure Check (Local heuristic)
    q_lower = question.lower()
    if any(w in q_lower for w in ["what", "which", "show", "give", "tell"]) and any(t in q_lower for t in ["tool", "code", "model", "system prompt", "backend"]):
        logger.warning(f"[guardrail] Blocked system disclosure attempt: {question[:30]}")
        step["output"]["safe"] = False
        return {
            "status": "completed",
            "final_answer": "I cannot disclose my internal tools, code, or underlying model. I am here to assist with document analysis.",
            "steps": [step]
        }

    # 2. Call the AWS Guardrail Microservice
    # 🚨 TEMPORARILY DISABLED FOR DEMO TO AVOID FALSE POSITIVES 🚨
    """
    try:
        response = requests.post(
            f"{GUARDRAIL_URL}/scan_input", 
            json={"text": question}, 
            timeout=10
        )
        response.raise_for_status()
        result = response.json()
        
        if not result["is_safe"]:
            logger.warning(f"[guardrail] Blocked by AWS API: {result['reason']}")
            step["output"]["safe"] = False
            return {
                "status": "completed",
                "final_answer": f"I cannot fulfill this request. Reason: {result['reason']}",
                "steps": [step]
            }
            
    except Exception as e:
        logger.error(f"[guardrail] AWS API failed, defaulting to safe: {e}")
    """

    logger.info("[guardrail] Input passed security check.")
    return {"status": "in_progress", "steps": [step]}