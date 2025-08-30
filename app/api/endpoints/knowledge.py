# app/api/endpoints/knowledge.py
import logging
from uuid import UUID
from fastapi import APIRouter, HTTPException, status, Path
from ...api import schemas # We'll need to add the new schema here
from ...services import knowledge_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tenants/{tenant_id}/knowledge", tags=["Knowledge Base"])

@router.post("/text", status_code=status.HTTP_201_CREATED, summary="Ingest raw text into the knowledge base")
def add_text_knowledge(
    request_data: schemas.KnowledgeIngestRequest, # The new Pydantic schema
    tenant_id: UUID = Path(..., description="The UUID of the tenant")
):
    try:
        chunk_count = knowledge_service.ingest_text_knowledge(
            tenant_id=tenant_id,
            text_content=request_data.text_content,
            source_name=request_data.source_name
        )
        return {"message": "Knowledge ingested successfully.", "chunks_created": chunk_count}
    except Exception as e:
        logger.error(f"API Error ingesting knowledge for tenant {tenant_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to ingest knowledge.")