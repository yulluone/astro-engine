# app/services/outbound_service.py

import logging
import httpx
from uuid import UUID
from ..config import Config
from ..db import supabase

logger = logging.getLogger(__name__)

def send_whatsapp_message(business_id: UUID, message_payload: dict):
    """
    Sends a pre-formatted payload to the WhatsApp API for a specific business.
    This service is "dumb" - it only handles delivery, not content creation.
    """
    to_number = message_payload.get("to")
    logger.info(f"OUTBOUND: Preparing to deliver payload for business {business_id} to {to_number}.")

    # Step 1: Fetch credentials
    try:
        res = supabase.table('businesses').select('whatsapp_phone_number_id, whatsapp_access_token').eq('id', business_id).single().execute()
        credentials = res.data
        if not credentials or not credentials.get('whatsapp_access_token') or not credentials.get('whatsapp_phone_number_id'):
            logger.error(f"OUTBOUND: Failed. Missing credentials for business {business_id}.")
            return
    except Exception as e:
        logger.error(f"OUTBOUND: Failed to fetch credentials for business {business_id}. Error: {e}")
        return

    # DEV MODE check
    if Config.DEV_MODE:
        logger.info("--- DEV MODE: SIMULATED WHATSAPP PAYLOAD SEND ---")
        logger.info(f"  Business ID: {business_id}")
        logger.info(f"   Phone ID: {credentials['whatsapp_phone_number_id']}")
        logger.info(f"      PAYLOAD: {message_payload}")
        logger.info("---------------------------------------------")
        return

    # Production Logic
    phone_number_id = credentials['whatsapp_phone_number_id']
    access_token = credentials['whatsapp_access_token']
    
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"
    
    logger.info(f"OUTBOUND: Delivering production payload to {to_number}...")
    try:
        with httpx.Client() as client:
            # THE FIX: We now send the `message_payload` directly as the JSON body.
            response = client.post(url, headers=headers, json=message_payload)
            response.raise_for_status()
        logger.info(f"OUTBOUND: Payload delivered successfully for business {business_id}.")
    except httpx.HTTPStatusError as e:
        logger.error(f"OUTBOUND: HTTP Error delivering payload for business {business_id}: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        logger.error(f"OUTBOUND: Unexpected error delivering payload for business {business_id}: {e}", exc_info=True)