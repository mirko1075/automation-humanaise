from app.logging import configure_logging
import logging

configure_logging()
logger = logging.getLogger(__name__)

logger.info("INIT GRAPH AUTH")
logger.info("INIT GRAPH MAIL CLIENT")
logger.info("CONNECT")
logger.info("FETCH MESSAGES")
# test_graph_mail.py
from ingestors.graph.auth import GraphAuthProvider
from ingestors.graph.graph_mail_client import GraphMailClient

print("INIT GRAPH AUTH")
auth = GraphAuthProvider()

    logger.info("INIT GRAPH MAIL CLIENT")
client = GraphMailClient(
    user_principal_name="mirko.siddi@humanaise.com",
    mailbox="Inbox",
)

    logger.info("CONNECT")
client.connect()

    logger.info("FETCH MESSAGES")
messages = list(client.fetch_messages())

    logger.info("MESSAGES FETCHED: %d", len(messages))
for m in messages[:3]:
    print("----")
        logger.debug("----")
        logger.debug("SUBJECT: %s", m.subject)
        logger.debug("FROM: %s", m.from_)
        logger.debug("ID: %s", getattr(m, "message_id", getattr(m, "id", "N/A")))
