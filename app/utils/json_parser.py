import json
import logging

logger = logging.getLogger(__name__)

def safe_json_from_llm(llm_response_text: str, max_retries: int = 1) -> dict | None:
    """A resilient parser for JSON strings from LLMs."""
    for attempt in range(max_retries + 1):
        try:
            # Most common error is markdown ```json ... ```
            clean_text = llm_response_text.strip()
            if clean_text.startswith('```json'):
                clean_text = clean_text[7:]
            if clean_text.endswith('```'):
                clean_text = clean_text[:-3]
            
            return json.loads(clean_text)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON Decode Error (Attempt {attempt + 1}): {e}. Raw text: '{llm_response_text}'")
            if attempt >= max_retries:
                # In a real system, you might make another LLM call here to fix the JSON
                logger.error("All JSON parsing attempts failed.")
                return None