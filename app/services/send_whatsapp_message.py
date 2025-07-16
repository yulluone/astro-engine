# in the service that sends messages
from ..config import Config
import logging

logger = logging.getLogger()

def send_whatsapp_message(to_number, message_text):
    if Config.DEV_MODE:
        logger.info("--- DEV MODE: SIMULATED WHATSAPP SEND ---")
        logger.info(f"TO: {to_number}")
        logger.info(f"BODY: {message_text}")
        logger.info("------------------------------------------")
        return
    
    # ... the real requests.post() logic goes here ...