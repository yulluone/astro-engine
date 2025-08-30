# app/services/outbound_service.py

import logging
import httpx
from uuid import UUID
from ..config import Config
from ..db import supabase

logger = logging.getLogger(__name__)

def send_whatsapp_message(tenant_id: UUID, message_payload: dict):
    """
    Sends a pre-formatted payload to the WhatsApp API for a specific tenant.
    This service is "dumb" - it only handles delivery, not content creation.
    """
    to_number = message_payload.get("to")
    logger.info(f"OUTBOUND: Preparing to deliver payload for tenant {tenant_id} to {to_number}.")

    # Step 1: Fetch credentials
    try:
        res = supabase.table('businesses').select('whatsapp_phone_number_id, whatsapp_access_token').eq('id', tenant_id).single().execute()
        credentials = res.data
        if not credentials or not credentials.get('whatsapp_access_token') or not credentials.get('whatsapp_phone_number_id'):
            logger.error(f"OUTBOUND: Failed. Missing credentials for tenant {tenant_id}.")
            return
    except Exception as e:
        logger.error(f"OUTBOUND: Failed to fetch credentials for tenant {tenant_id}. Error: {e}")
        return

    # DEV MODE check
    if Config.DEV_MODE:
        logger.info("--- DEV MODE: SIMULATED WHATSAPP PAYLOAD SEND ---")
        logger.info(f"  tenant ID: {tenant_id}")
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
        logger.info(f"OUTBOUND: Payload delivered successfully for tenant {tenant_id}.")
    except httpx.HTTPStatusError as e:
        logger.error(f"OUTBOUND: HTTP Error delivering payload for tenant {tenant_id}: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        logger.error(f"OUTBOUND: Unexpected error delivering payload for tenant {tenant_id}: {e}", exc_info=True)
        

# In app/services/outbound_service.py

# ... (imports and existing send_whatsapp_message function) ...

def send_read_receipt_and_typing(tenant_id: UUID, message_id: str):
    """
    Marks a message as read and displays a typing indicator to the user.
    This should be called immediately upon receiving a message.
    """
    logger.info(f"OUTBOUND: Sending Read Receipt/Typing Indicator for message {message_id}")

    # Step 1: Fetch credentials (this logic is the same)
    try:
        res = supabase.table('businesses').select('whatsapp_phone_number_id, whatsapp_access_token').eq('id', tenant_id).single().execute()
        credentials = res.data
        if not credentials or not credentials.get('whatsapp_access_token') or not credentials.get('whatsapp_phone_number_id'):
            logger.error(f"OUTBOUND: Failed. Missing credentials for tenant {tenant_id}.")
            return
    except Exception as e:
        logger.error(f"OUTBOUND: Failed to fetch credentials for tenant {tenant_id}. Error: {e}")
        return

    # DEV MODE check
    if Config.DEV_MODE:
        logger.info("--- DEV MODE: SIMULATED READ RECEIPT & TYPING INDICATOR ---")
        logger.info(f"  tenant ID: {tenant_id}")
        logger.info(f"   Message ID: {message_id}")
        logger.info("---------------------------------------------------------")
        return

    # Production Logic
    phone_number_id = credentials['whatsapp_phone_number_id']
    access_token = credentials['whatsapp_access_token']
	
    json_payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
        "typing_indicator": {
            "type": "text"
								}
    }
    
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"
    
    logger.info(f"OUTBOUND: Sending 'read' status for message {message_id}...")
    try:
        with httpx.Client() as client:
            response = client.post(url, headers=headers, json=json_payload)
            response.raise_for_status()
        logger.info(f"OUTBOUND: 'Read' status sent successfully for message {message_id}.")
    except httpx.HTTPStatusError as e:
        logger.error(f"OUTBOUND: HTTP Error sending read receipt: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        logger.error(f"OUTBOUND: Unexpected error sending read receipt: {e}", exc_info=True)