# app/services/gemini_service.py
import logging
from google import genai
from google.genai import types
from ..config import Config
from pydantic import BaseModel
from typing import Type, TypeVar

logger = logging.getLogger(__name__)

# --- Generic Type Setup ---
# Create a TypeVar that is constrained to be a subclass of Pydantic's BaseModel.
# This means only Pydantic models can be used with this generic type.
T = TypeVar('T', bound=BaseModel)


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
    

def think_and_generate_json(prompt: str, response_schema: Type[T]) -> T | None:
    """
    Generates a response from Gemini, constrained to a specific Pydantic schema.
    Returns the parsed dictionary on success.
    """
    if not client:
        logger.error("Gemini client is not available.")
        return None
    try:
        # Define the generation configuration with the schema
        generation_config = {
            "response_mime_type": "application/json",
            "response_schema": response_schema,
        }
        
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            config={
                "response_mime_type": "application/json",
                "response_schema": response_schema,
												},
            contents=prompt
        )
        
        logger.info(f"Response: {response}")
        
        # THE FIX: The library provides a direct '.parsed' attribute
        # which holds the validated Pydantic object. We just need to
        # convert it back to a dictionary for the rest of our app to use.
        if not response or not hasattr(response, 'parsed') or not response.parsed:
            logger.warning("Gemini schema mode returned an empty or un-parsable response.")
            # Log the raw text for debugging if it exists
            if response and response.text:
                logger.warning(f"Raw text from Gemini: {response.text}")
            return None
            
        # Explicitly convert the google.protobuf.Struct object
        # into a standard Python dictionary before unpacking it.
        parsed_dict = dict(response.parsed)
        
        # Now, instantiate our Pydantic model with the clean dictionary.
        validated_model_instance = response_schema(**parsed_dict)
        
        return validated_model_instance


    except Exception as e:
        logger.error(f"Error generating Gemini JSON response with schema: {e}", exc_info=True)
        return None