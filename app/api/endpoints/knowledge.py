# app/api/endpoints/knowledge.py
import logging
from uuid import UUID
from fastapi import APIRouter, HTTPException, status, Path
from ...api import schemas # We'll need to add the new schema here
from ...services import knowledge_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/businesses/{business_id}/knowledge", tags=["Knowledge Base"])

@router.post("/text", status_code=status.HTTP_201_CREATED, summary="Ingest raw text into the knowledge base")
def add_text_knowledge(
    request_data: schemas.KnowledgeIngestRequest, # The new Pydantic schema
    business_id: UUID = Path(..., description="The UUID of the business")
):
    try:
        chunk_count = knowledge_service.ingest_text_knowledge(
            business_id=business_id,
            text_content=request_data.text_content,
            source_name=request_data.source_name
        )
        return {"message": "Knowledge ingested successfully.", "chunks_created": chunk_count}
    except Exception as e:
        logger.error(f"API Error ingesting knowledge for business {business_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to ingest knowledge.")