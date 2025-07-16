import logging
from fastapi import APIRouter, HTTPException, status
from ... import db  # Imports the initialized Supabase client
from ...api import schemas # Imports our Pydantic models

# Initialize a logger for this module
logger = logging.getLogger(__name__)

# Create an APIRouter instance. We'll include this in our main app.
router = APIRouter(
    prefix="/businesses",  # All routes in this file will start with /businesses
    tags=["Businesses"]   # Group these endpoints in the API docs
)

@router.post(
    "/",
    response_model=schemas.BusinessRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new business"
)
async def create_business(business_data: schemas.BusinessCreate):
    """
    Registers a new business on the platform.

    - **business_name**: Name of the business.
    - **whatsapp_number**: The business's WhatsApp phone number.
    - **whatsapp_phone_number_id**: The ID from the Meta for Developers platform.
    - **system_prompt**: The base personality prompt for the AI assistant.
    """
    try:	
        logger.info(f"Attempting to create business: {business_data.business_name}")

        # The .dict() method is deprecated, use .model_dump()
        # Pydantic V2 uses model_dump(), V1 uses dict()
        business_dict = business_data.model_dump()

        # Insert the data into the 'businesses' table
        response = db.supabase.table('businesses').insert(business_dict).execute()

        # Check for errors from Supabase
        if response.data is None:
            logger.error(f"Supabase error creating business: {response.error.message if response.error else 'Unknown error'}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not create business. Supabase error: {response.error.message if response.error else 'Unknown'}"
            )
        
        created_business = response.data[0]
        logger.info(f"Successfully created business with ID: {created_business['id']}")

        # Pydantic will automatically validate that the returned data
        # matches the BusinessRead schema.
        return created_business

    except HTTPException as http_exc:
        # Re-raise HTTPException to be handled by FastAPI
        raise http_exc
    except Exception as e:
        logger.error(f"An unexpected error occurred while creating business: {e}", exc_info=True)
        # For any other unexpected errors, return a generic 500 error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal server error occurred."
        )