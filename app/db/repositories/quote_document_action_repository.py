from app.integrations.onedrive_api import QuoteDocumentAction
from sqlalchemy import select

class QuoteDocumentActionRepository:
    def __init__(self, db):
        self.db = db

    async def list_pending(self):
        q = await self.db.execute(select(QuoteDocumentAction).where(QuoteDocumentAction.status == 'PENDING'))
        return q.scalars().all()

    async def update(self, action_id, **kwargs):
        obj = await self.db.get(QuoteDocumentAction, action_id)
        for k, v in kwargs.items():
            setattr(obj, k, v)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj
