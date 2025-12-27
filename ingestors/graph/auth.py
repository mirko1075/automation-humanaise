# ingestors/graph/auth.py
"""
GraphAuthProvider: Handles Microsoft Graph OAuth2 authentication using msal.
"""
import os
import msal
from app.config import settings

class GraphAuthProvider:
    def __init__(self):
        # Allow either GRAPH_TENANT_ID or the generic TENANT_ID to be set in environment
        self.tenant_id = (
            os.getenv("GRAPH_TENANT_ID")
            or os.getenv("TENANT_ID")
            or getattr(settings, "GRAPH_TENANT_ID", None)
            or getattr(settings, "TENANT_ID", None)
        )

        self.client_id = (
            os.getenv("GRAPH_CLIENT_ID") or getattr(settings, "GRAPH_CLIENT_ID", None)
        )
        self.client_secret = (
            os.getenv("GRAPH_CLIENT_SECRET") or getattr(settings, "GRAPH_CLIENT_SECRET", None)
        )

        # Validate required credentials before initializing msal to produce clearer errors
        missing = []
        if not self.tenant_id:
            missing.append("GRAPH_TENANT_ID or TENANT_ID")
        if not self.client_id:
            missing.append("GRAPH_CLIENT_ID")
        if not self.client_secret:
            missing.append("GRAPH_CLIENT_SECRET")
        if missing:
            raise RuntimeError(
                "Missing Microsoft Graph credentials: " + ", ".join(missing) + ". "
                "Set these environment variables or configure them in app.config.settings."
            )

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
