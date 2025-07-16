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
        business_phone_id = value['metadata']['phone_number_id']
        contact = value['contacts'][0]
        user_phone, user_name = contact['wa_id'], contact['profile']['name']
        user_message = value['messages'][0]['text']['body']
    except (KeyError, IndexError) as e:
        raise ValueError(f"Could not parse required fields from event payload. Error: {e}")

    # 2. Identify Business & Customer
    business = _get_business(business_phone_id)
    if not business: raise ValueError(f"No business found with phone_number_id {business_phone_id}")
    
    customer = _find_or_create_customer(business['id'], user_phone, user_name)

    # 3. Use Gemini to infer tags
    inferred_tags = _get_inferred_tags(business['id'], user_message)
    if not inferred_tags:
        logger.info("No tags inferred. Ending profiling workflow.")
        return

    # 4. Update the customer's profile graph
    _update_customer_interest_scores(customer['id'], inferred_tags)
    logger.info("--- Profile Analysis Workflow COMPLETED ---")

def _get_business(phone_number_id: str) -> dict | None:
    logger.info(f"PROFILING: Fetching business with phone_id {phone_number_id}")
    res = supabase.table('businesses').select('id').eq('whatsapp_phone_number_id', phone_number_id).single().execute()
    return res.data

def _find_or_create_customer(business_id: UUID, phone_number: str, name: str) -> dict:
    logger.info(f"PROFILING: Finding or creating customer for phone {phone_number}")
    res = supabase.table('customers').select('*').eq('business_id', business_id).eq('phone_number', phone_number).maybe_single().execute()
    
    if res and res.data:
        logger.info(f"PROFILING: Found existing customer {res.data['id']}")
        return res.data
    else:
        logger.info("PROFILING: New customer detected. Creating record.")
        new_customer_res = supabase.table('customers').insert({
            "business_id": str(business_id), "phone_number": phone_number, "customer_name": name
        }).execute()
        return new_customer_res.data[0]

def _get_inferred_tags(business_id: UUID, message: str) -> list[str]:
    logger.info("PROFILING: Inferring tags with Gemini...")
    tags_res = supabase.table('product_tags').select('tag_name').eq('business_id', business_id).execute()
    tags_context = json.dumps([t['tag_name'] for t in tags_res.data])

    prompt = f"""You are a customer analyst...
    **Available Tags:** {tags_context}
    **Customer's Message:** "{message}"
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

def _update_customer_interest_scores(customer_id: UUID, tag_names: list[str]):
    logger.info(f"PROFILING: Updating interest scores for customer {customer_id} with tags: {tag_names}")
    
    # Use the robust DB function to handle the upsert logic
    supabase.rpc('increment_interest_scores', {
        'p_customer_id': str(customer_id), 'p_tag_names': tag_names
    }).execute()
    logger.info("PROFILING: Successfully called DB function to update scores.")