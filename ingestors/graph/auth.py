# ingestors/graph/auth.py
"""
GraphAuthProvider: Handles Microsoft Graph OAuth2 authentication using msal.
"""
import os
import msal
from app.config import settings

class GraphAuthProvider:
    def __init__(self):
        self.tenant_id = os.getenv("GRAPH_TENANT_ID") or getattr(settings, "GRAPH_TENANT_ID", None)
        self.client_id = os.getenv("GRAPH_CLIENT_ID") or getattr(settings, "GRAPH_CLIENT_ID", None)
        self.client_secret = os.getenv("GRAPH_CLIENT_SECRET") or getattr(settings, "GRAPH_CLIENT_SECRET", None)
        self._app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}",
            client_credential=self.client_secret,
        )
        self._token_cache = None

    def get_access_token(self) -> str:
        scope = ["https://graph.microsoft.com/.default"]
        result = self._app.acquire_token_silent(scope, account=None)
        if not result:
            result = self._app.acquire_token_for_client(scopes=scope)
        if not result or "access_token" not in result:
            raise RuntimeError(f"Failed to obtain Graph access token: {result}")
        return result["access_token"]
