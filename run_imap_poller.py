from ingestors.imap.poller import IMAPPoller

from app.logging import configure_logging
import logging

configure_logging()
logger = logging.getLogger(__name__)

logger.info("STARTING IMAP POLLER")

poller = IMAPPoller(
    tenant_id="edilcos",
    mailbox="INBOX",
)

poller.run_forever()
