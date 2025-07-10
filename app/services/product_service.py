# app/services/product_service.py
import logging
from . import gemini_service

logger = logging.getLogger(__name__)

def generate_synthetic_description(product_name: str, user_description: str | None) -> str:
    """Generates a rich, synthetic description for a product."""
    
    prompt = f"""You are a creative copywriter for a retail store. 
    Given the following product information, write a rich, one-paragraph descriptive text that would be useful for a recommendation system.
    Include key attributes, potential use cases, and associated concepts. Do not use markdown.

    Product Name: '{product_name}'
    User's Provided Description: '{user_description or 'None provided'}'

    Rich Description:
    """
    
    synthetic_description = gemini_service.generate_text(prompt)
    
    if not synthetic_description:
        logger.warning(f"Gemini failed to generate a synthetic description for '{product_name}'. Falling back to original description.")
        # Fallback to a combination of name and user description if AI fails
        return f"{product_name}. {user_description or ''}".strip()
        
    logger.info(f"Generated synthetic description for '{product_name}'")
    return synthetic_description.strip()