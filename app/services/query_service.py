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
				conversation_history: List[Dict],
				business_prompt
) -> str:
				"""
				Uses a fast LLM with context to refine a user message into an optimal search query.
				"""
				logger.info(f"Query Refinement: Starting for raw message: '{raw_user_message}'")

				try:
					if not raw_user_message or not raw_user_message.strip():
						return ""

					prompt = f"""
					Your a search intent analysis engine. Your task is to look at a chat understand what the user wants and create a detailed descriptive text of the users search intent for rag search on knowledge base to find the knowledge needed to help the user.
					Your job is vital because we need to match the right knowledge from our knowledge base when we do a vector search with the embedding of the descriptive text you provide.

					**BUSINESS CONTEXT:**
					- Name: {business_name}
					- Bio: {business_bio}
					- Business Prompt: This will help you understand the task of the response AI because you are gettign information for them: {business_prompt}

					**RECENT CONVERSATION:**
					{json.dumps(conversation_history)}

					**USER'S LATEST MESSAGE:**
					"{raw_user_message}"

			**INSTRUCTIONS:**
					1.  **Identify the Core Intent:** What is the user's fundamental need? (e.g., "hungry for a cheap lunch").
					2. 	**What information would I need to help the user?
					3. **Create the best descriptive text to match the information we need from the knowledge base** 
					4. 	**Do not include boiler play eg: The User is looking for, The customer want. Assume you are giving an answer to, what should I search for to answer this customer? What information do I need to answer this query?**

					**Your Descriptive Text:**
					"""
					# Use the fast, non-thinking text generation.
					refined_query = gemini_service.generate_text(prompt)
					if not refined_query or not refined_query.strip():
						logger.warning("Query Refinement: LLM returned an empty query. Falling back to original message.")
						return raw_user_message
					logger.info(f"Query Refinement: Refined query is: '{refined_query.strip()}'")
					return refined_query.strip()

				except Exception as e:
					logger.info(f"Query Service failed: {e}")
					return raw_user_message