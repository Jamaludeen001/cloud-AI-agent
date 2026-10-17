# app/nodes/tool_node.py
import logging
import time
from typing import Any, Dict
from langchain_core.messages import ToolMessage
from app.graph.state import AgentState
from app.tools import TOOLS

logger = logging.getLogger(__name__)

def tool_node(state: AgentState, config: dict = None) -> Dict[str, Any]:
    started = time.time()
    last_message = state["messages"][-1]
    tool_messages = []
    tool_registry = {t.name: t for t in TOOLS}
    
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = dict(tool_call["args"])
        tool_id = tool_call["id"]
        
        # Enforce Slot-Filling in Python
        if tool_name == "search_documents":
            if not tool_args.get("customer_name") and not tool_args.get("invoice_number"):
                logger.warning("[tool_node] Search blocked: No metadata provided.")
                tool_messages.append(ToolMessage(
                    content="Error: You must provide a customer_name or invoice_number to search documents. Ask the user for it.",
                    tool_call_id=tool_id
                ))
                continue
        
        logger.info(f"[tool_node] Executing {tool_name} with {tool_args}")
        
        if tool_name in tool_registry:
            try:
                # Execute the tool (This might crash due to Qdrant network error)
                result = tool_registry[tool_name].invoke(tool_args)
            except Exception as e:
                # CATCH THE CRASH HERE
                logger.exception(f"[tool_node] Execution failed for {tool_name}")
                result = f"Tool Execution Error: {str(e)}. Please check your arguments or try again."
        else:
            result = f"Tool {tool_name} not found."
            
        tool_messages.append(
            ToolMessage(content=str(result), tool_call_id=tool_id)
        )
        
    step = {
        "name": "tool_node",
        "started_at": started,
        "ended_at": time.time(),
        "duration_ms": int((time.time() - started) * 1000),
    }

    return {
        "messages": tool_messages,
        "status": "in_progress",
        "steps": [step],
    }