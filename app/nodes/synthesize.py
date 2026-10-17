# app/nodes/synthesize.py
import logging
import time
from typing import Any, Dict
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from app.graph.state import AgentState
from app.services.llm_factory import get_llm

logger = logging.getLogger(__name__)

AGENT_SYSTEM_PROMPT = """
You are an expert AI assistant for a fintech document processing system. 
Your goal is to answer user queries accurately by utilizing the tools provided.

=== CORE OPERATING RULES ===

1. TOOL SELECTION:
- Use `calculate_math` for any arithmetic.
- Use `search_documents` for looking up information in the invoice database.

2. DYNAMIC METADATA EXTRACTION & EXECUTION:
When you need to use `search_documents`, scan the user's current query and the conversation history for identifiers.
- If the user provides a `customer_name` (e.g., "Xylona Preis"), you MUST pass it to the `customer_name` argument.
- If the user provides an `invoice_number` (e.g., "15951"), you MUST pass it to the `invoice_number` argument.
- NEVER pass a customer name into the `invoice_number` argument, or vice versa.
- If the user provides BOTH, pass both to the tool.
- If the user provides NEITHER, you must HALT. Do not call the tool. Reply to the user: "Please provide the customer name or invoice number."

3. TOOL ERRORS & RETRIES:
- If the tool returns an error, do NOT try again with the exact same arguments. If you get an error, just tell the user what happened.

4. FINAL SYNTHESIS:
- Once you have the retrieved facts, generate a direct, plain-text answer.
"""

def synthesize_node(state: AgentState, config: dict = None) -> Dict[str, Any]:
    started = time.time()
    llm = get_llm()
    
    messages = [SystemMessage(content=AGENT_SYSTEM_PROMPT)]
    
    for turn in state.get("history", []):
        messages.append(HumanMessage(content=turn["q"]))
        messages.append(AIMessage(content=turn["a"]))
        
    messages.append(HumanMessage(content=state["user_query"]))
    messages.extend(state.get("messages", []))

    response = llm.invoke(messages)
    
    step = {
        "name": "synthesize",
        "started_at": started,
        "ended_at": time.time(),
        "duration_ms": int((time.time() - started) * 1000),
    }

    if response.tool_calls:
        logger.info(f"[synthesize] LLM requested tool: {response.tool_calls[0]['name']}")
        return {
            "messages": [response],
            "status": "needs_tool",
            "steps": [step],
        }
        
    logger.info("[synthesize] LLM provided final answer")
    return {
        "draft_answer": response.content,
        "status": "completed",
        "steps": [step],
    }