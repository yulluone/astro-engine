import logging
from fastapi import APIRouter, HTTPException, status, Request, Response, Query
from ... import db
from ...config import Config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

@router.get("/whatsapp", summary="Verify WhatsApp Webhook")
def verify_whatsapp_webhook(
    request: Request
):
    """Handles Meta's webhook verification challenge."""
    logger.info("Received GET request for WhatsApp webhook verification.")
    verify_token = request.query_params.get("hub.verify_token")
    
    if verify_token == Config.VERIFY_TOKEN:
        logger.info("Verification token matched.")
        challenge = request.query_params.get("hub.challenge")
        return Response(content=challenge, media_type="text/plain", status_code=200)
    
    logger.warning("Verification token mismatch.")
    raise HTTPException(status_code=403, detail="Invalid verification token.")

@router.post("/whatsapp", status_code=status.HTTP_202_ACCEPTED, summary="Handle Incoming WhatsApp Events")
async def handle_whatsapp_events(request: Request):
    """Receives events from Meta and queues them in the central dispatcher."""
    data = await request.json()
    logger.info("--- INCOMING WHATSAPP PAYLOAD ---")
    
    try:
        # We only care about user-sent text messages for now
        if (data.get("object") == "whatsapp_business_account" and
            data["entry"][0]["changes"][0]["value"]["messages"][0]["type"] == "text"):
            
            event_payload = {"event_type": "new_inbound_message", "payload": data}
            db.supabase.table('event_dispatcher').insert(event_payload).execute()
            logger.info(f"Event '{event_payload['event_type']}' queued in dispatcher.")
    except (KeyError, IndexError):
        logger.info("Received a valid but non-message event (e.g., status update). Ignoring.")
    except Exception as e:
        logger.error(f"Error queueing webhook payload: {e}", exc_info=True)
    
    # Always return a 202 to Meta
    return {"status": "event received"}