from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

flow = InstalledAppFlow.from_client_secrets_file(
    "google_oauth.json",
    SCOPES
)

creds = flow.run_local_server(port=0)

service = build("gmail", "v1", credentials=creds)

response = service.users().watch(
    userId="me",
    body={
        "topicName": "projects/automationhumanaise/topics/gmail-incoming-events",
        "labelIds": ["INBOX"]
    }
).execute()

print("WATCH RESPONSE:", response)
