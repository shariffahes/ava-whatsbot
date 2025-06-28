
import os
import aiohttp
import urllib.parse
import json
import pytz
import datetime
import uuid
from azure.servicebus import ServiceBusClient, ServiceBusMessage
from buspal_backend.models.reminder import ReminderModel
from azure.servicebus.exceptions import ServiceBusError
import logging

logger = logging.getLogger(__name__)
def encode_query(query: str) -> str:
    return urllib.parse.quote(query)

KEY = "my_pal"
LIMIT = 8

async def send_reaction(query, reaction_type="GIF"):
    media_type = "webp" if reaction_type == "STICKER" else "mp4"
    search_filter = "sticker" if reaction_type == "STICKER" else None
    
    url = "https://tenor.googleapis.com/v2/search"
    params = {
        "random": "true",
        "media_filter": media_type,
        "q": encode_query(query),
        "key": os.getenv("TENOR_API_KEY"),
        "client_key": KEY,
        "limit": LIMIT,
        "searchFilter": search_filter
    }
    
    timeout = aiohttp.ClientTimeout(total=10)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params) as response:
                response.raise_for_status()
                res = await response.json()
                contents = []
                media = [content.get('media_formats', {}).get(media_type, {}).get('url', None) for content in res.get('results', [])]
                for index, result in enumerate(res.get('results', [])):
                    media_url = media[index]
                    if not media_url:
                        continue
                    contents.append({"gif_content": result.get('content_description', ''), "index": index})
          
                return {'contents': contents, "media": media, "type": reaction_type}
    except aiohttp.ClientError as e:
        logger.error(f"Error fetching reaction: {e}")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error fetching reaction: {e}")
        return {}

def schedule_reminder(chat_id: str, message: str, scheduled_time: str, recurrence_pattern: str = None):
    """
    Schedule a reminder using hybrid approach: Service Bus (≤7 days) or Database (>7 days).
    
    Args:
        chat_id: WhatsApp chat ID to send reminder to
        message: Reminder message text
        scheduled_time: ISO format datetime string (e.g., "2024-06-25T15:30:00")
        recurrence_pattern: Optional recurrence pattern (e.g., "daily", "weekly", "monthly")
    
    Returns:
        dict: Success/error status and reminder ID
    """
    try:
        reminder_id = str(uuid.uuid4())
        beirut_tz = pytz.timezone("Asia/Beirut")
        if 'T' in scheduled_time:
            local_dt = datetime.datetime.fromisoformat(scheduled_time.replace('Z', ''))
        else:
            local_dt = datetime.datetime.strptime(scheduled_time, "%Y-%m-%d %H:%M:%S")
        
        if local_dt.tzinfo is None:
            local_dt = beirut_tz.localize(local_dt)
        
        utc_dt = local_dt.astimezone(pytz.utc)
        
        # Calculate days until reminder
        now_utc =  datetime.datetime.now(pytz.utc)
        days_until_reminder = (utc_dt - now_utc).days
        if days_until_reminder < 14:
            return _schedule_with_service_bus(
                reminder_id, chat_id, message, utc_dt, local_dt, 
                recurrence_pattern, scheduled_time
            )
        else:
            return _schedule_with_database(
                reminder_id, chat_id, message, utc_dt, local_dt, 
                recurrence_pattern, scheduled_time
            )
        
    except Exception as e:
        print("Failed to schedule ", e)
        return {"success": False, "error": f"Failed to schedule reminder: {str(e)}"}

def get_scheduled_reminders(chat_id):
    """Get the scheduled reminders for the current conversation"""
    try:
        if chat_id is None:
            return {"success": False, "error": "Could not fetch active reminders"}
        
        reminders = ReminderModel.get_by_chat_id(chat_id=chat_id, status=["scheduled", "pending"])
        
        return {
            "success": True, 
            "reminders": reminders
        }
        
    except Exception as e:
        return {"success": False, "error": f"Failed to get scheduled reminders: {str(e)}"}

def cancel_reminder(reminder_id):
    """Get the scheduled reminders for the current conversation"""
    try:
        if reminder_id is None:
            return {"success": False, "error": "Could not cancel the scheduled reminder"}
        
        result = ReminderModel.cancel_reminder(reminder_id)
        
        return { "success": result }
        
    except Exception as e:
        return {"success": False, "error": f"Failed to store reminder: {str(e)}"}

def _schedule_with_service_bus(reminder_id, chat_id, message, utc_dt, local_dt, 
                              recurrence_pattern, scheduled_time):
    """Schedule reminder using Service Bus (for reminders ≤7 days)."""
    try:
        reminder_payload = {
            "reminder_id": reminder_id,
            "chat_id": chat_id,
            "message": message,
            "recurrence_pattern": recurrence_pattern,
            "scheduled_time": scheduled_time,
            "created_at": datetime.datetime.utcnow().isoformat()
        }
        
        ReminderModel.create(
            reminder_id=reminder_id,
            chat_id=chat_id,
            message=message,
            scheduled_time=utc_dt,
            recurrence_pattern=recurrence_pattern,
            status="scheduled"
        )
        
        connection_str = os.getenv("AZURE_SERVICE_BUS_CONNECTION_STRING")
        queue_name = os.getenv("REMINDER_QUEUE_NAME", "reminders")

        if not connection_str:
            return {"success": False, "error": "Service Bus connection string not configured"}
        
        with ServiceBusClient.from_connection_string(connection_str) as client:
            with client.get_queue_sender(queue_name) as sender:
                message_body = json.dumps(reminder_payload)
                scheduled_message = ServiceBusMessage(
                    body=message_body,
                    scheduled_enqueue_time_utc=utc_dt
                )
                
                sender.send_messages(scheduled_message)
        
        return {
            "success": True, 
            "reminder_id": reminder_id,
            "message": f"Reminder scheduled for {local_dt.strftime('%Y-%m-%d %H:%M %Z')} (Service Bus)"
        }
        
    except ServiceBusError as e:
        print(f"ServiceBus Error Details:")
        print(f"Message: {e.message}")
        print(f"Inner Exception: {e.__cause__}")
        print(f"Full Exception: {e}")
        
        return {"success": False, "error": f"Failed to store reminder: {str(e)}"}

def _schedule_with_database(reminder_id, chat_id, message, utc_dt, local_dt, 
                           recurrence_pattern, scheduled_time):
    """Schedule reminder using database storage (for reminders >7 days or Service Bus fallback)."""
    try:
        # Store reminder metadata in MongoDB with pending status
        ReminderModel.create(
            reminder_id=reminder_id,
            chat_id=chat_id,
            message=message,
            scheduled_time=utc_dt,
            recurrence_pattern=recurrence_pattern,
            status="pending"
        )
        
        return {
            "success": True, 
            "reminder_id": reminder_id,
            "message": f"Reminder scheduled for {local_dt.strftime('%Y-%m-%d %H:%M %Z')} (Long-term)"
        }
        
    except Exception as e:
        return {"success": False, "error": f"Failed to store reminder: {str(e)}"}
