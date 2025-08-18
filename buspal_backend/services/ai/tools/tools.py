
import os
from typing import Optional
import aiohttp
import urllib.parse
import json
import pytz
import datetime
import uuid
from azure.servicebus import ServiceBusClient, ServiceBusMessage
from buspal_backend.models.reminder import ReminderModel
from buspal_backend.models.user import UserModel
from buspal_backend.models.conversation import ConversationModel
from buspal_backend.types.enums import AIMode
from buspal_backend.services.expense_settlement import ExpenseSettlementService
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

def schedule_reminder(chat_id: str, message: str, scheduled_time: str, recurrence_pattern: Optional[str] = None):
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

def add_expense(chat_id: str, amount: float, payer_name: str, participants: Optional[list] = None, desc: str = 'Expense'):
    """
    Add a new expense to the group chat.
    
    Args:
        chat_id: WhatsApp chat ID
        description: Description of the expense
        amount: Total amount spent
        payer_name: Name of the person who paid. Exactly as it appears in sender
        participants: List of participant names (optional, defaults to equal split)
    
    Returns:
        dict: Success/error status and expense details
    """
    try:
        payer = UserModel.get_by_name(payer_name, chat_id)
        if not payer:
          payer_id = f"{chat_id}_{payer_name.lower().replace(' ', '_')}"
        else:
            payer_id = payer['wa_id']
        
        # If no participants specified, create a default list with just the payer
        if not participants:
            participants = [{"user_id": payer_id, "name": payer_name}]
        else:
            # Convert participant names to user objects
            participant_objects = []
            for name in participants:
                participant = UserModel.get_by_name(name, chat_id)
                if participant:
                    participant_id = participant['wa_id']
                else:
                  participant_id = f"{chat_id}_{name.lower().replace(' ', '_')}"
                participant_objects.append({"user_id": participant_id, "name": name})
            participants = participant_objects
        
        # Split equally among participants
        participants_with_shares = ExpenseSettlementService.split_equally(amount, participants)
        
        # Add expense
        expense = ExpenseSettlementService.add_expense(
            convo_id=chat_id,
            description=desc,
            total_amount=amount,
            payer_id=payer_id,
            payer_name=payer_name,
            participants=participants_with_shares
        )
        
        participant_names = ", ".join([p["name"] for p in participants_with_shares])
        per_person = amount / len(participants_with_shares)
        
        return {
            "success": True,
            "expense_id": str(expense.get("_id")),
            "message": f"💰 Expense added!\n"
                      f"Amount: ${amount:.2f}\n"
                      f"Description: {desc}\n"
                      f"Paid by: {payer_name}\n"
                      f"Split among: {participant_names}\n"
                      f"Per person: ${per_person:.2f}"
        }
        
    except Exception as e:
        logger.error(f"Failed to add expense: {e}")
        return {"success": False, "error": f"Failed to add expense: {str(e)}"}

def calculate_expense_settlement(chat_id: str):
    """
    Calculate optimal expense settlements for a group chat.
    
    Args:
        chat_id: WhatsApp chat ID
    
    Returns:
        dict: Settlement details with who owes whom
    """
    try:
        settlement_data = ExpenseSettlementService.calculate_settlements(chat_id)
        
        # Clean transactions to remove user IDs, keeping only names for AI
        if "transactions" in settlement_data:
            cleaned_transactions = []
            for transaction in settlement_data["transactions"]:
                cleaned_transaction = {
                    "from_name": transaction["from_name"],
                    "to_name": transaction["to_name"],
                    "amount": transaction["amount"]
                }
                cleaned_transactions.append(cleaned_transaction)
            settlement_data["transactions"] = cleaned_transactions
        
        return {
            "success": True,
            "settlment_date": settlement_data
        }
        
    except Exception as e:
        logger.error(f"Failed to calculate settlements: {e}")
        return {"success": False, "error": f"Failed to calculate settlements: {str(e)}"}

def get_expense_balance(chat_id: str, user_name: str):
    """
    Get individual expense balance for a user.
    
    Args:
        chat_id: WhatsApp chat ID
        user_name: Name of the user
    
    Returns:
        dict: User's balance and transaction details
    """
    try:
        user = UserModel.get_by_name(user_name, chat_id)
        if user:
            user_id = user['wa_id']
        else:
          user_id = f"{chat_id}_{user_name.lower().replace(' ', '_')}"
        balance_data = ExpenseSettlementService.get_user_balance_summary(chat_id, user_id)
        balance = balance_data["net_balance"]
        
        if abs(balance) < 0.01:
            message = f"✅ {user_name}, you're all settled!"
        elif balance > 0:
            message = f"💰 {user_name}, you should receive ${balance:.2f}"
        else:
            message = f"💳 {user_name}, you owe ${abs(balance):.2f}"
        
        # Add transaction details
        if balance_data["transactions"]:
            message += "\n\n📋 Your transactions:"
            for t in balance_data["transactions"]:
                if t["from"] == user_id:
                    message += f"\n• Pay ${t['amount']:.2f} to {t['to_name']}"
                else:
                    message += f"\n• Receive ${t['amount']:.2f} from {t['from_name']}"
        
        return {
            "success": True,
            "message": message,
            "net_balance": balance,
            "status": balance_data["status"]
        }
        
    except Exception as e:
        logger.error(f"Failed to get expense balance: {e}")
        return {"success": False, "error": f"Failed to get expense balance: {str(e)}"}

def settle_payments(chat_id: str, expense_ids: Optional[str] = None):
    """
    Mark expenses as settled - either all or specific ones.
    
    Args:
        chat_id: WhatsApp chat ID
        expense_ids: Comma-separated list of expense IDs to settle. If None, settles all expenses.
    
    Returns:
        dict: Settlement result with success status and message
    """
    try:
        # Parse expense IDs if provided
        parsed_expense_ids = None
        if expense_ids:
            parsed_expense_ids = [id.strip() for id in expense_ids.split(',')]
        
        result = ExpenseSettlementService.settle_payments(chat_id, parsed_expense_ids)
        return result
        
    except Exception as e:
        logger.error(f"Failed to settle payments: {e}")
        return {"success": False, "error": f"Failed to settle payments: {str(e)}"}

def get_expense_history(chat_id: str, limit: int = 5):
    """
    Get recent expense history for a group chat.
    
    Args:
        chat_id: WhatsApp chat ID
        limit: Number of recent expenses to return
    
    Returns:
        dict: List of recent expenses
    """
    try:
        expenses = ExpenseSettlementService.get_expense_history(chat_id, limit)
        
        if not expenses:
            return {
                "success": True,
                "message": "📋 No expenses found in this chat."
            }
        
        message = f"📋 Recent Expenses ({len(expenses)} of {limit}):\n\n"
        
        for i, expense in enumerate(expenses, 1):
            message += f"{i}. ${expense['total_amount']:.2f} - {expense['description']}\n"
            message += f"   👤 Paid by: {expense['payer_name']}\n"
            message += f"   📅 Date: {expense['created_at'].strftime('%Y-%m-%d')}\n"
            message += f"   👥 Split among {len(expense['participants'])} people\n\n"
        
        return {
            "success": True,
            "message": message,
            "expenses": expenses
        }
        
    except Exception as e:
        logger.error(f"Failed to get expense history: {e}")
        return {"success": False, "error": f"Failed to get expense history: {str(e)}"}

def switch_mode(chat_id: str, mode: str):
    try:
        # Convert string to AIMode enum
        ai_mode = AIMode[mode]
        
        ConversationModel.update_by_id(
            convo_id=chat_id,
            update_fields={"mode": ai_mode.value},
            type="$set"
        )
        return {
            "success": True,
            "message": f"Mode switched to {ai_mode.value} successfully. All future messages will use this mode."
        }
    except ValueError as e:
        logger.error(f"Invalid mode provided: {mode}")
        return {"success": False, "error": f"Invalid mode '{mode}'. Available modes: {[m.value for m in AIMode]}"}
    except Exception as e:
        logger.error(f"Failed to switch conversation mode: {e}")
        return {"success": False, "error": f"Failed to switch mode: {str(e)}"}