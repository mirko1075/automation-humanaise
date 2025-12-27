# test_graph_mail.py
from ingestors.graph.auth import GraphAuthProvider
from ingestors.graph.graph_mail_client import GraphMailClient

print("INIT GRAPH AUTH")
auth = GraphAuthProvider()

print("INIT GRAPH MAIL CLIENT")
client = GraphMailClient(
    user_principal_name="mirko.siddi@humanaise.com",
    mailbox="Inbox",
)

print("CONNECT")
client.connect()

print("FETCH MESSAGES")
messages = list(client.fetch_messages())

print("MESSAGES FETCHED:", len(messages))
for m in messages[:3]:
    print("----")
    print("SUBJECT:", m.subject)
    print("FROM:", m.from_)
    print("ID:", getattr(m, "message_id", getattr(m, "id", "N/A")))
