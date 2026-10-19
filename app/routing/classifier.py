# app/routing/classifier.py
"""
Hybrid intent classifier.

Order:
  1. Fast rules (empty, exact matches, cached)
  2. LLM classifier (structured output, cached result)
  3. Fallback to "query"
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import config

logger = logging.getLogger(__name__)


INTENTS = [
    "greeting",
    "gratitude",
    "acknowledgment",
    "farewell",
    "identity",
    "meta",
    "memory",
    "query",
]

# Fast paths — exact match, no LLM
FAST_RULES = {
    "hi": "greeting", "hello": "greeting", "hey": "greeting",
    "yo": "greeting", "sup": "greeting", "hiya": "greeting",
    "thanks": "gratitude", "thank you": "gratitude", "thx": "gratitude",
    "ok": "acknowledgment", "okay": "acknowledgment", "got it": "acknowledgment",
    "sure": "acknowledgment", "cool": "acknowledgment", "nice": "acknowledgment",
    "bye": "farewell", "goodbye": "farewell", "cya": "farewell",
}

CLASSIFIER_SYSTEM = """You are an intent classifier. Classify the user's message into exactly one of these labels:

- greeting: social greetings (hi, hello, good morning, how are you)
- gratitude: thanks, appreciation (thanks, thank you, cheers)
- acknowledgment: brief affirmations (ok, got it, sure, cool, nice)
- farewell: goodbyes (bye, see you, goodbye)
- identity: questions about who you are (who are you, what is your name)
- meta: questions about your capabilities (what can you do, help, how do I use this)
- memory: questions about the past conversation (what did I say, summarize, remember)
- query: any real question that isn't the above (what is 1+1, explain X, how tall is Y)

Return ONLY a JSON object: {"intent": "<label>"}
No other text. No explanation.
"""


def _normalize(text: str) -> str:
    t = text.strip().lower()
    while t and t[-1] in ".!? ":
        t = t[:-1]
    return t


@lru_cache(maxsize=2000)
def _classify_with_llm(normalized_question: str) -> str:
    """Call the LLM classifier. Cached by exact question string."""
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-3.5-flash-lite",
            google_api_key=config.llm_api_key,
            temperature=0.0,
            convert_system_message_to_human=True,
        )
        messages = [
            SystemMessage(content=CLASSIFIER_SYSTEM),
            HumanMessage(content=normalized_question),
        ]
        response = llm.invoke(messages)
        text = getattr(response, "content", "") or ""
        if isinstance(text, list):
            text = " ".join(
                c.get("text", "") if isinstance(c, dict) else str(c)
                for c in text
            )

        text = text.strip()
        # Strip markdown fences if the model wraps the JSON
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        parsed = json.loads(text)
        intent = str(parsed.get("intent", "")).strip().lower()
        if intent in INTENTS:
            return intent
        logger.warning("[classifier] Unknown intent %r, defaulting to query", intent)
        return "query"

    except Exception as e:
        logger.warning("[classifier] LLM classification failed: %s", e)
        return "query"


def classify(question: str) -> tuple[str, str]:
    """
    Classify a question into an intent.

    Returns:
        (intent, source) where source is "fast", "llm", or "fallback"
    """
    if not question or not question.strip():
        return "greeting", "fast"

    normalized = _normalize(question)

    if normalized in FAST_RULES:
        return FAST_RULES[normalized], "fast"

    intent = _classify_with_llm(normalized)
    return intent, "llm"