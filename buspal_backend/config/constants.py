from buspal_backend.services.ai.tools import tools

TOOLS_MAP = {
  "send_reaction": tools.send_reaction,
  "schedule_reminder": tools.schedule_reminder,
  "get_scheduled_reminders": tools.get_scheduled_reminders,
  "cancel_reminder": tools.cancel_reminder,
  "add_expense": tools.add_expense,
  "calculate_expense_settlement": tools.calculate_expense_settlement,
  "get_expense_balance": tools.get_expense_balance,
  "get_expense_history": tools.get_expense_history,
  "settle_payments": tools.settle_payments,
  "switch_conversation_mode": tools.switch_mode,
}
