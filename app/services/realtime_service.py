# app/services/realtime_service.py
import logging
import json
from uuid import UUID
from typing import Optional, Dict, Any, List

# Import Pydantic for internal data validation
from pydantic import BaseModel, Field

from ..api.schemas import ActionPlan

from ..db import supabase
from ..config import Config
from . import gemini_service, openai_service
from ..utils.json_parser import safe_json_from_llm


logger = logging.getLogger(__name__)

# This will eventually come from a config or DB
CAPABILITY_PROMPT = """
- You *can* answer questions based on the business's knowledge base (hours, locations).
- You *can* look up product information, prices, and promotions.
- You *can* learn customer preferences for future recommendations.
- You *cannot* yet process payments or finalize delivery orders. If a user tries to complete an order, guide them by saying "I can get that ready for you! To finalize the payment and delivery, please call us at [phone number] or click this link to our online portal: [link]."
"""

cap = """
- You *can* look up product information, prices, and promotions.
- You *can* learn customer preferences for future recommendations.
- You *cannot* yet process payments or finalize delivery orders. If a user tries to complete an order, guide them by saying "I can get that ready for you! To finalize the payment and delivery, please call us at [phone number] or click this link to our online portal: [link]."
"""

# --- SYSTEM-LEVEL CORE PROMPT ---
# This is our application's "firmware". It enforces the fundamental rules
# of how the AI must behave, regardless of the business's specific persona.
# In app/services/realtime_service.py

SYSTEM_CORE_PROMPT = """
**CORE OPERATIONAL RULES (NON-NEGOTIABLE):**

1.  **GROUNDING:** You MUST base your answers *exclusively* on the information provided in the "CONTEXT" section. Do not use any outside knowledge or make assumptions. If the context is empty or does not contain the answer, you do not know the answer.

2.  **TOOL-FORCING:**
    - **IF** a user asks about a specific item or product AND the answer is NOT in the CONTEXT, **THEN** you MUST use the `lookup_product_info` tool. Your `response_text` in this case must be a simple "loading message" like "Let me check on that for you... ⏳".
    - **ELSE IF** you cannot answer a factual question for any other reason, **THEN** you MUST use the `request_human_intervention` tool and your `response_text` must be "That's a great question, let me get my supervisor to help with that."

3.  **NO HALLUCINATION:** You are strictly forbidden from inventing products, information, prices, or any other factual information. If you don't know, you MUST follow the TOOL-FORCING rule.
"""


# --- Internal Data Models for Type Safety ---
# These models ensure that the data we pass between methods is structured and validated.

class BusinessContext(BaseModel):
    id: UUID
    system_prompt: str
    business_name: str

class CustomerContext(BaseModel):
    id: UUID
    customer_name: str

class LLMContext(BaseModel):
    history: List[Dict[str, str]] = []
    long_term_memory: List[Dict[str, str]] = []
    rag_knowledge: List[str] = []

# --- The Service Class ---

class RealtimeService:
    """
    A robust, fail-fast service to handle a single real-time task from the queue.
    It is instantiated for each task, processes it, and then is discarded.
    """
    
    # --- Step 0: Initialization with Type Hinting ---
    def __init__(self, task_payload: dict):
        """
        Initializes the service with the raw payload.
        Class attributes are explicitly typed for clarity and static analysis.
        """
        self.payload: Dict[str, Any] = task_payload
        
        # These will be populated by the workflow methods.
        # They are 'Optional' because they don't exist until the methods run.
        self.user_phone: Optional[str] = None
        self.user_message: Optional[str] = None
        self.business: Optional[BusinessContext] = None
        self.customer: Optional[CustomerContext] = None
        self.context: LLMContext = LLMContext() # Initialize with an empty context model

    # --- Main Orchestration Method ---
    def run(self):
        """
        Executes the full, sequential workflow. Each step validates its own
        pre-requisites, ensuring the system fails fast if data is missing.
        """
        logger.info("--- Realtime Task Processing STARTED ---")
        try:
            # Each method now returns a boolean indicating success.
            if not self._deconstruct_and_fetch_business(): return
            if not self._fetch_or_create_customer(): return
            self._gather_context() # This method can proceed even with no context.
            
            action_plan = self._get_llm_action_plan()
            if not action_plan:
                # If the LLM fails, we should still handle it gracefully.
                # Here we could send a generic "I'm sorry, I'm having trouble" message.
                logger.error("LLM failed to produce a valid action plan. Aborting task.")
                return

            self._execute_action_plan(action_plan)
            logger.info("--- Realtime Task Processing COMPLETED ---")
        except Exception as e:
            # Catch any unexpected errors from the methods.
            logger.error(f"FATAL error during RealtimeService execution: {e}", exc_info=True)
            # This exception will be caught by the worker, which will mark the task as 'failed'.
            raise

    # --- Workflow Step Methods ---

    def _deconstruct_and_fetch_business(self) -> bool:
        """
        Step 1: Parses the payload and fetches the essential Business object.
        If the business cannot be found, the entire process cannot continue.
        """
        logger.info("[STEP 1/5] Deconstructing payload and fetching business...")
        try:
            value = self.payload['entry'][0]['changes'][0]['value']
            self.user_phone = value['contacts'][0]['wa_id']
            self.user_message = value['messages'][0]['text']['body']
            business_phone_id = value['metadata']['phone_number_id']
            
            res = supabase.table('businesses').select('id, system_prompt, business_name').eq('whatsapp_phone_number_id', business_phone_id).single().execute()
            
            # The Pydantic model validates the structure of the response data.
            self.business = BusinessContext(**res.data)
            logger.info(f"[STEP 1/5] Success. Operating for business ID: {self.business.id}")
            return True
        except Exception as e:
            # This handles JSON parsing errors, database errors, or Pydantic validation errors.
            logger.error(f"[STEP 1/5] FAILED. Could not deconstruct payload or find business. Error: {e}", exc_info=True)
            return False


    def _fetch_or_create_customer(self) -> bool:
        """
        Step 2: Finds an existing customer or creates a new one.
        This method is now robust and uses the correct Python library patterns.
        """
        if not self.business or not self.user_phone:
            logger.error("[STEP 2/5] FAILED: Cannot fetch customer without business or user phone.")
            return False

        logger.info(f"[STEP 2/5] Finding or creating customer for phone: {self.user_phone}")
        
        try:
            # 1. Try to find an existing customer first.
            find_res = supabase.table('customers') \
                .select('id, customer_name') \
                .eq('business_id', self.business.id) \
                .eq('phone_number', self.user_phone) \
                .limit(1) \
                .execute()

            # The response for a query will always have a .data attribute, which is a list.
            if find_res.data:
                # Customer exists.
                customer_data = find_res.data[0]
                logger.info(f"DEBUG: Data from DB to be validated by Pydantic: {customer_data}")
                self.customer = CustomerContext(**customer_data)
                logger.info(f"[STEP 2/5] Found existing customer ID: {self.customer.id}")
                return True
            else:
                # 2. Customer does not exist. Create them.
                user_name_from_payload = self.payload['entry'][0]['changes'][0]['value']['contacts'][0]['profile']['name']
                logger.info(f"[STEP 2/5] New customer detected. Creating record for '{user_name_from_payload}'.")
                
                insert_data = {
                    "business_id": str(self.business.id),
                    "phone_number": self.user_phone,
                    "customer_name": user_name_from_payload
                }
                
                # Execute the insert. The Python library for v1/sync does not support
                # chaining .select() after .insert(). We must do it in two steps.
                # We also don't need the returned data from the insert itself.
                supabase.table('customers').insert(insert_data).execute()

                # 3. Now that the customer is created, fetch their new record to get the UUID.
                # This is the guaranteed way to get the correct data.
                refetch_res = supabase.table('customers') \
                    .select('id, customer_name') \
                    .eq('business_id', self.business.id) \
                    .eq('phone_number', self.user_phone) \
                    .single() \
                    .execute()

                # Now we can safely create our Pydantic model.
                self.customer = CustomerContext(**refetch_res.data)
                logger.info(f"[STEP 2/5] Successfully created and fetched new customer ID: {self.customer.id}")
                return True

        except Exception as e:
            # This will catch any Postgrest APIError or other exceptions.
            logger.error(f"[STEP 2/5] FAILED to fetch or create customer. Error: {e}", exc_info=True)
            return False

    def _gather_context(self):
        """
        Step 3: Gathers all available context for the LLM.
        This method is designed to be resilient and will simply result in empty
        context lists if any part fails.
        """
        if not self.business: return # Cannot proceed without a business context

        logger.info("[STEP 3/5] Gathering context for LLM...")
        
        # A) Short-term history (only if a customer exists)
        if self.customer:
            history_res = supabase.table('conversations').select('role, content').eq('customer_id', self.customer.id).order('created_at', desc=True).limit(8).execute()
            self.context.history = list(reversed(history_res.data)) if history_res.data else []

        # B) Long-term memory (only if a customer exists)
        if self.customer:
            memory_res = supabase.table('customer_memory').select('fact_key, fact_value').eq('customer_id', self.customer.id).limit(10).execute()
            self.context.long_term_memory = memory_res.data or []

        # C) RAG Knowledge (always attempt this)
        try:
            if self.user_message:
                embedding = openai_service.get_embedding(self.user_message)
                rag_res = supabase.rpc('match_knowledge', {'query_embedding': embedding, 'p_business_id': str(self.business.id), 'match_threshold': 0.72, 'match_count': 3}).execute()
                self.context.rag_knowledge = [item['content'] for item in (rag_res.data or [])]
            else:
                logger.warning(f"Could not fetch RAG knowledge. Proceeding without it. self.user_message is None")
                
        except Exception as e:
            logger.warning(f"Could not fetch RAG knowledge. Proceeding without it. Error: {e}")

        logger.info(f"Context gathered: {len(self.context.history)} history, {len(self.context.long_term_memory)} memory, {len(self.context.rag_knowledge)} RAG chunks.")

    def _get_llm_action_plan(self) -> ActionPlan | None:
        """Step 4: Constructs the prompt and calls Gemini to get a structured action plan."""
        if not self.business: return None
        logger.info("[STEP 4/5] Calling Gemini for unified action plan...")
        
        # We use .model_dump() to safely serialize our Pydantic models for the prompt
        prompt = f"""{self.business.system_prompt}
        **Your Capabilities:**
        {CAPABILITY_PROMPT}

        **Relevant Long-Term Memory about this User:**
        {json.dumps(self.context.long_term_memory)}

        **Relevant Business Information & FAQs:**
        {json.dumps(self.context.rag_knowledge)}

        **Recent Conversation History:**
        {json.dumps(self.context.history)}

        **User's Latest Message:**
        "{self.user_message}"

        **Your Task:**
        ... (rest of the detailed prompt is the same) ...
        """
        
								# Level 2: The business-specific persona prompt from the DB
        business_persona_prompt = self.business.system_prompt
        business_name = self.business # Assuming this field exists from our pydantic model
        
								# Assemble the final prompt using our layered approach
        prompt = f"""
        **Your Identity:** Your name is Astro. You are an customer assistant representing {	self.business.business_name	}.

        {SYSTEM_CORE_PROMPT}

        ---
        **BUSINESS-SPECIFIC STYLE GUIDELINES (Adopt this tone):**
        {business_persona_prompt}
        ---

        **CONTEXT (Your ONLY source of truth):**
        - Long-Term Memory: {json.dumps(self.context.long_term_memory)}
        - Business FAQs & Knowledge: {json.dumps(self.context.rag_knowledge)}

        **CONVERSATION HISTORY:**
        {json.dumps(self.context.history)}

        **USER'S LATEST MESSAGE:**
        "{self.user_message}"

        **YOUR TASK:**
        1.  Adopt the persona of Astro as described in the style guidelines.
        2.  Follow your CORE OPERATIONAL RULES exactly.
        3.  Analyze the user's message based on the CONTEXT and HISTORY.
        4.  Generate a valid JSON object using the `ActionPlan` schema to define your response and any necessary tool calls.
        """
        
        action_plan_object = gemini_service.think_and_generate_json(prompt=prompt, response_schema=ActionPlan)
        if not action_plan_object:
              logger.error("LLM (Schema Mode) failed to generate a valid action plan object.")
              return None
        
        logger.info(f"LLM returned valid action plan object: {action_plan_object}")
        return action_plan_object

    def _execute_action_plan(self, action_plan: ActionPlan):
        """Step 5: Parses the LLM's plan and queues follow-up events."""
        if not self.business or not self.user_phone: return
        logger.info(f"[STEP 5/5] Executing action plan: {action_plan}")

        logger.info("------------------------------------------------------------")
        logger.info(f"{action_plan}")
        logger.info("------------------------------------------------------------")

        response_text = action_plan.response_text
        tool_calls = action_plan.tool_calls

        # Respond First
        if response_text:
            whatsapp_payload = {
                "messaging_product": "whatsapp",
                "to": self.user_phone,
                "type": "text",
                "text": {"body": response_text},
            }
            outbound_event = {"event_type": "send_outbound_message", "payload": {"data": whatsapp_payload, "config": {"channel": "whatsapp", "business_id": str(self.business.id)}}}
            supabase.table('event_dispatcher').insert(outbound_event).execute()
            logger.info(f"Queued outbound message for {self.user_phone}.")

        # Then queue background tasks
        for tool_call in tool_calls:
            if tool_call.name == "queue_for_profiling":
                if not self.customer:
                    logger.warning("Cannot queue for profiling as customer object does not exist.")
                    continue
                profiling_task = {"event_type": "run_profiling_analysis", "payload": { "customer_id": str(self.customer.id), "business_id": str(self.business.id), "summary": tool_call.arguments.summary_of_new_info, "full_conversation": self.context.history + [{"role": "user", "content": self.user_message}]}}
                supabase.table('profiling_tasks').insert(profiling_task).execute()
                logger.info(f"Queued task for profiling customer {self.customer.id}.")
        
        # Save conversation to DB (only if customer exists)
        if self.customer and response_text:
            db_entries = [{'customer_id': str(self.customer.id), 'role': 'user', 'content': self.user_message}, {'customer_id': str(self.customer.id), 'role': 'assistant', 'content': response_text}]
            supabase.table('conversations').insert(db_entries).execute()