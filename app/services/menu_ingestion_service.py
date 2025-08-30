# app/services/menu_ingestion_service.py
import logging
from uuid import UUID
from typing import List # FIX #1: Import List for type hinting
from pydantic import BaseModel # Import BaseModel for defining the schema

from ..api.schemas import ProductCreate # We'll use this to validate the LLM's output
from . import gemini_service, product_service, openai_service, tagging_service
from ..db import supabase

logger = logging.getLogger(__name__)

def ingest_menu_from_text(tenant_id: UUID, menu_text: str) -> dict:
    """
    Orchestrates the process of parsing menu text and creating products in batch.
    """
    logger.info(f"MENU INGESTION: Starting for tenant {tenant_id}.")
    
    # Step 1: Use LLM to parse the unstructured text into structured data
    parsed_products = _parse_menu_with_ai(menu_text)
    
    # The _parse_menu_with_ai function now returns a list of ProductCreate objects or None
    if not parsed_products:
        return {"message": "AI failed to identify any products in the provided text.", "total_identified": 0, "successfully_created": 0, "failed": 0}

    logger.info(f"MENU INGESTION: AI identified {len(parsed_products)} potential products.")
    
    success_count = 0
    failure_count = 0

    # Step 2: Iterate and create each product using our existing single-product workflow
    for product_data in parsed_products:
        try:
            # The data is already a validated Pydantic model from the parser
            _create_single_product(tenant_id, product_data)
            success_count += 1
        except Exception as e:
            logger.error(f"MENU INGESTION: Failed to create product '{product_data.product_name}'. Error: {e}")
            failure_count += 1
    
    logger.info(f"MENU INGESTION: Process complete. Success: {success_count}, Failed: {failure_count}.")
    return {"message": "Batch product ingestion complete.", "total_identified": len(parsed_products), "successfully_created": success_count, "failed": failure_count}


def _parse_menu_with_ai(menu_text: str) -> List[ProductCreate] | None:
    """Uses Gemini to parse raw menu text into a list of ProductCreate objects."""
    
    # Define the Pydantic model for the expected list structure INSIDE the function
    # This keeps it scoped to where it's used.
    class MenuProductList(BaseModel):
        products: List[ProductCreate]

    prompt = f"""You are an expert menu data entry system. Your task is to read the following unstructured menu text and convert it into a structured list of products. Ignore all non-product text like headings, addresses, or opening hours. For each menu item, extract its name, a brief description if available, and its price.

    **Unstructured Menu Text:**
    {menu_text}

    **Your Task:**
    Strictly follow the provided JSON schema to structure your output. The `products` key must contain a list of all identified menu items.

    """

    # We use the schema-constrained JSON generation
    # The 'response_schema' argument expects the Pydantic class itself
    parsed_model_instance = gemini_service.think_and_generate_json(prompt, MenuProductList)
    
    # FIX #2 & #3: Check for the object and access its attribute with dot notation
    if not parsed_model_instance or not hasattr(parsed_model_instance, 'products'):
        logger.error("MENU INGESTION: AI failed to return a valid object with a 'products' attribute.")
        return None
        
    return parsed_model_instance.products


def _create_single_product(tenant_id: UUID, product_data: ProductCreate):
    """
    This is our robust, single-product creation workflow, now as a helper function.
    """
    logger.info(f"Creating product: {product_data.product_name}")
    
    # 1. AI Enrichment
    synthetic_desc = product_service.generate_synthetic_description(product_data.product_name, product_data.description)
    
    # 2. Embedding
    product_embedding = openai_service.get_embedding(synthetic_desc)
    
    # 3. Insert Product
    product_dict = product_data.model_dump()
    product_dict.update({
        'tenant_id': str(tenant_id),
        'description_embedding': product_embedding,
        'generated_description': synthetic_desc
    })
    product_res = supabase.table('products').insert(product_dict).execute()
    new_product_id = product_res.data[0]['id']
    
    # 4. Intelligent Tagging
    final_tag_ids = tagging_service.suggest_and_reconcile_tags(
        tenant_id, product_data.product_name, synthetic_desc, product_embedding
    )
    
    # 5. Associate Tags
    if final_tag_ids:
        associations = [{"product_id": new_product_id, "tag_id": str(tag_id)} for tag_id in final_tag_ids]
        supabase.table('product_tag_associations').insert(associations).execute()