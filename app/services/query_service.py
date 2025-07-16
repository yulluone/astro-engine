# app/services/query_service.py
import logging
from . import gemini_service

logger = logging.getLogger(__name__)

def refine_user_query(raw_user_message: str) -> str:
    """
    Uses a fast LLM to refine a raw user message into a clean, optimal search query.
    """
    logger.info(f"Query Refinement: Starting for raw message: '{raw_user_message}'")
    
    if not raw_user_message or not raw_user_message.strip():
        logger.warning("Query Refinement: Raw message is empty. Returning as is.")
        return ""

    prompt = f"""You are a search query optimization engine. Your task is to read the user's message below and extract the core, essential search query. 
    - Remove all conversational fluff, greetings, or filler words.
    - If the message is in a language other than English, translate the core query to English.
    - The output should be a concise question or statement.

    **User's Message:**
    "{raw_user_message}"

    **Optimized Search Query:**
    """

    # We use the fast, non-thinking text generation for this simple task.
    refined_query = gemini_service.generate_text(prompt)

    if not refined_query or not refined_query.strip():
        logger.warning("Query Refinement: LLM returned an empty query. Falling back to original message.")
        return raw_user_message # Fallback to the original if the LLM fails

    logger.info(f"Query Refinement: Refined query is: '{refined_query.strip()}'")
    return refined_query.strip()