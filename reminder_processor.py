import azure.functions as func
import json
import logging
import datetime
import pytz
import os
from google import genai
from buspal_backend.config.constants import PROMPTS
from buspal_backend.services.whatsapp import WhatsappService
from buspal_backend.models.reminder import ReminderModel
from google.genai.types import GenerateContentConfig, Part, Content

# Initialize WhatsApp service
whatsapp_client = WhatsappService(
    api_url=os.environ.get("WHATSAPP_API_URL")
)
gemini = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"),)

async def main(msg: func.ServiceBusMessage):
    """
    Azure Function triggered by Service Bus messages for processing reminders.
    
    Args:
        msg: Service Bus message containing reminder data
    """
    logging.info('Reminder processor function started')
    
    try:
        # Parse the message body
        message_body = msg.get_body().decode('utf-8')
        reminder_data = json.loads(message_body)
        print(f"processing reminder: {reminder_data}", )
        logging.info(f"Processing reminder: {reminder_data.get('reminder_id')}")
        
        # Extract reminder details
        reminder_id = reminder_data.get('reminder_id')
        chat_id = reminder_data.get('chat_id')
        message = reminder_data.get('message')
        recurrence_pattern = reminder_data.get('recurrence_pattern')
        
        if not all([reminder_id, chat_id, message]):
            logging.error(f"Missing required fields in reminder data: {reminder_data}")
            return
        reminder_record = ReminderModel.get_by_id(reminder_id)
        if reminder_record and reminder_record['status'] != "scheduled":
            return
        try:
            formatted_message = f"🔔 {message}"
            
            # Send the message
            await whatsapp_client.send_message(chat_id, formatted_message)
            logging.info(f"Reminder sent successfully to {chat_id}")
            ReminderModel.mark_as_sent(reminder_id)
            
        except Exception as e:
            logging.error(f"Failed to send reminder message: {str(e)}")
            ReminderModel.mark_as_failed(reminder_id, str(e))
            return
        
        # Handle recurring reminders with enhanced logic
        if recurrence_pattern:
            try:
                schedule_next_occurrence_enhanced(reminder_data, recurrence_pattern)
                logging.info(f"Next occurrence scheduled for recurring reminder {reminder_id}")
            except Exception as e:
                logging.error(f"Failed to schedule next occurrence: {str(e)}")
        
        logging.info(f"Reminder {reminder_id} processed successfully")
        
    except Exception as e:
        logging.error(f"Error processing reminder: {str(e)}")
        raise

def schedule_next_occurrence_enhanced(reminder_data, recurrence_pattern):
    """
    Enhanced version of schedule_next_occurrence with better month/year handling.
    Uses hybrid approach for scheduling (Service Bus ≤7 days, Database >7 days).
    
    Args:
        reminder_data: Original reminder data from database or Service Bus message
        recurrence_pattern: Recurrence pattern (daily, weekly, monthly, yearly)
    """
    try:
        from buspal_backend.services.ai.tools.tools import schedule_reminder
        
        # Get original scheduled time - handle both database format and Service Bus format
        if isinstance(reminder_data, dict) and 'scheduled_time' in reminder_data:
            # From Service Bus message payload
            original_time = reminder_data.get('scheduled_time')
        else:
            # From database document (might be datetime object)
            original_time = reminder_data.get('scheduled_time')
            if isinstance(original_time, datetime.datetime):
                original_time = original_time.isoformat()
        
        beirut_tz = pytz.timezone("Asia/Beirut")
        
        # Parse the original scheduled time
        if 'T' in original_time:
            base_dt = datetime.datetime.fromisoformat(original_time.replace('Z', ''))
        else:
            base_dt = datetime.datetime.strptime(original_time, "%Y-%m-%d %H:%M:%S")
        
        # Localize to Beirut timezone if not already timezone-aware
        if base_dt.tzinfo is None:
            base_dt = beirut_tz.localize(base_dt)
        
        # Calculate next occurrence based on recurrence pattern
        if recurrence_pattern.lower() == 'daily':
            next_dt = base_dt + datetime.timedelta(days=1)
        elif recurrence_pattern.lower() == 'weekly':
            next_dt = base_dt + datetime.timedelta(weeks=1)
        elif recurrence_pattern.lower() == 'monthly':
            # Enhanced month handling
            next_dt = add_months(base_dt, 1)
        elif recurrence_pattern.lower() == 'yearly':
            next_dt = add_months(base_dt, 12)
        else:
            logging.warning(f"Unknown recurrence pattern: {recurrence_pattern}")
            return
        # Schedule the next occurrence using hybrid approach
        next_time_str = next_dt.strftime("%Y-%m-%dT%H:%M:%S")
        config = GenerateContentConfig(system_instruction=PROMPTS['REMINDER'])
        response = gemini.models.generate_content(
            config=config,
            model="gemini-2.5-flash-preview-05-20",
            contents=[Content(role="user", parts=[Part.from_text(text=reminder_data.get('message'))])]
          )
        result = schedule_reminder(
            chat_id=reminder_data.get('chat_id'),
            message=response.text,
            scheduled_time=next_time_str,
            recurrence_pattern=recurrence_pattern
        )
        
        if not result.get('success'):
            logging.error(f"Failed to schedule next occurrence: {result.get('error')}")
        else:
            # Log whether it went to Service Bus or Database
            approach = "Service Bus" if "Service Bus" in result.get('message', '') else "Database"
            logging.info(f"Next occurrence scheduled via {approach}: {next_time_str}")
        
    except Exception as e:
        logging.error(f"Error in schedule_next_occurrence_enhanced: {str(e)}")
        raise

def add_months(dt, months):
    """
    Add months to a datetime, handling month boundaries correctly.
    
    Args:
        dt: datetime object
        months: number of months to add
    
    Returns:
        datetime: new datetime with months added
    """
    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    day = min(dt.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return dt.replace(year=year, month=month, day=day)