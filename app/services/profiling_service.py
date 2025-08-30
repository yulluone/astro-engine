# app/services/profiling_service.py
import logging
import json
from uuid import UUID
from ..db import supabase
from . import gemini_service

logger = logging.getLogger(__name__)

def run_profiling_from_event(event_payload: dict):
    """The main entrypoint for the profiling service, triggered by a worker."""
    logger.info("--- Starting Profile Analysis Workflow ---")
    
    # 1. Deconstruct payload
    try:
        value = event_payload['entry'][0]['changes'][0]['value']
        tenant_phone_id = value['metadata']['phone_number_id']
        contact = value['contacts'][0]
        user_phone, user_name = contact['wa_id'], contact['profile']['name']
        user_message = value['messages'][0]['text']['body']
    except (KeyError, IndexError) as e:
        raise ValueError(f"Could not parse required fields from event payload. Error: {e}")

    # 2. Identify tenant & User
    tenant = _get_tenant(tenant_phone_id)
    if not tenant: raise ValueError(f"No tenant found with phone_number_id {tenant_phone_id}")
    
    user = _find_or_create_user(tenant['id'], user_phone, user_name)

    # 3. Use Gemini to infer tags
    inferred_tags = _get_inferred_tags(tenant['id'], user_message)
    if not inferred_tags:
        logger.info("No tags inferred. Ending profiling workflow.")
        return

    # 4. Update the user's profile graph
    _update_user_interest_scores(user['id'], inferred_tags)
    logger.info("--- Profile Analysis Workflow COMPLETED ---")

def _get_tenant(phone_number_id: str) -> dict | None:
    logger.info(f"PROFILING: Fetching tenant with phone_id {phone_number_id}")
    res = supabase.table('businesses').select('id').eq('whatsapp_phone_number_id', phone_number_id).single().execute()
    return res.data

def _find_or_create_user(tenant_id: UUID, phone_number: str, name: str) -> dict:
    logger.info(f"PROFILING: Finding or creating user for phone {phone_number}")
    res = supabase.table('users').select('*').eq('tenant_id', tenant_id).eq('phone_number', phone_number).maybe_single().execute()
    
    if res and res.data:
        logger.info(f"PROFILING: Found existing user {res.data['id']}")
        return res.data
    else:
        logger.info("PROFILING: New user detected. Creating record.")
        new_user_res = supabase.table('users').insert({
            "tenant_id": str(tenant_id), "phone_number": phone_number, "user_name": name
        }).execute()
        return new_user_res.data[0]

def _get_inferred_tags(tenant_id: UUID, message: str) -> list[str]:
    logger.info("PROFILING: Inferring tags with Gemini...")
    tags_res = supabase.table('product_tags').select('tag_name').eq('tenant_id', tenant_id).execute()
    tags_context = json.dumps([t['tag_name'] for t in tags_res.data])

    prompt = f"""You are a user analyst...
    **Available Tags:** {tags_context}
    **User's Message:** "{message}"
    ... (rest of prompt as designed) ...
    """
    response_str = gemini_service.generate_text(prompt) # Use fast model
    if not response_str: return []
    try:
        data = json.loads(response_str.strip().replace("`", ""))
        inferred = data.get('inferred_tags', [])
        logger.info(f"PROFILING: Gemini inferred tags: {inferred}")
        return inferred
    except json.JSONDecodeError:
        return []

def _update_user_interest_scores(user_id: UUID, tag_names: list[str]):
    logger.info(f"PROFILING: Updating interest scores for user {user_id} with tags: {tag_names}")
    
    # Use the robust DB function to handle the upsert logic
    supabase.rpc('increment_interest_scores', {
        'p_user_id': str(user_id), 'p_tag_names': tag_names
    }).execute()
    logger.info("PROFILING: Successfully called DB function to update scores.")