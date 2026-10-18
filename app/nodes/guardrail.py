# app/nodes/guardrail.py
import logging
import time
from typing import Any, Dict
from app.graph.state import AgentState
from llm_guard.input_scanners import PromptInjection, Toxicity
from llm_guard.input_scanners.prompt_injection import MatchType

logger = logging.getLogger(__name__)

# Initialize scanners ONCE
logger.info("Initializing Input Guardrails...")
injection_scanner = PromptInjection(threshold=0.5, match_type=MatchType.FULL)
toxicity_scanner = Toxicity(threshold=0.7)
logger.info("✅ Input Guardrails ready.")

def is_meta_question(question: str) -> bool:
    """Blocks requests probing system internals (tools, code, model)."""
    q = question.lower()
    triggers = ["tool", "code", "model", "system prompt", "instructions", "backend"]
    asks_about_system = any(word in q for word in ["what", "which", "show", "give", "tell", "list"])
    return asks_about_system and any(trigger in q for trigger in triggers)

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

    # 1. System Disclosure Check
    if is_meta_question(question):
        logger.warning(f"[guardrail] Blocked system disclosure attempt: {question[:30]}")
        step["output"]["safe"] = False
        return {
            "status": "completed",
            "final_answer": "I cannot disclose my internal tools, code, or underlying model. I am here to assist with document analysis.",
            "steps": [step]
        }

    # 2. Prompt Injection & Toxicity Checks
    try:
        _, is_valid_inj, risk_inj = injection_scanner.scan(question)
        if not is_valid_inj:
            logger.warning(f"[guardrail] Blocked injection (Risk: {risk_inj:.2f})")
            step["output"]["safe"] = False
            return {
                "status": "completed",
                "final_answer": "I cannot fulfill this request due to security policy violations.",
                "steps": [step]
            }
            
        _, is_valid_tox, risk_tox = toxicity_scanner.scan(question)
        if not is_valid_tox:
            logger.warning(f"[guardrail] Blocked toxic input (Risk: {risk_tox:.2f})")
            step["output"]["safe"] = False
            return {
                "status": "completed",
                "final_answer": "Please maintain a professional tone. I am here to assist with your financial documents.",
                "steps": [step]
            }
            
    except Exception as e:
        logger.error(f"[guardrail] Scanner failed: {e}")

    logger.info("[guardrail] Input passed security check.")
    return {"status": "in_progress", "steps": [step]}