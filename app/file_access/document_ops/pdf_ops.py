# app/file_access/document_ops/pdf_ops.py
"""
Protocol-agnostic PDF operations.

All functions take a FileStorageProvider and operate on bytes,
making them work with any storage backend (local, SMB, NFS, etc.).
"""
import io
from typing import Any, Dict, List, Optional
from datetime import datetime

import structlog

from app.file_access.base_fs import FileStorageProvider

# PDF library imports
try:
    from pypdf import PdfReader, PdfWriter, PdfMerger
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False
    logger = structlog.get_logger()
    logger.warning("pypdf_not_available", message="Install pypdf for PDF operations: pip install pypdf")

# For PDF generation from HTML/text
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.units import inch
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

logger = structlog.get_logger()


async def read_pdf_text(
    provider: FileStorageProvider,
    path: str
) -> str:
    """
    Extract text from PDF file.
    
    Args:
        provider: FileStorageProvider instance (connected)
        path: Path to PDF file
        
    Returns:
        Extracted text content
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ImportError: If pypdf is not installed
    """
    if not PYPDF_AVAILABLE:
        raise ImportError("pypdf is required for PDF operations. Install: pip install pypdf")
    
    try:
        logger.debug("reading_pdf_text", path=path)
        
        # Read PDF bytes from provider
        data = await provider.read_file(path)
        
        # Load PDF
        buffer = io.BytesIO(data)
        reader = PdfReader(buffer)
        
        # Extract text from all pages
        text_parts = []
        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text()
            text_parts.append(text)
            logger.debug("pdf_page_extracted", page=page_num, length=len(text))
        
        full_text = "\n\n".join(text_parts)
        
        logger.info("pdf_text_extracted", path=path, pages=len(reader.pages), length=len(full_text))
        return full_text
        
    except Exception as e:
        logger.error("pdf_text_extraction_failed", path=path, error=str(e))
        raise


async def extract_pdf_metadata(
    provider: FileStorageProvider,
    path: str
) -> Dict[str, Any]:
    """
    Extract metadata from PDF file.
    
    Args:
        provider: FileStorageProvider instance (connected)
        path: Path to PDF file
        
    Returns:
        Dictionary with PDF metadata
        
    Example result:
        {
            "title": "Document Title",
            "author": "Author Name",
            "subject": "Document Subject",
            "creator": "Creator App",
            "producer": "PDF Producer",
            "creation_date": "2024-01-15T10:30:00",
            "modification_date": "2024-01-16T14:20:00",
            "pages": 10,
            "encrypted": False
        }
    """
    if not PYPDF_AVAILABLE:
        raise ImportError("pypdf is required for PDF operations. Install: pip install pypdf")
    
    try:
        logger.debug("reading_pdf_metadata", path=path)
        
        # Read PDF bytes
        data = await provider.read_file(path)
        buffer = io.BytesIO(data)
        reader = PdfReader(buffer)
        
        # Extract metadata
        metadata = {}
        if reader.metadata:
            metadata["title"] = reader.metadata.get("/Title", "")
            metadata["author"] = reader.metadata.get("/Author", "")
            metadata["subject"] = reader.metadata.get("/Subject", "")
            metadata["creator"] = reader.metadata.get("/Creator", "")
            metadata["producer"] = reader.metadata.get("/Producer", "")
            
            # Parse dates if available
            creation_date = reader.metadata.get("/CreationDate")
            if creation_date:
                metadata["creation_date"] = _parse_pdf_date(creation_date)
            
            mod_date = reader.metadata.get("/ModDate")
            if mod_date:
                metadata["modification_date"] = _parse_pdf_date(mod_date)
        
        metadata["pages"] = len(reader.pages)
        metadata["encrypted"] = reader.is_encrypted
        
        logger.info("pdf_metadata_extracted", path=path, metadata=metadata)
        return metadata
        
    except Exception as e:
        logger.error("pdf_metadata_extraction_failed", path=path, error=str(e))
        raise


def _parse_pdf_date(pdf_date: str) -> Optional[str]:
    """
    Parse PDF date format (D:YYYYMMDDHHmmSS) to ISO format.
    
    Args:
        pdf_date: PDF date string
        
    Returns:
        ISO format date string or None
    """
    try:
        # PDF date format: D:YYYYMMDDHHmmSS+HH'mm'
        if pdf_date.startswith("D:"):
            pdf_date = pdf_date[2:]
        
        # Extract date parts
        year = int(pdf_date[0:4])
        month = int(pdf_date[4:6])
        day = int(pdf_date[6:8])
        hour = int(pdf_date[8:10]) if len(pdf_date) >= 10 else 0
        minute = int(pdf_date[10:12]) if len(pdf_date) >= 12 else 0
        second = int(pdf_date[12:14]) if len(pdf_date) >= 14 else 0
        
        dt = datetime(year, month, day, hour, minute, second)
        return dt.isoformat()
        
    except Exception:
        return None


async def merge_pdfs(
    provider: FileStorageProvider,
    source_paths: List[str],
    destination_path: str,
    overwrite: bool = False
) -> bool:
    """
    Merge multiple PDF files into one.
    
    Args:
        provider: FileStorageProvider instance (connected)
        source_paths: List of PDF file paths to merge
        destination_path: Output PDF path
        overwrite: Whether to overwrite existing file
        
    Returns:
        True if successful
        
    Example:
        await merge_pdfs(
            provider,
            ["/docs/part1.pdf", "/docs/part2.pdf", "/docs/part3.pdf"],
            "/docs/combined.pdf"
        )
    """
    if not PYPDF_AVAILABLE:
        raise ImportError("pypdf is required for PDF operations. Install: pip install pypdf")
    
    try:
        logger.debug("merging_pdfs", sources=source_paths, destination=destination_path)
        
        merger = PdfMerger()
        
        # Read and append each PDF
        for source_path in source_paths:
            data = await provider.read_file(source_path)
            buffer = io.BytesIO(data)
            merger.append(buffer)
            logger.debug("pdf_appended", source=source_path)
        
        # Write merged PDF
        output_buffer = io.BytesIO()
        merger.write(output_buffer)
        merged_data = output_buffer.getvalue()
        merger.close()
        
        # Save to provider
        result = await provider.write_file(destination_path, merged_data, overwrite=overwrite)
        
        if result.success:
            logger.info("pdfs_merged", sources=len(source_paths), destination=destination_path, size=len(merged_data))
            return True
        else:
            logger.error("pdf_merge_write_failed", error=result.error)
            raise Exception(f"Failed to write merged PDF: {result.error}")
            
    except Exception as e:
        logger.error("pdf_merge_failed", error=str(e))
        raise


async def create_pdf(
    provider: FileStorageProvider,
    path: str,
    content: str,
    overwrite: bool = False,
    page_size: str = "A4",
    title: Optional[str] = None
) -> bool:
    """
    Create simple PDF from text content.
    
    Requires reportlab: pip install reportlab
    
    Args:
        provider: FileStorageProvider instance (connected)
        path: Destination PDF path
        content: Text content (supports line breaks)
        overwrite: Whether to overwrite existing file
        page_size: Page size ("A4" or "letter")
        title: PDF title metadata
        
    Returns:
        True if successful
        
    Example:
        content = '''
        Quote #Q001
        Customer: ACME Corp
        Amount: $1,000.00
        
        Items:
        - Product A: $500.00
        - Product B: $500.00
        '''
        
        await create_pdf(
            provider,
            "/quotes/Q001.pdf",
            content,
            title="Quote Q001"
        )
    """
    if not REPORTLAB_AVAILABLE:
        raise ImportError("reportlab is required for PDF creation. Install: pip install reportlab")
    
    try:
        logger.debug("creating_pdf", path=path, title=title)
        
        # Create PDF in memory
        buffer = io.BytesIO()
        
        # Set page size
        if page_size.upper() == "A4":
            size = A4
        else:
            size = letter
        
        c = canvas.Canvas(buffer, pagesize=size)
        
        # Set title
        if title:
            c.setTitle(title)
        
        # Write content
        width, height = size
        y_position = height - inch  # Start 1 inch from top
        
        lines = content.split("\n")
        for line in lines:
            if y_position < inch:  # New page if near bottom
                c.showPage()
                y_position = height - inch
            
            c.drawString(inch, y_position, line)
            y_position -= 14  # Line height
        
        c.save()
        pdf_data = buffer.getvalue()
        
        # Save to provider
        result = await provider.write_file(path, pdf_data, overwrite=overwrite)
        
        if result.success:
            logger.info("pdf_created", path=path, size=len(pdf_data))
            return True
        else:
            logger.error("pdf_create_write_failed", error=result.error)
            raise Exception(f"Failed to write PDF: {result.error}")
            
    except Exception as e:
        logger.error("pdf_create_failed", path=path, error=str(e))
        raise


async def split_pdf(
    provider: FileStorageProvider,
    source_path: str,
    output_dir: str,
    page_ranges: Optional[List[tuple]] = None
) -> List[str]:
    """
    Split PDF into multiple files.
    
    Args:
        provider: FileStorageProvider instance (connected)
        source_path: Source PDF path
        output_dir: Directory for output files
        page_ranges: List of (start, end) page ranges (1-indexed)
                    If None, splits into individual pages
        
    Returns:
        List of created file paths
        
    Example:
        # Split into ranges
        await split_pdf(
            provider,
            "/docs/report.pdf",
            "/docs/split",
            page_ranges=[(1, 5), (6, 10), (11, 15)]
        )
        # Creates: split/part_1-5.pdf, split/part_6-10.pdf, split/part_11-15.pdf
        
        # Split into individual pages
        await split_pdf(provider, "/docs/report.pdf", "/docs/pages")
        # Creates: pages/page_1.pdf, pages/page_2.pdf, ...
    """
    if not PYPDF_AVAILABLE:
        raise ImportError("pypdf is required for PDF operations. Install: pip install pypdf")
    
    try:
        logger.debug("splitting_pdf", source=source_path, output_dir=output_dir)
        
        # Read source PDF
        data = await provider.read_file(source_path)
        buffer = io.BytesIO(data)
        reader = PdfReader(buffer)
        total_pages = len(reader.pages)
        
        # Default: split into individual pages
        if page_ranges is None:
            page_ranges = [(i, i) for i in range(1, total_pages + 1)]
        
        created_files = []
        
        # Create each split file
        for start_page, end_page in page_ranges:
            writer = PdfWriter()
            
            # Add pages (convert 1-indexed to 0-indexed)
            for page_num in range(start_page - 1, end_page):
                if 0 <= page_num < total_pages:
                    writer.add_page(reader.pages[page_num])
            
            # Write to buffer
            output_buffer = io.BytesIO()
            writer.write(output_buffer)
            split_data = output_buffer.getvalue()
            
            # Generate output filename
            if start_page == end_page:
                filename = f"page_{start_page}.pdf"
            else:
                filename = f"part_{start_page}-{end_page}.pdf"
            
            output_path = f"{output_dir.rstrip('/')}/{filename}"
            
            # Save to provider
            result = await provider.write_file(output_path, split_data, overwrite=True)
            
            if result.success:
                created_files.append(output_path)
                logger.debug("pdf_split_created", path=output_path, pages=f"{start_page}-{end_page}")
        
        logger.info("pdf_split_success", source=source_path, files=len(created_files))
        return created_files
        
    except Exception as e:
        logger.error("pdf_split_failed", source=source_path, error=str(e))
        raise
