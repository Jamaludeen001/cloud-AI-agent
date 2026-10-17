# app/graph/builder.py
import logging
from langgraph.graph import StateGraph, START, END
from app.graph.state import AgentState
from app.graph.checkpointer import build_checkpointer
from app.nodes.route import route_node
from app.nodes.synthesize import synthesize_node
from app.nodes.tool_node import tool_node
from app.nodes.validate import validate_node
from app.nodes.finalize import finalize_node

logger = logging.getLogger(__name__)

def _after_route(state: AgentState) -> str:
    if state.get("status") == "completed": 
        return "finalize"
    return "synthesize"

def _after_synthesize(state: AgentState) -> str:
    if state.get("status") == "needs_tool":
        return "tool_node"
    return "validate"

def build_graph():
    builder = StateGraph(AgentState)

    builder.add_node("route", route_node)
    builder.add_node("synthesize", synthesize_node)
    builder.add_node("tool_node", tool_node)
    builder.add_node("validate", validate_node)
    builder.add_node("finalize", finalize_node)

    builder.add_edge(START, "route")
    
    builder.add_conditional_edges("route", _after_route, {
        "synthesize": "synthesize",
        "finalize": "finalize",
    })
    
    # The ReAct Loop: Synthesize decides if it needs a tool
    builder.add_conditional_edges("synthesize", _after_synthesize, {
        "tool_node": "tool_node",
        "validate": "validate",
    })
    
    # After the tool runs, ALWAYS go back to synthesize to read the result
    builder.add_edge("tool_node", "synthesize")
    
    builder.add_edge("validate", "finalize")
    builder.add_edge("finalize", END)

    checkpointer = build_checkpointer()
    logger.info("[graph] ReAct Agent Compiled")
    return builder.compile(checkpointer=checkpointer)