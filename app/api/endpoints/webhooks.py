import logging
from fastapi import APIRouter, HTTPException, status, Request, Response, Query, BackgroundTasks
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

# @router.post("/whatsapp", status_code=status.HTTP_202_ACCEPTED, summary="Handle Incoming WhatsApp Events")
# async def handle_whatsapp_events(request: Request):
#     """Receives events from Meta and queues them in the central dispatcher."""
#     data = await request.json()
#     logger.info("--- INCOMING WHATSAPP PAYLOAD ---")
				
#     try:
#         # We only care about user-sent text messages for now
#         if (data.get("object") == "whatsapp_business_account" and
#             data["entry"][0]["changes"][0]["value"]["messages"][0]["type"] == "text"):
												
#             event_payload = {"event_type": "new_inbound_message", "payload": data}
#             db.supabase.table('event_dispatcher').insert(event_payload).execute()
#             logger.info(f"Event '{event_payload['event_type']}' queued in dispatcher.")
#     except (KeyError, IndexError):
#         logger.info("Received a valid but non-message event (e.g., status update). Ignoring.")
#     except Exception as e:
#         logger.error(f"Error queueing webhook payload: {e}", exc_info=True)
				
#     # Always return a 202 to Meta
#     return {"status": "event received"}

# # In app/api/endpoints/webhooks.py

@router.post("/whatsapp", status_code=status.HTTP_200_OK, summary="Handle Incoming WhatsApp Events")
async def handle_whatsapp_events(request: Request, background_tasks: BackgroundTasks):
				"""
				Receives events from Meta, immediately queues feedback and processing tasks,
				and returns 200 OK.
				"""
				data = await request.json()
				
				logger.info(f"Message received: {data}")
				
				# We use FastAPI's BackgroundTasks to ensure we respond to Meta instantly.
				background_tasks.add_task(queue_events, data)
				
				return {"status": "ok"}

def queue_events(data: dict):
				"""
				This function is run in the background. It validates the payload and
				queues all necessary events.
				"""
				logger.info("--- BACKGROUND TASK: Queuing events from webhook ---")
				
				try:
								# We only process user-sent text messages
								if (data.get("object") == "whatsapp_business_account" and
																data["entry"][0]["changes"][0]["value"].get("messages")):
												
												value = data['entry'][0]['changes'][0]['value']
												message_id = value['messages'][0]['id']
												tenant_phone_id = value['metadata']['phone_number_id']

												# Find our internal tenant_id from the phone_number_id
												tenant_res = db.supabase.table('businesses').select('id').eq('whatsapp_phone_number_id', tenant_phone_id).single().execute()
												if not tenant_res.data:
																logger.error(f"Webhook received for unknown tenant phone ID: {tenant_phone_id}. Ignoring.")
																return
												
												tenant_id = tenant_res.data['id']
												
												# --- Queue BOTH events ---
												
												# Event A: The immediate read receipt
												read_receipt_event = {
																"event_type": "send_read_receipt",
																"payload": {"tenant_id": str(tenant_id), "message_id": message_id}
												}
												db.supabase.table('event_dispatcher').insert(read_receipt_event).execute()
												logger.info("Queued 'send_read_receipt' event.")

												# Event B: The main processing task
												processing_event = {
																"event_type": "new_inbound_message",
																"payload": data
												}
												db.supabase.table('event_dispatcher').insert(processing_event).execute()
												logger.info("Queued 'new_inbound_message' event.")
												
				except Exception as e:
								logger.error(f"Background task failed to queue events: {e}", exc_info=True)