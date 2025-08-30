# app/api/endpoints/tags.py
import logging
from uuid import UUID
from fastapi import APIRouter, HTTPException, status, Path
from ... import db
from ...api import schemas
from ...services import openai_service # We need the embedding service here

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/tenants/{tenant_id}/tags",
    tags=["Tags"]
)

@router.post("/", response_model=schemas.TagRead, status_code=status.HTTP_201_CREATED, summary="Create a new tag with its embedding")
def create_tag(
    tag_data: schemas.TagCreate,
    tenant_id: UUID = Path(..., description="The UUID of the tenant this tag belongs to")
):
    """
    Creates a new product tag and pre-calculates its vector embedding for future searches.
    """
    try:
        tag_name_lower = tag_data.tag_name.lower()
        logger.info(f"Attempting to create tag '{tag_name_lower}' for tenant {tenant_id}")

        # Generate embedding for the new tag name
        tag_embedding = openai_service.get_embedding(tag_name_lower)

        tag_dict = {
            "tenant_id": str(tenant_id),
            "tag_name": tag_name_lower,
            "embedding": tag_embedding # Store the pre-calculated embedding
        }

        response = db.supabase.table('product_tags').insert(tag_dict).execute()

        if response.data is None:
            # Check for unique violation
            if response.error and '23505' in response.error.code:
                 raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Tag '{tag_name_lower}' already exists for this tenant."
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not create tag. Supabase error: {response.error.message if response.error else 'Unknown'}"
            )
        
        created_tag = response.data[0]
        logger.info(f"Successfully created tag '{created_tag['tag_name']}' with ID: {created_tag['id']}")

        return created_tag

    except Exception as e:
        logger.error(f"An unexpected error occurred while creating tag: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal server error occurred.")