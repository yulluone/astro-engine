# In your query_service.py or equivalent file

import logging
import json
from typing import List, Dict
# Make sure you import your gemini_service
from . import gemini_service 

logger = logging.getLogger(__name__)

def refine_user_query(
    raw_user_message: str, 
    business_name: str,
    business_bio: str, # Renamed from business_type for clarity
    conversation_history: List[Dict]
) -> str:
    """
    Uses a fast LLM with conversational and business context to expand a raw user
    message into a rich, semantically-dense search query string for vector search.
    """
    logger.info(f"Query Expansion: Starting for raw message: '{raw_user_message, conversation_history, business_bio}'")
    
    if not raw_user_message or not raw_user_message.strip():
        logger.warning("Query Expansion: Raw message is empty, returning empty string.")
        return ""

    # Construct the new, more powerful prompt
    prompt = f"""
    You are a Search Query Expansion Engine. Your expert task is to analyze a user's message in the chat context of a conversation and the business they are talking to to understand the user's intent, then generate a single, powerful descriptive search query string for our knowledge. This string should be semantically dense with relevant keywords to maximize the chance of finding a match in a vector database once the query is converted to embeddings.

    **BUSINESS CONTEXT:**
    - Name: {business_name}
    - Description: {business_bio}

    **RECENT CONVERSATION HISTORY (for context):**
    {json.dumps(conversation_history)}

    **USER'S LATEST MESSAGE:**
    "{raw_user_message}"

    **INSTRUCTIONS:**
    1.  **Analyze True Intent:** Read the "USER'S LATEST MESSAGE" in the context of the "RECENT CONVERSATION HISTORY". Do not just rephrase the words; infer the user's underlying need. For example, if the user previously asked about locations and now says "the one downtown," their intent is "downtown location hours." If a user says "I'm cold" to a restaurant, their intent is about "hot drinks or food."
    2.  **Brainstorm Keywords:** Based on the true intent, generate a list of diverse, relevant keywords and synonyms.
    3.  **Preserve Specifics:** ALWAYS include any specific names, numbers, or constraints from the user's message (e.g., "500 Ksh," "chocolate cake," "CBD").
    4.  **Construct the Final Query:** Combine all of this into a single, comma-separated string. The string should be a flat list of concepts. Do not use nested structures.

    **Example 1:**
    - User Message: "I'm looking for lunch and my budget is 500 bob"
    - Expanded Query: "Affordable lunch under 500 ksh, savory midday meal, cheap food options, value menu items"

    **Example 2:**
    - History: [{"role": "assistant", "content": "Our cakes are delicious!"}]
    - User Message: "What about the chocolate one?"
    - Expanded Query: "Chocolate cake details, price of chocolate cake, ingredients in chocolate cake"

    **Example 3:**
    - Business Type: "Clothing Store"
    - User Message: "I'm feeling cold"
    - Expanded Query: "Warm apparel, sweaters, jackets, hoodies, winter clothing"

    **Your Expanded Search Query:**
    """

    # We use the fast, non-thinking text generation for this task.
    expanded_query = gemini_service.generate_text(prompt)

    if not expanded_query or not expanded_query.strip():
        logger.warning("Query Expansion: LLM returned an empty query. Falling back to the original raw message.")
        return raw_user_message

    final_query = expanded_query.strip()
    logger.info(f"Query Expansion: Final query for embedding is: '{final_query}'")
    return final_query