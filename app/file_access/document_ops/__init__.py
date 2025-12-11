# app/file_access/document_ops/__init__.py
"""
Protocol-agnostic document operations.

This module provides document manipulation functions that work
with any FileStorageProvider implementation, operating on bytes
without needing to know the underlying storage protocol.
"""

from app.file_access.document_ops.excel_ops import (
    read_excel,
    write_excel,
    update_excel,
    create_excel_from_data
)
from app.file_access.document_ops.pdf_ops import (
    read_pdf_text,
    create_pdf,
    merge_pdfs,
    extract_pdf_metadata
)
from app.file_access.document_ops.word_ops import (
    read_word,
    create_word,
    update_word
)

__all__ = [
    # Excel operations
    "read_excel",
    "write_excel",
    "update_excel",
    "create_excel_from_data",
    # PDF operations
    "read_pdf_text",
    "create_pdf",
    "merge_pdfs",
    "extract_pdf_metadata",
    # Word operations
    "read_word",
    "create_word",
    "update_word",
]
