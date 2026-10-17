# app/services/llm_factory.py
from functools import lru_cache
import logging
from app.config import config
from app.tools import TOOLS

logger = logging.getLogger(__name__)

@lru_cache(maxsize=1)
def get_llm():
    from langchain_google_genai import ChatGoogleGenerativeAI
    
    api_key = config.llm_api_key.strip()
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is not set.")

    llm = ChatGoogleGenerativeAI(
        model=config.llm_model,
        google_api_key=api_key,
        temperature=0.0,
        convert_system_message_to_human=True,
    )
    
    # Bind the tools so the LLM knows they exist
    return llm.bind_tools(TOOLS)