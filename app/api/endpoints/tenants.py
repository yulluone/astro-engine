import logging
from fastapi import APIRouter, HTTPException, status
from ... import db  # Imports the initialized Supabase client
from .. import schemas # Imports our Pydantic models

# Initialize a logger for this module
logger = logging.getLogger(__name__)

# Create an APIRouter instance. We'll include this in our main app.
router = APIRouter(
    prefix="/tenants",  # All routes in this file will start with /tenants
    tags=["tenants"]   # Group these endpoints in the API docs
)

@router.post(
    "/",
    response_model=schemas.tenantRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new tenant"
)
async def create_tenant(tenant_data: schemas.tenantCreate):
    """
    Registers a new tenant on the platform.

    - **tenant_name**: Name of the tenant.
    - **whatsapp_number**: The tenant's WhatsApp phone number.
    - **whatsapp_phone_number_id**: The ID from the Meta for Developers platform.
    - **system_prompt**: The base personality prompt for the AI assistant.
    """
    try:	
        logger.info(f"Attempting to create tenant: {tenant_data.tenant_name}")

        # The .dict() method is deprecated, use .model_dump()
        # Pydantic V2 uses model_dump(), V1 uses dict()
        tenant_dict = tenant_data.model_dump()

        # Insert the data into the 'businesses' table
        response = db.supabase.table('businesses').insert(tenant_dict).execute()

        # Check for errors from Supabase
        if response.data is None:
            logger.error(f"Supabase error creating tenant: {response.error.message if response.error else 'Unknown error'}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not create tenant. Supabase error: {response.error.message if response.error else 'Unknown'}"
            )
        
        created_tenant = response.data[0]
        logger.info(f"Successfully created tenant with ID: {created_tenant['id']}")

        # Pydantic will automatically validate that the returned data
        # matches the tenantRead schema.
        return created_tenant

    except HTTPException as http_exc:
        # Re-raise HTTPException to be handled by FastAPI
        raise http_exc
    except Exception as e:
        logger.error(f"An unexpected error occurred while creating tenant: {e}", exc_info=True)
        # For any other unexpected errors, return a generic 500 error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal server error occurred."
        )