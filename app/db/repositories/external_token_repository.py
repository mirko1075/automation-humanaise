# app/db/repositories/external_token_repository.py
"""
CRUD operations for ExternalToken model.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.models import ExternalToken
from uuid import UUID
from typing import Optional, List
from sqlalchemy import insert, update, select as sa_select
from sqlalchemy.dialects.postgresql import insert as pg_insert
import structlog

logger = structlog.get_logger()
from types import SimpleNamespace

class ExternalTokenRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, tenant_id: UUID, flow_id: Optional[str], provider: str, token: str, external_id: Optional[str] = None, data: Optional[dict] = None) -> ExternalToken:
        """Create a new ExternalToken record.

        Args:
            tenant_id: tenant UUID or None
            flow_id: optional flow id
            provider: provider name (e.g. 'google')
            token: access token
            external_id: optional external identifier (email or external user id)
            data: optional JSON blob for extra token data (refresh_token, expires_at)
        """
        ext_token = ExternalToken(
            tenant_id=tenant_id,
            flow_id=flow_id,
            provider=provider,
            external_id=external_id,
            data=data,
            token=token
        )
        self.db.add(ext_token)
        await self.db.commit()
        await self.db.refresh(ext_token)
        return SimpleNamespace(
            id=ext_token.id,
            tenant_id=ext_token.tenant_id,
            provider=ext_token.provider,
            token=ext_token.token,
            external_id=ext_token.external_id,
            data=ext_token.data,
        )

    async def get(self, token_id: UUID) -> Optional[ExternalToken]:
        result = await self.db.execute(select(ExternalToken).where(ExternalToken.id == token_id))
        row = result.scalar_one_or_none()
        if not row:
            return None
        return SimpleNamespace(
            id=row.id,
            tenant_id=row.tenant_id,
            provider=row.provider,
            token=row.token,
            external_id=row.external_id,
            data=row.data,
        )

    async def list_by_tenant(self, tenant_id: UUID) -> List[ExternalToken]:
        result = await self.db.execute(select(ExternalToken).where(ExternalToken.tenant_id == tenant_id))
        rows = result.scalars().all()
        return [
            SimpleNamespace(
                id=r.id,
                tenant_id=r.tenant_id,
                provider=r.provider,
                token=r.token,
                external_id=r.external_id,
                data=r.data,
            )
            for r in rows
        ]

    async def list_by_external_id(self, external_id: str) -> List[ExternalToken]:
        result = await self.db.execute(select(ExternalToken).where(ExternalToken.external_id == external_id))
        rows = result.scalars().all()
        return [
            SimpleNamespace(
                id=r.id,
                tenant_id=r.tenant_id,
                provider=r.provider,
                token=r.token,
                external_id=r.external_id,
                data=r.data,
            )
            for r in rows
        ]

    async def update(self, token_id: UUID, **kwargs) -> Optional[ExternalToken]:
        # Load ORM instance to perform updates
        result = await self.db.execute(select(ExternalToken).where(ExternalToken.id == token_id))
        ext_token = result.scalar_one_or_none()
        if not ext_token:
            return None
        for key, value in kwargs.items():
            setattr(ext_token, key, value)
        await self.db.commit()
        await self.db.refresh(ext_token)
        return SimpleNamespace(
            id=ext_token.id,
            tenant_id=ext_token.tenant_id,
            provider=ext_token.provider,
            token=ext_token.token,
            external_id=ext_token.external_id,
            data=ext_token.data,
        )

    async def delete(self, token_id: UUID) -> bool:
        ext_token = await self.get(token_id)
        if not ext_token:
            return False
        await self.db.delete(ext_token)
        await self.db.commit()
        return True

    async def upsert(self, tenant_id: UUID, flow_id: Optional[str], provider: str, token: str, external_id: Optional[str] = None, data: Optional[dict] = None):
        """Atomically insert or update an ExternalToken row keyed by (tenant_id, provider).

        Uses Postgres ON CONFLICT when available; otherwise falls back to read-then-write.
        Returns the ExternalToken instance after write.
        """
        # If we're connected to PostgreSQL and the unique constraint exists,
        # attempt an atomic INSERT ... ON CONFLICT upsert. Otherwise fall back
        # to read-then-update which works across DB backends.
        try:
            dialect = getattr(self.db.bind, "dialect", None)
        except Exception:
            dialect = None

        # If connected to Postgres, attempt an atomic INSERT ... ON CONFLICT.
        # If it fails (for example because the unique constraint doesn't exist),
        # rollback and fall back to read-then-update.
        did_on_conflict = False
        if dialect is not None and getattr(dialect, "name", "") == "postgresql":
            try:
                stmt = pg_insert(ExternalToken).values(
                    tenant_id=tenant_id,
                    flow_id=flow_id,
                    provider=provider,
                    external_id=external_id,
                    data=data,
                    token=token,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=[ExternalToken.tenant_id, ExternalToken.provider],
                    set_={
                        "token": pg_insert(ExternalToken).excluded.token,
                        "external_id": external_id,
                        "data": data,
                        "flow_id": flow_id,
                    }
                )
                await self.db.execute(stmt)
                await self.db.commit()
                did_on_conflict = True
            except Exception as e:
                try:
                    await self.db.rollback()
                except Exception:
                    pass
                logger.debug("upsert_postgres_failed", provider=provider, tenant_id=str(tenant_id), error=str(e))

        if not did_on_conflict:
            try:
                existing_id = None
                if tenant_id:
                    res = await self.db.execute(
                        select(ExternalToken.id).where(
                            ExternalToken.tenant_id == tenant_id,
                            ExternalToken.provider == provider,
                        )
                    )
                    existing_id = res.scalar_one_or_none()

                if not existing_id and external_id:
                    res = await self.db.execute(
                        select(ExternalToken.id).where(
                            ExternalToken.external_id == external_id,
                            ExternalToken.provider == provider,
                        )
                    )
                    existing_id = res.scalar_one_or_none()

                if existing_id:
                    await self.db.execute(
                        update(ExternalToken)
                        .where(ExternalToken.id == existing_id)
                        .values(token=token, external_id=external_id, data=data, flow_id=flow_id)
                    )
                    await self.db.commit()
                    res = await self.db.execute(
                        sa_select(
                            ExternalToken.id,
                            ExternalToken.tenant_id,
                            ExternalToken.provider,
                            ExternalToken.token,
                            ExternalToken.external_id,
                            ExternalToken.data,
                        ).where(ExternalToken.id == existing_id)
                    )
                    mapping = res.mappings().first()
                    if mapping:
                        return SimpleNamespace(**mapping)
                else:
                    return await self.create(tenant_id=tenant_id, flow_id=flow_id, provider=provider, token=token, external_id=external_id, data=data)
            except Exception:
                try:
                    await self.db.rollback()
                except Exception:
                    pass

        # Return fresh row by querying and converting to a plain object to avoid
        # any lazy-loading or greenlet-related IO when the caller accesses attrs.
        if tenant_id:
            res = await self.db.execute(
                select(ExternalToken).where(
                    ExternalToken.tenant_id == tenant_id,
                    ExternalToken.provider == provider,
                )
            )
            row = res.scalar_one_or_none()
            if row:
                return SimpleNamespace(
                    id=row.id,
                    tenant_id=row.tenant_id,
                    provider=row.provider,
                    token=row.token,
                    external_id=row.external_id,
                    data=row.data,
                )
        if external_id:
            res = await self.db.execute(
                select(ExternalToken).where(
                    ExternalToken.external_id == external_id,
                    ExternalToken.provider == provider,
                )
            )
            row = res.scalar_one_or_none()
            if row:
                return SimpleNamespace(
                    id=row.id,
                    tenant_id=row.tenant_id,
                    provider=row.provider,
                    token=row.token,
                    external_id=row.external_id,
                    data=row.data,
                )
        return None
