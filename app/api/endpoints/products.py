# app/api/endpoints/products.py
import logging
from uuid import UUID
from fastapi import APIRouter, HTTPException, status, Path
from ... import db
from ...api import schemas
# Import our new, powerful services
from ...services import openai_service, product_service, tagging_service, menu_ingestion_service


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/tenants/{tenant_id}/products",
    tags=["Products"]
)

@router.post(
    		"/",
    response_model=schemas.ProductRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a product with AI-driven description and tagging"
)
def create_product( # Removed async as supabase-py v1 is sync
    product_data: schemas.ProductCreate,
    tenant_id: UUID = Path(..., description="The UUID of the tenant this product belongs to")
):
    """
    Creates a new product using the intelligent workflow:
    1.  Generates a rich, synthetic description.
    2.  Generates a vector embedding from the synthetic description.
    3.  Uses AI to suggest and reconcile a de-duplicated list of tags.
    4.  Creates the product and its tag associations in the database.
    """
    logger.info(f"API: Received request to add product '{product_data.product_name}'")
    
    logger.info(f"--- PRODUCT CREATION WORKFLOW STARTED for '{product_data.product_name}' ---")


    try:
        # Step 1: AI Enrichment
        logger.info("[STEP 1/5] Generating synthetic description with Gemini...")

        synthetic_desc = product_service.generate_synthetic_description(
            product_data.product_name,
            product_data.description
        )
        logger.info(f"[STEP 1/5] Synthetic description generated: '{synthetic_desc[:100]}...'")

        # Step 2: Embedding
        logger.info("[STEP 2/5] Generating product embedding with OpenAI...")
        product_embedding = openai_service.get_embedding(synthetic_desc)
        logger.info("[STEP 2/5] Product embedding created successfully.")

        # Step 3: Insert Product (without tags first)
        logger.info("[STEP 3/5] Inserting product into database...")
        product_dict = product_data.model_dump()
        product_dict['tenant_id'] = str(tenant_id)
        product_dict['description_embedding'] = product_embedding
        # Add a new column for the generated description to 'products' table:
        # ALTER TABLE products ADD COLUMN generated_description TEXT;
        product_dict['generated_description'] = synthetic_desc

        product_res = db.supabase.table('products').insert(product_dict).execute()
        if not product_res.data:
            raise HTTPException(status_code=400, detail="DB Error: Failed to create product.")
        
        new_product = product_res.data[0]
        new_product_id = new_product['id']
        logger.info(f"DB: Product '{new_product_id}' created.")
        logger.info(f"[STEP 3/5] Product '{new_product_id}' created successfully in DB.")

        # Step 4: Intelligent Tagging
        final_tag_ids = tagging_service.suggest_and_reconcile_tags(
            tenant_id,
            new_product['product_name'],
            synthetic_desc,
            product_embedding,
        )

        # Step 5: Associate Tags
        if final_tag_ids:
            associations = [{"product_id": new_product_id, "tag_id": str(tag_id)} for tag_id in final_tag_ids]
            db.supabase.table('product_tag_associations').insert(associations).execute()
            logger.info(f"DB: Associated {len(final_tag_ids)} tags with product '{new_product_id}'.")
        
        return new_product

    except Exception as e:
        logger.error(f"API Error adding product: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error.")
    
@router.post(
    "/batch-from-text",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create multiple products from a block of menu text"
)
def create_products_from_text(
    request_data: schemas.MenuIngestRequest, # New schema needed
    tenant_id: UUID = Path(..., description="The UUID of the tenant")
):
    """
    Accepts a large block of unstructured text (e.g., a copied-and-pasted menu),
    and initiates a background task to parse, create, and tag products.
    """
    # For a long-running process like this, we should ideally use a background task.
    # For the MVP, we can run it synchronously and let the client wait.
    # In a future sprint, we would queue this in a `batch_tasks` queue.
    
    logger.info(f"API: Received request to ingest menu text for tenant {tenant_id}.")
    
    try:
        result = menu_ingestion_service.ingest_menu_from_text(
            tenant_id=tenant_id,
            menu_text=request_data.menu_text
        )
        return result
    except Exception as e:
        logger.error(f"API Error ingesting menu text: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process menu text.")