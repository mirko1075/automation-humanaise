# app/workers/graph_mail_poller.py
"""
Graph Mail Poller Worker

Production-ready background worker for Microsoft Graph email polling.

- Runs as a Render Background Worker or standalone process
- Uses GraphMailClient and MailPoller (provider-agnostic)
- Reads configuration from environment variables
- Handles SIGTERM/SIGINT for graceful shutdown
- Logs startup, shutdown, and poll cycles

Usage:
    python -m app.workers.graph_mail_poller

Required environment variables:
    TENANT_ID
    GRAPH_USER_PRINCIPAL_NAME
    POLL_INTERVAL_SECONDS (default: 60)
    DATABASE_URL
    N8N_WEBHOOK_URL
    LOG_LEVEL
"""
import os
import signal
import sys
import logging
from time import sleep

from ingestors.graph.graph_mail_client import GraphMailClient
from ingestors.imap.poller import MailPoller
from app.logging import configure_logging

# Ensure logging is configured for standalone workers
configure_logging()
logger = logging.getLogger(__name__)

shutdown_flag = False

def handle_shutdown(signum, frame):
    global shutdown_flag
    logger.info(f"Received shutdown signal ({signum}), exiting after current poll cycle...")
    shutdown_flag = True

def main():
    tenant_id = os.environ.get("TENANT_ID")
    user_principal_name = os.environ.get("GRAPH_USER_PRINCIPAL_NAME")
    interval = int(os.environ.get("POLL_INTERVAL_SECONDS", "60"))

    if not tenant_id or not user_principal_name:
        logger.error("TENANT_ID and GRAPH_USER_PRINCIPAL_NAME must be set in environment.")
        sys.exit(1)

    logger.info("Starting Graph Mail Poller worker", extra={
        "tenant_id": tenant_id,
        "user_principal_name": user_principal_name,
        "interval": interval
    })

    client = GraphMailClient(user_principal_name=user_principal_name, mailbox="Inbox")
    poller = MailPoller(tenant_id=tenant_id, mail_client=client, interval_seconds=interval)

    # Register signal handlers
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    try:
        while not shutdown_flag:
            poller.run_once()
            if not shutdown_flag:
                sleep(interval)
    except Exception:
        logger.exception("Fatal error in polling loop")
    finally:
        logger.info("Graph Mail Poller worker shutting down.")

if __name__ == "__main__":
    main()
