# app/nodes/validate.py
import time
from typing import Any, Dict
from app.graph.state import AgentState

MIN_LEN = 5
NON_ANSWERS = {"ok", "okay", "sure", "yes", "no", "understood", "got it"}

def validate_node(state: AgentState, config: dict = None) -> Dict[str, Any]:
    started = time.time()
    
    # 1. Safely extract the answer
    raw_answer = state.get("draft_answer")
    
    if isinstance(raw_answer, list):
        # If it's a list of blocks (like Gemini sometimes returns), extract the text
        answer = " ".join(
            str(c.get("text", "")) if isinstance(c, dict) else str(c)
            for c in raw_answer
        ).strip()
    else:
        # If it's already a string, just use it
        answer = str(raw_answer or "").strip()

    # 2. Validate
    valid = (
        bool(answer)
        and len(answer) >= MIN_LEN
        and answer.lower().rstrip(".!?") not in NON_ANSWERS
    )

    step = {
        "name": "validate",
        "started_at": started,
        "ended_at": time.time(),
        "input": {"len": len(answer)},
        "output": {"valid": valid},
        "error": None,
        "duration_ms": int((time.time() - started) * 1000),
    }

    # 3. Return the clean string
    if valid:
        return {
            "final_answer": answer, # Save the clean string!
            "status": "completed",
            "steps": [step],
        }
    return {
        "status": "invalid",
        "steps": [step],
    }