import azure.functions as func

from buspal_backend import app as fastapi_app
from reminder_processor import main as reminder_processor
from daily_reminder_scheduler import main as daily_scheduler

app = func.AsgiFunctionApp(app=fastapi_app, http_auth_level=func.AuthLevel.ANONYMOUS)

# Service Bus trigger for processing reminders
@app.service_bus_queue_trigger(
    arg_name="msg", 
    queue_name="reminders",
    connection="SERVICEBUSCONNSTR_AZURE_SERVICE_BUS_CONNECTION_STRING"
)
async def process_reminder(msg: func.ServiceBusMessage) -> None:
    """Process reminder messages from Service Bus queue"""
    await reminder_processor(msg)

#Daily timer for moving long-term reminders to Service Bus
@app.timer_trigger(
    schedule="0 0 6 * * *",  # Daily at 6:00 AM UTC (9:00 AM Beirut time)
    arg_name="mytimer", 
    run_on_startup=False,
    use_monitor=False
) 
def daily_reminder_scheduler(mytimer: func.TimerRequest) -> None:
    """Daily scheduler for processing long-term reminders"""
    daily_scheduler(mytimer)