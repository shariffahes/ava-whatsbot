import azure.functions as func
import json
import logging
import datetime
import os
from azure.servicebus import ServiceBusClient, ServiceBusMessage
from buspal_backend.models.reminder import ReminderModel
from buspal_backend.services.whatsapp import WhatsappService
from reminder_processor import schedule_next_occurrence_enhanced

# Initialize WhatsApp service
whatsapp_client = WhatsappService(
    api_url=os.environ.get("WHATSAPP_API_URL") # type: ignore
)

def main(mytimer: func.TimerRequest) -> None:
    """
    Daily timer function that processes long-term reminders.
    Runs daily at 9:00 AM Beirut time to:
    1. Move pending reminders (due within 7 days) to Service Bus
    2. Process overdue pending reminders immediately
    3. Clean up old completed reminders
    """
    logging.info('Daily reminder scheduler started')
    
    try:
        # Process overdue pending reminders first
        overdue_count = process_overdue_reminders()
        logging.info(f"Processed {overdue_count} overdue reminders")
        
        # Move pending reminders due within x days to Service Bus
        moved_count = move_pending_to_service_bus()
        logging.info(f"Moved {moved_count} pending reminders to Service Bus")
        
        # Clean up old reminders (optional, runs weekly)
        if datetime.datetime.utcnow().weekday() == 0:  # Monday
            cleaned_count = ReminderModel.cleanup_old_reminders(days_old=30)
            logging.info(f"Cleaned up {cleaned_count} old reminders")
        
        logging.info('Daily reminder scheduler completed successfully')
        
    except Exception as e:
        logging.error(f"Error in daily reminder scheduler: {str(e)}")
        raise

def process_overdue_reminders():
    """
    Process reminders that are already overdue but still in pending status.
    These should be sent immediately.
    """
    overdue_reminders = ReminderModel.get_overdue_pending_reminders()
    processed_count = 0
    
    for reminder in overdue_reminders:
        try:
            # Send the reminder immediately
            reminder_id = reminder['_id']
            chat_id = reminder['chat_id']
            message = reminder['message']
            recurrence_pattern = reminder.get('recurrence_pattern')
            
            formatted_message = f"🔔 {message}"
            whatsapp_client.send_message(chat_id, formatted_message)
            
            ReminderModel.mark_as_sent(reminder_id)
            logging.info(f"Sent overdue reminder {reminder_id} to {chat_id}")
            
            if recurrence_pattern:
                schedule_next_occurrence_enhanced(reminder, recurrence_pattern)
                logging.info(f"Scheduled next occurrence for recurring reminder {reminder_id}")
            
            processed_count += 1
            
        except Exception as e:
            logging.error(f"Failed to process overdue reminder {reminder.get('_id')}: {str(e)}")
            ReminderModel.mark_as_failed(reminder.get('_id'), str(e))
    
    return processed_count

def move_pending_to_service_bus():
    """
    Move pending reminders that are due within 13 days to Service Bus.
    """
    pending_reminders = ReminderModel.get_pending_reminders_due_soon(days_ahead=13)
    moved_count = 0
    
    connection_str = os.getenv("AZURE_SERVICE_BUS_CONNECTION_STRING")
    queue_name = os.getenv("REMINDER_QUEUE_NAME", "reminders")
    
    if not connection_str:
        logging.error("Service Bus connection string not configured")
        return 0
    
    with ServiceBusClient.from_connection_string(connection_str) as client:
        with client.get_queue_sender(queue_name) as sender:
            for reminder in pending_reminders:
                try:
                    reminder_id = reminder['_id']
                    
                    reminder_payload = {
                        "reminder_id": reminder_id,
                        "chat_id": reminder['chat_id'],
                        "message": reminder['message'],
                        "recurrence_pattern": reminder.get('recurrence_pattern'),
                        "scheduled_time": reminder['scheduled_time'].isoformat(),
                        "created_at": reminder['created_at'].isoformat()
                    }
                    
                    message_body = json.dumps(reminder_payload)
                    scheduled_message = ServiceBusMessage(
                        body=message_body,
                        scheduled_enqueue_time_utc=reminder['scheduled_time']
                    )

                    sender.send_messages(scheduled_message)
                
                    ReminderModel.move_to_service_bus(reminder_id)
                    
                    logging.info(f"Moved reminder {reminder_id} to Service Bus")
                    moved_count += 1
                    
                except Exception as e:
                    logging.error(f"Failed to move reminder {reminder.get('_id')} to Service Bus: {str(e)}")
                    # Keep as pending, will retry next day
    
    return moved_count

