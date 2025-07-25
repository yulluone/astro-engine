# app/api/schemas.py

from pydantic import BaseModel, UUID4, Field, model_validator
from typing import Optional, List
from datetime import datetime
from enum import Enum

# ===================================================================
#                       Business Schemas
# ===================================================================

class BusinessBase(BaseModel):
    business_name: str
    whatsapp_number: str
    whatsapp_phone_number_id: str
    system_prompt: Optional[str] = "You are a helpful assistant."

class BusinessCreate(BusinessBase):
    pass

class BusinessRead(BusinessBase):
    id: UUID4
    created_at: datetime

    class Config:
        from_attributes = True

# ===================================================================
#                         Tag Schemas
# ===================================================================

class TagBase(BaseModel):
    tag_name: str

class TagCreate(TagBase):
    pass

class TagRead(TagBase):
    id: UUID4

    class Config:
        from_attributes = True


# ===================================================================
#                       Product Schemas
# ===================================================================

class ProductBase(BaseModel):
    product_name: str = Field(..., examples=["Chocolate Fudge Cake"])
    description: Optional[str] = Field(None, examples=["A rich, moist chocolate cake with a fudge frosting."])
    list_price: float = Field(..., gt=0, examples=[25.50])
    floor_price: Optional[float] = Field(None, gt=0, examples=[20.00])
    image_url: Optional[str] = None
    is_active: bool = True

class ProductCreate(ProductBase):
    pass

class ProductRead(ProductBase):
    id: UUID4
    business_id: UUID4
    created_at: datetime
    # We can enrich this later to show associated tags.
    # associated_tags: List[TagRead] = [] 

    class Config:
        from_attributes = True


# ===================================================================
#                       Knowledge Schemas
# ===================================================================

class KnowledgeBase(BaseModel):
    content: str
    source_document_name: Optional[str] = None

class KnowledgeCreate(KnowledgeBase):
    pass

class KnowledgeRead(KnowledgeBase):
    id: UUID4
    business_id: UUID4

    class Config:
        from_attributes = True


# ===================================================================
#                      Promotion Schemas
# ===================================================================

class PromotionBase(BaseModel):
    promo_description: str = Field(..., examples=["Weekend 2-for-1 Special on all Cakes!"])
    product_id: Optional[UUID4] = None # Can be tied to a specific product or be general
    discount_percentage: Optional[float] = Field(None, gt=0, le=100) # Percentage > 0 and <= 100
    discount_amount: Optional[float] = Field(None, gt=0) # Amount must be > 0
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    is_active: bool = True

class PromotionCreate(PromotionBase):
    """Schema for creating a promotion, with custom validation."""
    
    @model_validator(mode='after')
    def check_one_discount_field(self) -> 'PromotionCreate':
        """
        Validates that EITHER 'discount_percentage' OR 'discount_amount' is set, but not both or neither.
        """
        if (self.discount_percentage is not None) and (self.discount_amount is not None):
            raise ValueError("Provide either 'discount_percentage' or 'discount_amount', not both.")
        if (self.discount_percentage is None) and (self.discount_amount is None):
            raise ValueError("Either 'discount_percentage' or 'discount_amount' must be provided.")
        return self

class PromotionRead(PromotionBase):
    """Schema for returning promotion data."""
    id: UUID4
    business_id: UUID4

    class Config:
        from_attributes = True
        

# In app/api/schemas.py

# ... (all your other schemas are above this) ...

# ===================================================================
#                LLM Action & Tool Schemas
# ===================================================================

class ToolCallArgument(BaseModel):
    # Using a generic dict for now, can be made more specific later
    summary_of_new_info: Optional[str] = None
    product_name: Optional[str] = None
    category: Optional[str] = None
    reason: Optional[str] = None

# Step 1: Define the Enum of all valid tool names
class ToolName(str, Enum):
    QUEUE_FOR_PROFILING = "queue_for_profiling"
    REQUEST_HUMAN_INTERVENTION = "request_human_intervention"
    LOOKUP_PRODUCT_INFO = "lookup_product_info"

class ToolCall(BaseModel):
    name: ToolName
    arguments: ToolCallArgument

class ActionPlan(BaseModel):
    """
    The structured response we expect from the main reasoning LLM call.
    This schema is passed to Gemini to constrain its output.
    - response_text: The conversational reply to send to the user.	
    - tool_calls: A list of allowed background actions to trigger.	
    """
    response_text: str = Field(..., description="The conversational reply to send to the user.")
    tool_calls: List[ToolCall] = Field(default=[], description="A list of background actions to trigger.")
    

class KnowledgeIngestRequest(BaseModel):
    text_content: str
    source_name: str # e.g., "From Website About Page"
    
class MenuIngestRequest(BaseModel):
    menu_text: str
