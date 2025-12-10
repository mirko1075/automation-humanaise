# app/scheduler/scheduler.py
"""
SchedulerEngine for Edilcos Automation Backend.
Configures APScheduler and manages job lifecycle.
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.scheduler.jobs import (
    process_pending_notifications,
    process_excel_update_queue,
    process_quote_reminders,
    process_daily_health_report
)
import logging

scheduler: AsyncIOScheduler = None

async def start_scheduler(app):
    global scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(process_pending_notifications, "interval", minutes=2)
    scheduler.add_job(process_excel_update_queue, "interval", minutes=5)
    scheduler.add_job(process_quote_reminders, "interval", hours=6)
    scheduler.add_job(process_daily_health_report, "cron", hour=7)
    scheduler.start()
    app.state.scheduler = scheduler
    logging.info("Scheduler started.")

async def shutdown_scheduler(app):
    global scheduler
    if scheduler:
        scheduler.shutdown(wait=False)
        logging.info("Scheduler shutdown.")
