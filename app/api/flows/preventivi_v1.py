# app/api/flows/preventivi_v1.py
"""
API router for PreventiviV1 flow (optional endpoints).
"""
from fastapi import APIRouter
from app.core.preventivi_service import process_normalized_event

router = APIRouter(prefix="/flows/preventivi_v1", tags=["flows"])

# No direct endpoints required for MVP; FlowRouter calls process_normalized_event directly.
# You may add admin/test endpoints here if needed.
