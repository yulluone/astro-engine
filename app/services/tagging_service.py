# app/services/tagging_service.py (Corrected with Stored Tag Embeddings)

import logging
import json
import numpy as np
from uuid import UUID
from sklearn.metrics.pairwise import cosine_similarity
from ..db import supabase
from . import openai_service, gemini_service
from deprecated import deprecated

logger = logging.getLogger(__name__)

# --- Main Orchestration Function ---
def suggest_and_reconcile_tags(tenant_id: UUID, product_name: str, product_description: str, product_embedding: list[float]) -> list[UUID]:
    """Orchestrates the 3-phase intelligent tagging workflow."""
    
    # Phase 1: Get candidates using pre-calculated embeddings
    candidate_tags = _get_candidate_tags_by_vector(tenant_id, product_embedding)

    # Phase 2: Use AI to review and refine
    refined_tag_names = _get_ai_refined_tags(product_name, product_description, candidate_tags)
    if not refined_tag_names:
        return []

    # Phase 3: Reconcile with DB, creating new tags (with embeddings) as needed
    final_tag_ids = _reconcile_tags_in_db(tenant_id, refined_tag_names)
    return final_tag_ids

# --- Private Helper Functions for Each Phase ---

def _get_candidate_tags_by_vector(tenant_id: UUID, product_embedding: list[float], threshold: float = 0.30, limit: int = 10) -> list[dict]:
    """PHASE 1:  Uses the new DB function for efficient vector search."""
    logger.info("Tagging Phase 1: Using the DB function (match_tags) for search.")
    
    # Call the new RPC function you created earlier.
    tags_res = supabase.rpc('match_tags', {
        'query_embedding': product_embedding,
        'p_tenant_id': str(tenant_id),
        'match_threshold': threshold,
        'match_count': limit
    }).execute()
    
    if not tags_res.data:
        logger.warning("Tagging Phase 1: DB Function (match_tags) returned no results.")
        return []

    # The RPC result only gives us 'content' and 'similarity'. We need the tag ID
    candidate_tags = tags_res.data
    
    logger.info(f"Tagging Phase 1: DB Function returned {len(candidate_tags)} candidates.")
    return candidate_tags


def _get_ai_refined_tags(product_name: str, product_description: str, candidate_tags: list[dict]) -> list[str]:
    """PHASE 2: Uses Gemini to review the candidates and provide a final list of names."""
    # This function's logic remains the same, as it deals with names, not embeddings.
    # It still correctly uses think_and_generate_text.
    logger.info("Tagging Phase 2: Asking AI to review and refine tags.")
    candidate_tag_names = [tag['tag_name'] for tag in candidate_tags]
   
			
    prompt = f"""You are an expert retail product classifier. Your goal is to select the most relevant and concise set of tags for a new product.

    **Product Name:** '{product_name}'
    **Product Description:** '{product_description}'
    **Initial Suggestions (from a vector embedding search):** {candidate_tag_names}

    **Instructions:**
    1.  Review the initial suggestions. Keep the good ones and discard the irrelevant ones.
    2.  Based on the product's name and description, add any other critical tags that are missing. Aim for a final list of 5-7 total tags.
    3.  Return your final selection as a JSON object with one key: "final_tags", which is a list of lowercase strings.

    **JSON Response:**
    """

    # Use thinking for this complex task
    response_str = gemini_service.think_and_generate_text(prompt)
    if not response_str: return []

    try:
        clean_json_str = response_str.strip().replace('```json', '').replace('```', '')
        data = json.loads(clean_json_str)
        tags = data.get("final_tags", [])
        logger.info(f"Tagging Phase 2: AI refined list to: {tags}")
        return tags
    except json.JSONDecodeError:
        logger.error(f"Tagging Phase 2: Failed to decode JSON: {response_str}")
        return []


def _reconcile_tags_in_db(tenant_id: UUID, refined_names: list[str]) -> list[UUID]: # Removed candidate_tags dependency
    """
    PHASE 3 (Hardened): Takes the final list of names from the AI, checks if each one
    exists in the DB, creates it if not, and returns all final UUIDs.
    """
    logger.info(f"Tagging Phase 3: Reconciling {len(refined_names)} final tags with DB.")
    
    # Fetch ALL existing tags for the tenant just once to create a lookup map.
    # This is more efficient than querying the DB inside a loop.
    existing_tags_res = supabase.table('product_tags').select('id, tag_name').eq('tenant_id', tenant_id).execute()
    existing_tags_map = {tag['tag_name']: tag['id'] for tag in (existing_tags_res.data or [])}
    
    final_tag_ids = set()
    
    for name in refined_names:
        name_lower = name.lower()
        
        # 1. Check if the tag already exists in our map
        if name_lower in existing_tags_map:
            final_tag_ids.add(existing_tags_map[name_lower])
            logger.info(f"Tagging Phase 3: Found existing tag '{name_lower}'.")
        else:
            # 2. If it doesn't exist, it's genuinely new. Create it.
            logger.info(f"Tagging Phase 3: Tag '{name_lower}' is new. Generating embedding and creating.")
            try:
                new_tag_embedding = openai_service.get_embedding(name_lower)
                new_tag_data = {
                    "tenant_id": str(tenant_id), 
                    "tag_name": name_lower,
                    "embedding": new_tag_embedding
                }
                new_tag_res = supabase.table('product_tags').insert(new_tag_data).execute()
                
                if new_tag_res.data:
                    new_tag_id = new_tag_res.data[0]['id']
                    final_tag_ids.add(new_tag_id)
                    # Add to our map so we don't try to create it again in this same run
                    existing_tags_map[name_lower] = new_tag_id 
                else:
                    # This could happen if there's a race condition, but we log it.
                    logger.error(f"Tagging Phase 3: Failed to create new tag '{name_lower}'. Supabase error: {new_tag_res}")
            except Exception as e:
                logger.error(f"Tagging Phase 3: Exception while creating new tag '{name_lower}': {e}")

    logger.info("Tagging Phase 3: Reconciliation complete.")
    return list(final_tag_ids)


@deprecated(version="1.0", reason="This function is outdated, use new_function() instead.")
def _get_candidate_tags_by_vector_python_side(tenant_id: UUID, product_embedding: list[float], limit: int = 10) -> list[dict]:
    """
    [DEPRECATED] PHASE 1: Performs a vector search against PRE-STORED tag embeddings.
    This is now much faster as it does not call any external AI services.
    """
    logger.info("Tagging Phase 1: Getting candidate tags via vector search.")
    # NOTE: We need a dedicated Postgres function for this kind of search.
    # Let's assume we create one called 'match_tags'.
    # For now, we'll simulate it, but we MUST create this function in the DB.
    
    # Fetching all tags is inefficient at scale, but works for the MVP.
    # The real solution is a DB function.
    cand = supabase.rpc("match_tags", )
    tags_res = supabase.table('product_tags').select('id, tag_name, embedding').eq('tenant_id', str(tenant_id)).not_.is_('embedding', None).execute()
    
    if not tags_res.data: return []

    existing_tags = tags_res.data
    # We no longer need to call openai_service.get_batch_embeddings here.
    tag_embeddings = [tag['embedding'] for tag in existing_tags]

    similarities = cosine_similarity(np.array([product_embedding]), np.array(tag_embeddings))[0]
    
    top_indices = np.argsort(similarities)[-limit:][::-1]
    
    candidates = [existing_tags[i] for i in top_indices]
    
    logger.info(f"Tagging Phase 1: Found {len(candidates)} candidates.")
    return candidates
