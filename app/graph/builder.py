# app/graph/builder.py
from __future__ import annotations
import logging
from langgraph.graph import StateGraph, START, END

from app.graph.state import AgentState
from app.graph.checkpointer import build_checkpointer
from app.nodes.guardrail import guardrail_node
from app.nodes.route import route_node
from app.nodes.synthesize import synthesize_node
from app.nodes.tool_node import tool_node
from app.nodes.validate import validate_node
from app.nodes.output_guardrail import output_guardrail_node
from app.nodes.finalize import finalize_node

logger = logging.getLogger(__name__)

def _after_guardrail(state: AgentState) -> str:
    if state.get("status") == "completed":
        return "finalize"
    return "route"

def _after_route(state: AgentState) -> str:
    if state.get("status") == "completed":
        return "finalize"
    return "synthesize"

def _after_synthesize(state: AgentState) -> str:
    if state.get("status") == "needs_tool":
        return "tool_node"
    return "validate"

def _after_validate(state: AgentState) -> str:
    if state.get("status") == "completed":
        return "output_guardrail"
    steps = [s.get("name") for s in state.get("steps", [])]
    if steps.count("synthesize") >= 2:
        return "output_guardrail"
    return "synthesize"

def build_graph():
    builder = StateGraph(AgentState)

    builder.add_node("guardrail", guardrail_node)
    builder.add_node("route", route_node)
    builder.add_node("synthesize", synthesize_node)
    builder.add_node("tool_node", tool_node)
    builder.add_node("validate", validate_node)
    builder.add_node("output_guardrail", output_guardrail_node)
    builder.add_node("finalize", finalize_node)

    builder.add_edge(START, "guardrail")
    
    builder.add_conditional_edges("guardrail", _after_guardrail, {
        "route": "route",
        "finalize": "finalize",
    })

    builder.add_conditional_edges("route", _after_route, {
        "synthesize": "synthesize",
        "finalize": "finalize",
    })

    builder.add_conditional_edges("synthesize", _after_synthesize, {
        "tool_node": "tool_node",
        "validate": "validate",
    })

    builder.add_edge("tool_node", "synthesize")

    builder.add_conditional_edges("validate", _after_validate, {
        "synthesize": "synthesize",
        "output_guardrail": "output_guardrail",
    })

    builder.add_edge("output_guardrail", "finalize")
    builder.add_edge("finalize", END)

    checkpointer = build_checkpointer()
    graph = builder.compile(checkpointer=checkpointer)
    logger.info("[graph] Dual-Guardrail ReAct Agent Compiled")
    return graph