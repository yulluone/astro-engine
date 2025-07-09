import logging
from fastapi import APIRouter, HTTPException, status, Path
from uuid import UUID
from ... import db
from ...api import schemas

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/businesses/{business_id}/tags", # Notice the prefix includes the business_id
    tags=["Tags"]
)

@router.post(
    "/",
    response_model=schemas.TagRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new tag for a business"
)
async def create_tag(
    tag_data: schemas.TagCreate,
    business_id: UUID = Path(..., description="The UUID of the business to which the tag belongs")
):
    """
    Creates a new product tag (category) for a specific business.
    Tags must be unique per business.
    """
    try:
        logger.info(f"Attempting to create tag '{tag_data.tag_name}' for business {business_id}")

        tag_dict = tag_data.model_dump()
        # Manually add the business_id from the path to the data we're inserting
        tag_dict['business_id'] = str(business_id) 

        response = db.supabase.table('product_tags').insert(tag_dict).execute()

        # Supabase will automatically enforce the UNIQUE constraint.
        # If the tag already exists for this business, it will return an error.
        if response.data is None:
            logger.error(f"Supabase error creating tag: {response.error.message if response.error else 'Unknown error'}")
            # Check for a unique violation error specifically
            if response.error and '23505' in response.error.code: # 23505 is PostgreSQL's unique_violation code
                 raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Tag '{tag_data.tag_name}' already exists for this business."
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not create tag. Supabase error: {response.error.message if response.error else 'Unknown'}"
            )
        
        created_tag = response.data[0]
        logger.info(f"Successfully created tag with ID: {created_tag['id']}")

        return created_tag

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"An unexpected error occurred while creating tag: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal server error occurred."
        )