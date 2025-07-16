# app/services/knowledge_service.py
import logging
import json
from uuid import UUID
from ..db import supabase
from ..utils.json_parser import safe_json_from_llm
from . import openai_service, gemini_service

logger = logging.getLogger(__name__)

# The old text_splitter is no longer needed.

def ingest_text_knowledge(business_id: UUID, text_content: str, source_name: str) -> int:
    """
    Takes a large block of text, uses an AI to create semantic chunks,
    generates embeddings for them, and stores them in the database.
    """
    logger.info(f"KNOWLEDGE: Starting AI-powered ingestion for source '{source_name}'.")

    # 1. AI Semantic Chunking
    chunks = _get_ai_semantic_chunks(text_content)
    if not chunks:
        logger.error("KNOWLEDGE: AI failed to generate any chunks. Aborting ingestion.")
        return 0
    
    logger.info(f"KNOWLEDGE: AI generated {len(chunks)} semantic chunks.")

    # 2. Get batch embeddings
    logger.info("KNOWLEDGE: Generating batch embeddings for all chunks...")
    try:
        embeddings = openai_service.get_batch_embeddings(chunks)
    except Exception as e:
        raise ValueError("Embedding generation failed.") from e
    
    # 3. Prepare and insert records
    records_to_insert = [
        {
            "business_id": str(business_id),
            "content": chunk,
            "embedding": embedding,
            "source_document_name": source_name
        }
        for chunk, embedding in zip(chunks, embeddings)
    ]

    try:
        supabase.table('knowledge').insert(records_to_insert).execute()
        logger.info(f"KNOWLEDGE: Successfully inserted {len(records_to_insert)} documents.")
        return len(records_to_insert)
    except Exception as e:
        logger.error(f"KNOWLEDGE: Database insert failed. Error: {e}", exc_info=True)
        raise

def _get_ai_semantic_chunks(raw_text: str) -> list[str]:
    """Uses Gemini to break a large text into meaningful, self-contained chunks."""
    
    prompt = f"""You are an expert data pre-processor. Your task is to read the following document and break it down into a series of self-contained, topically-focused chunks of information. Each chunk should represent a single, complete thought or answer to a potential question.

    **Document Text:**
    {raw_text}

    **Instructions:**
    1.  Identify distinct topics or questions a user might ask (e.g., Opening Hours, Delivery Policy, Company History).
    2.  For each topic, create a concise paragraph that fully answers a potential question about it.
    3.  Return the result as a JSON object with one key: "knowledge_chunks", which is a list of these text strings.
    
    **JSON Response:**
    """

    # We can use the simple text generation here, but need to parse its JSON output
    response_str = gemini_service.generate_text(prompt)
    if not response_str:
        return []
        
    parsed_json = safe_json_from_llm(response_str)
    if not parsed_json or 'knowledge_chunks' not in parsed_json:
        logger.error(f"KNOWLEDGE: AI chunker failed to return valid JSON with 'knowledge_chunks' key. Raw response: {response_str}")
        return []

    return parsed_json['knowledge_chunks']