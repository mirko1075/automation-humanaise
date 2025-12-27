# ingestors/mail/base_client.py
"""
BaseMailClient: Abstract interface for mail clients (IMAP, Graph, etc).
"""
from abc import ABC, abstractmethod
from typing import Iterable
from ingestors.imap.models import RawEmail

class BaseMailClient(ABC):
    @abstractmethod
    def connect(self):
        """Establish connection to mail provider."""
        pass

    @abstractmethod
    def fetch_messages(self) -> Iterable[RawEmail]:
        """Yield RawEmail objects from the mailbox."""
        pass

    @abstractmethod
    def disconnect(self):
        """Clean up resources and close connection."""
        pass
