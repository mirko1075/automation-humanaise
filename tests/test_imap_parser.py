from ingestors.imap.parser import parse_rfc822
from ingestors.imap.models import Attachment

def test_parse_plain_and_html_and_attachment():
    # Build a multipart message with text/plain, text/html and an attachment
    from email.message import EmailMessage
    msg = EmailMessage()
    msg['Subject'] = 'Test'
    msg['From'] = 'a@example.com'
    msg['To'] = 'b@example.com'
    msg.set_content('This is plain text')
    msg.add_alternative('<p>This is <b>HTML</b></p>', subtype='html')
    # Add attachment
    msg.add_attachment(b'filebytes', maintype='application', subtype='octet-stream', filename='file.bin')

    raw = msg.as_bytes()
    parsed = parse_rfc822(raw, tenant_id='t1', mailbox='INBOX', uid=123, uidvalidity='v1')

    assert parsed.text is not None and 'plain text' in parsed.text
    assert parsed.html is not None and '<b>HTML</b>' in parsed.html
    assert len(parsed.attachments) == 1
    a = parsed.attachments[0]
    assert isinstance(a, Attachment)
    assert a.filename == 'file.bin'
