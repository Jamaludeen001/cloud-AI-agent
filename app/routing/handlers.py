# app/routing/handlers.py
"""
Deterministic replies for non-query intents.
"""
from __future__ import annotations

import random


FIRST_NO_DATA   = "Hi! Ask me anything, or attach a URL, file, or text to ask about it."
FIRST_WITH_DATA = "Hi! Ask me anything about the data you've attached."

GREETING_FOLLOW_UPS = [
    "Hi again. What would you like to know?",
    "Hello. What else can I help with?",
    "Hi. Ask away.",
]

GRATITUDE_REPLIES = ["You're welcome.", "Glad to help.", "Anytime."]

ACK_REPLIES = [
    "Got it. What would you like to know next?",
    "Okay. What else can I help with?",
    "Sure. Ask away.",
]

FAREWELL_REPLIES = ["Goodbye! Come back anytime.", "See you next time.", "Take care!"]

IDENTITY_ANSWER = (
    "I am API Chat, a document assistant. "
    "Attach a URL, file, or pasted text, and I can answer questions about it. "
    "Without attached data, I can still help with general questions."
)

META_ANSWER = (
    "I can help with two things:\n\n"
    "1. Answer questions about documents you attach "
    "(URL, file, or pasted text).\n"
    "2. Answer general questions from my own knowledge.\n\n"
    "Click '+ Attach data' to add a document."
)


def reply_for(intent: str, has_history: bool, has_data: bool) -> str:
    """Return the canned reply for a deterministic intent."""
    if intent == "greeting":
        if not has_history:
            return FIRST_WITH_DATA if has_data else FIRST_NO_DATA
        return random.choice(GREETING_FOLLOW_UPS)

    if intent == "gratitude":
        return random.choice(GRATITUDE_REPLIES)

    if intent == "acknowledgment":
        return random.choice(ACK_REPLIES)

    if intent == "farewell":
        return random.choice(FAREWELL_REPLIES)

    if intent == "identity":
        return IDENTITY_ANSWER

    if intent == "meta":
        return META_ANSWER

    raise ValueError(f"No canned reply for intent: {intent}")