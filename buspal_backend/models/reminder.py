from buspal_backend.db.mongo import db
import datetime
from typing import Optional, List, Dict, Any, Union

class ReminderModel:
    collection = db.reminders

    @classmethod
    def create(cls, reminder_id: str, chat_id: str, message: str, scheduled_time: datetime.datetime, 
               recurrence_pattern: Optional[str] = None, status: str = "scheduled"):
        """
        Create a new reminder in the database.
        
        Args:
            reminder_id: Unique identifier for the reminder
            chat_id: WhatsApp chat ID to send reminder to
            message: Reminder message text
            scheduled_time: When to send the reminder (UTC)
            recurrence_pattern: Optional recurrence pattern (daily, weekly, monthly)
            status: Reminder status (scheduled, sent, failed, cancelled)
        
        Returns:
            dict: Created reminder document
        """
        reminder = {
            "_id": reminder_id,
            "chat_id": chat_id,
            "message": message,
            "scheduled_time": scheduled_time,
            "recurrence_pattern": recurrence_pattern,
            "status": status,
            "created_at": datetime.datetime.utcnow(),
            "updated_at": datetime.datetime.utcnow()
        }
        cls.collection.insert_one(reminder)
        return reminder

    @classmethod
    def get_by_id(cls, reminder_id: str) -> Optional[Dict[str, Any]]:
        """Get a reminder by its ID."""
        return cls.collection.find_one({"_id": reminder_id})

    @classmethod
    def get_by_chat_id(cls, chat_id: str, status: Optional[Union[str, List[str]]] = None) -> List[Dict[str, Any]]:
        """
        Get reminders for a specific chat.
        
        Args:
            chat_id: WhatsApp chat ID
            status: Optional status filter
        
        Returns:
            List of reminder documents
        """
        query = {"chat_id": chat_id}

        if isinstance(status, list):
          query["status"] = {"$in": status}
        elif isinstance(status, str):
            query["status"] = status
        
        return list(cls.collection.find(query).sort("scheduled_time", 1))

    @classmethod
    def get_due_reminders(cls, current_time: datetime.datetime = None) -> List[Dict[str, Any]]:
        """
        Get reminders that are due to be sent.
        
        Args:
            current_time: Current UTC time (defaults to now)
        
        Returns:
            List of due reminder documents
        """
        if current_time is None:
            current_time = datetime.datetime.utcnow()
        
        return list(cls.collection.find({
            "scheduled_time": {"$lte": current_time},
            "status": "scheduled"
        }).sort("scheduled_time", 1))

    @classmethod
    def update_by_id(cls, reminder_id: str, update_fields: Dict[str, Any], 
                     operation: str = "$set") -> bool:
        """
        Update a reminder by its ID.
        
        Args:
            reminder_id: Reminder ID to update
            update_fields: Fields to update
            operation: MongoDB update operation (default: $set)
        
        Returns:
            bool: True if update was successful
        """
        update_fields["updated_at"] = datetime.datetime.utcnow()
        
        result = cls.collection.update_one(
            {"_id": reminder_id},
            {operation: update_fields}
        )
        return result.modified_count > 0

    @classmethod
    def cancel_reminder(cls, reminder_id: str) -> bool:
        """
        Cancel a scheduled reminder.
        
        Args:
            reminder_id: Reminder ID to cancel
        
        Returns:
            bool: True if cancellation was successful
        """
        return cls.update_by_id(reminder_id, {
            "status": "cancelled",
            "cancelled_at": datetime.datetime.utcnow()
        })

    @classmethod
    def mark_as_sent(cls, reminder_id: str) -> bool:
        """
        Mark a reminder as sent.
        
        Args:
            reminder_id: Reminder ID to mark as sent
        
        Returns:
            bool: True if update was successful
        """
        return cls.update_by_id(reminder_id, {
            "status": "sent",
            "sent_at": datetime.datetime.utcnow()
        })

    @classmethod
    def mark_as_failed(cls, reminder_id: str, error: str) -> bool:
        """
        Mark a reminder as failed.
        
        Args:
            reminder_id: Reminder ID to mark as failed
            error: Error message
        
        Returns:
            bool: True if update was successful
        """
        return cls.update_by_id(reminder_id, {
            "status": "failed",
            "error": error,
            "failed_at": datetime.datetime.utcnow()
        })

    @classmethod
    def delete_by_id(cls, reminder_id: str) -> bool:
        """
        Delete a reminder by its ID.
        
        Args:
            reminder_id: Reminder ID to delete
        
        Returns:
            bool: True if deletion was successful
        """
        result = cls.collection.delete_one({"_id": reminder_id})
        return result.deleted_count > 0

    @classmethod
    def get_pending_reminders_due_soon(cls, days_ahead: int = 7) -> List[Dict[str, Any]]:
        """
        Get pending reminders that are due within the specified number of days.
        These are candidates for moving to Service Bus.
        
        Args:
            days_ahead: Number of days to look ahead (default: 7)
        
        Returns:
            List of pending reminder documents due within the timeframe
        """
        cutoff_time = datetime.datetime.utcnow() + datetime.timedelta(days=days_ahead)
        
        return list(cls.collection.find({
            "status": "pending",
            "scheduled_time": {"$lte": cutoff_time}
        }).sort("scheduled_time", 1))

    @classmethod
    def move_to_service_bus(cls, reminder_id: str, service_bus_message_id: str = None) -> bool:
        """
        Mark a pending reminder as scheduled in Service Bus.
        
        Args:
            reminder_id: Reminder ID to update
            service_bus_message_id: Optional Service Bus message ID for tracking
        
        Returns:
            bool: True if update was successful
        """
        update_fields = {
            "status": "scheduled",
            "moved_to_service_bus_at": datetime.datetime.utcnow()
        }
        
        if service_bus_message_id:
            update_fields["service_bus_message_id"] = service_bus_message_id
        
        return cls.update_by_id(reminder_id, update_fields)

    @classmethod
    def get_overdue_pending_reminders(cls) -> List[Dict[str, Any]]:
        """
        Get pending reminders that are already overdue (should have been sent).
        These need to be processed immediately.
        
        Returns:
            List of overdue pending reminder documents
        """
        current_time = datetime.datetime.utcnow()
        
        return list(cls.collection.find({
            "status": "pending",
            "scheduled_time": {"$lte": current_time}
        }).sort("scheduled_time", 1))

    @classmethod
    def cleanup_old_reminders(cls, days_old: int = 30) -> int:
        """
        Clean up old completed/failed reminders.
        
        Args:
            days_old: Remove reminders older than this many days
        
        Returns:
            int: Number of reminders deleted
        """
        cutoff_date = datetime.datetime.utcnow() - datetime.timedelta(days=days_old)
        
        result = cls.collection.delete_many({
            "status": {"$in": ["sent", "failed", "cancelled"]},
            "updated_at": {"$lt": cutoff_date}
        })
        
        return result.deleted_count