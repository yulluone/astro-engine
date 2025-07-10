# app/services/gemini_service.py
import logging
from google import genai
from google.genai import types
from ..config import Config

logger = logging.getLogger(__name__)

# Configure the Gemini client
try:
    client = genai.Client(api_key=Config.GEMINI_API_KEY)
    logger.info("Successfully configured Google Gemini client.")
except Exception as e:
    logger.critical(f"FATAL: Could not configure Gemini client: {e}")
    client = None

def generate_text(prompt: str) -> str | None:
    """Generates a text response for a simple, single-turn prompt."""
    if not client:
        logger.error("Gemini model is not available.")
        return None
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
												contents=prompt,
												config=types.GenerateContentConfig(thinking_config=types.ThinkingConfig(thinking_budget=0)),
								)
        # Add safety checks for the response
        if not response.text:
            logger.warning("Gemini response is empty.")
            return None
        return response.text
    except Exception as e:
        logger.error(f"Error generating Gemini response: {e}")
        return None
    
def think_and_generate_text(prompt: str) -> str | None:
    """Generates a text response for a simple, single-turn prompt."""
    if not client:
        logger.error("Gemini model is not available.")
        return None
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
												contents=prompt,
								)
        # Add safety checks for the response
        if not response.text:
            logger.warning("Gemini response is empty.")
            return None
        return response.text
    except Exception as e:
        logger.error(f"Error generating Gemini response: {e}")
        return None

