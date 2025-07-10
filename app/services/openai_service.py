# app/services/openai_service.py

import logging
from openai import OpenAI
from ..config import Config

logger = logging.getLogger(__name__)

try:
    client = OpenAI(api_key=Config.OPENAI_API_KEY)
    logger.info("OpenAI client initialized successfully.")
except Exception as e:
    logger.critical(f"Failed to initialize OpenAI client: {e}")
    client = None

def get_embedding(text: str, model="text-embedding-3-small") -> list[float]:
    """Generates a single embedding for a given text string."""
    if not client:
        raise ConnectionError("OpenAI client is not initialized.")
    
    try:
        # Replace newlines with spaces for better embedding performance
        text = text.replace("\n", " ")
        response = client.embeddings.create(input=[text], model=model)
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"OpenAI embedding failed for text: '{text[:50]}...'. Error: {e}")
        # Re-raise the exception to be handled by the calling endpoint
        raise e

def get_batch_embeddings(texts: list[str], model="text-embedding-3-small") -> list[list[float]]:
    """Generates embeddings for a list of text strings in a single API call."""
    if not client:
        raise ConnectionError("OpenAI client is not initialized.")
        
    try:
        # It's good practice to also clean up newlines here
        cleaned_texts = [text.replace("\n", " ") for text in texts]
        response = client.embeddings.create(input=cleaned_texts, model=model)
        return [emb.embedding for emb in response.data]
    except Exception as e:
        logger.error(f"OpenAI batch embedding failed. Error: {e}")
        raise e