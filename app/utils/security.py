# app/utils/security.py
import hmac
import hashlib
from ..config import Config

def verify_whatsapp_signature(request_body: bytes, signature_header: str) -> bool:
    """
    Verifies the signature of an incoming WhatsApp webhook request.

    :param request_body: The raw bytes of the request body.
    :param signature_header: The value of the 'X-Hub-Signature-256' header.
    :return: True if the signature is valid, False otherwise.
    """
    if not signature_header:
        return False

    # The header is in the format 'sha256=...'. We only need the part after the equals sign.
    try:
        signature_hash = signature_header.split('=')[1]
    except IndexError:
        return False
    
    # Calculate our own signature of the payload using the App Secret
    expected_hash = hmac.new(
        key=Config.VERIFY_TOKEN.encode('utf-8'),
        msg=request_body,
        digestmod=hashlib.sha256
    ).hexdigest()

    # Compare the two signatures in a way that is safe against timing attacks
    return hmac.compare_digest(signature_hash, expected_hash)	