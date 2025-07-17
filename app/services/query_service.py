# app/services/query_service.py
import logging
import json
from typing import List, Dict
from . import gemini_service

logger = logging.getLogger(__name__)

def refine_user_query(
    raw_user_message: str, 
    business_name: str,
    business_bio: str,
    conversation_history: List[Dict]
) -> str:
    """
    Uses a fast LLM with context to refine a user message into an optimal search query.
    """
    logger.info(f"Query Refinement: Starting for raw message: '{raw_user_message}'")
    
    if not raw_user_message or not raw_user_message.strip():
        return ""

    prompt = f"""
    You are an expert Search Intent Query Expansion Engine for Customer to business queries. Your goal is to take a user's message, remove anything generic or filler and rewrite it into a single, powerful search query string. The new string should be dense with relevant keywords and concepts to maximize the chances of finding a match in a vector database.
    **BUSINESS CONTEXT:**
    - Name: {business_name}
    - Bio: {business_bio}

    **RECENT CONVERSATION:**
    {json.dumps(conversation_history)}

    **USER'S LATEST MESSAGE:**
    "{raw_user_message}"

  **INSTRUCTIONS:**
    1.  **Identify the Core Intent:** What is the user's fundamental need? (e.g., "hungry for a cheap lunch").
    2.  **Brainstorm Synonyms and Related Concepts:** Think of alternative words and related ideas. For "lunch," think "midday meal," "food," "savory." For "salty," think "fries," "chips," "savory snack." For "I'm cold" at a restaurant, think "hot drink," "warm soup," "coffee," "tea."
    3.  **Preserve Key Constraints:** Retain any critical constraints like price ("under 500"), location, or specific ingredients.
    4.  **Combine into a Single String:** Construct a single, comma-separated string containing the core intent, the brainstormed concepts, and the constraints. This string will be used for a vector search.

    **Example 1:**
    - User Message: "I'm looking for lunch and my budget is 500 bob"
    - Expanded Query: "Affordable lunch under 500 ksh, savory midday meal, cheap food options, value meal"

    **Example 2:**
    - User Message: "I'm feeling cold"
    - Expanded Query: "Hot beverages, warm drinks, coffee, tea, hot chocolate, soup"

    **Your Expanded Search Query:**
    """

    # Use the fast, non-thinking text generation.
    refined_query = gemini_service.generate_text(prompt)

    if not refined_query or not refined_query.strip():
        logger.warning("Query Refinement: LLM returned an empty query. Falling back to original message.")
        return raw_user_message

    logger.info(f"Query Refinement: Refined query is: '{refined_query.strip()}'")
    return refined_query.strip()