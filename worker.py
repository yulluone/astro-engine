# worker.py
import logging
import time
import threading
from app.db import supabase
from app.logging_config import setup_logging
from app.services.realtime_service import RealtimeService
from app.services import outbound_service # Import our new service
from app.config import Config

# Configure logging for the worker process
setup_logging()
logger = logging.getLogger("worker")

def dispatch_events():
    """Polls the event_dispatcher and routes events to specialized queues."""
    logger.info("Dispatcher worker started...")
    while True:
        try:
            res = supabase.rpc('get_and_lock_dispatcher_event', {}).execute()
            if res.data:
                event = res.data[0]
                event_id, event_type, payload = event['id'], event['event_type'], event['payload']
                logger.info(f"DISPATCHER: Processing event {event_id} of type '{event_type}'")

                # --- The Routing Logic ---
                if event_type == 'new_inbound_message':
                    # All inbound messages go to the realtime queue first
                    task = {"event_type": "handle_user_message", "payload": payload}
                    supabase.table('realtime_tasks').insert(task).execute()
                    logger.info(f"DISPATCHER: Event {event_id} dispatched to 'realtime_tasks'.")
                
                # --- NEW ROUTE FOR OUTBOUND MESSAGES ---
                elif event_type == 'send_outbound_message':
                    # Outbound messages are also high-priority, so they use the realtime queue.
                    # We give it a different event_type so the realtime worker knows what to do.
                    task = {"event_type": "execute_whatsapp_send", "payload": payload}
                    supabase.table('realtime_tasks').insert(task).execute()
                    logger.info(f"DISPATCHER: Event {event_id} dispatched to 'realtime_tasks' for sending.")

                else:
                    logger.warning(f"DISPATCHER: No route found for event type '{event_type}'. Marking as failed.")
                    supabase.table('event_dispatcher').update({'status': 'failed'}).eq('id', event_id).execute()

        except Exception as e:
            logger.error(f"Error in dispatcher loop: {e}", exc_info=True)
        
        time.sleep(2)

# In worker.py

def process_realtime_tasks():
    """Polls the realtime_tasks queue and triggers the appropriate service."""
    logger.info("Realtime worker started...")
    while True:
        try:
            res = supabase.rpc('get_and_lock_realtime_task', {}).execute()
            
            if res.data:
                task = res.data[0]
                
                # THE FIX: Get the event_type from the task object itself.
                task_id = task.get('id')
                event_type = task.get('event_type')
                payload = task.get('payload')

                logger.info(f"REALTIME: Processing task {task_id} of type '{event_type}'")

                try:
                    # THE FIX: Check against the correct task event types.
                    if event_type == 'handle_user_message':
                        # The payload of the task IS the original dispatcher event payload.
                        service_instance = RealtimeService(task_payload=payload)
                        service_instance.run()
                    
                    elif event_type == 'execute_whatsapp_send':
                        # The payload of the task IS the original dispatcher event payload.
                        config = payload.get('config', {})
                        
                        business_id = config.get('business_id')
                        channel = config.get('channel')
                        message_payload = payload.get('data')
                        
                        if not all([business_id, channel, message_payload]):
                            raise ValueError("Missing business_id, channel, or data payload for sending message.")
                        
                        if channel == 'whatsapp':
                            outbound_service.send_whatsapp_message(business_id=business_id, message_payload=message_payload)
                        else:
                            logger.warning(f"REALTIME: Outbound channel '{channel}' not supported yet.")
                            
                    else:
                        # This will now correctly catch the 'None' case or any other unexpected type.
                        raise ValueError(f"Unknown event_type in realtime_tasks: {event_type}")

                    supabase.table('realtime_tasks').update({'status': 'complete'}).eq('id', task_id).execute()
                    logger.info(f"REALTIME: Task {task_id} completed successfully.")
                except Exception as task_error:
                    logger.error(f"REALTIME: Error processing task {task_id}: {task_error}", exc_info=True)
                    supabase.table('realtime_tasks').update({'status': 'failed', 'last_error': str(task_error)}).eq('id', task_id).execute()
        except Exception as e:
            logger.error(f"Error in realtime worker loop: {e}", exc_info=True)
        
        time.sleep(2)
        
# ... (profiling worker function can be defined here but not run yet) ...

if __name__ == "__main__":
    import threading
    logger.info(f"Starting workers in separate threads... DEV MODE: {Config.DEV_MODE}")
    
    dispatcher_thread = threading.Thread(target=dispatch_events, daemon=True)
    realtime_thread = threading.Thread(target=process_realtime_tasks, daemon=True)
    
    dispatcher_thread.start()
    realtime_thread.start()
    
    while True:
        time.sleep(1)