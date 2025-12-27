from ingestors.imap.poller import IMAPPoller

print("STARTING IMAP POLLER")

poller = IMAPPoller(
    tenant_id="edilcos",
    mailbox="INBOX",
)

poller.run_forever()
