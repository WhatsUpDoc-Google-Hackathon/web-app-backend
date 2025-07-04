from markdown_pdf import MarkdownPdf, Section
from pathlib import Path
from typing import Optional
import logging

# Configure logging
logger = logging.getLogger(__name__)


def convert_markdown_to_pdf(
    markdown_content: str,
    output_path: str,
    title: Optional[str] = None,
    author: Optional[str] = None,
    subject: Optional[str] = None,
    keywords: Optional[str] = None,
    toc_level: int = 2,
    optimize: bool = True,
    paper_size: str = "A4",
    include_toc: bool = True,
    custom_css: Optional[str] = None,
) -> bool:
    """
    Convert markdown content to PDF file.

    Args:
        markdown_content (str): The markdown content to convert
        output_path (str): Path where the PDF file will be saved
        title (str, optional): PDF document title
        author (str, optional): PDF document author
        subject (str, optional): PDF document subject
        keywords (str, optional): PDF document keywords
        toc_level (int): Table of contents heading level (default: 2)
        optimize (bool): Whether to optimize the PDF (default: True)
        paper_size (str): Paper size for the PDF (default: "A4")
        include_toc (bool): Whether to include table of contents (default: True)
        custom_css (str, optional): Custom CSS styling for the PDF

    Returns:
        bool: True if conversion successful, False otherwise

    Example:
        >>> markdown_text = "# Hello World\n\nThis is a test document."
        >>> success = convert_markdown_to_pdf(
        ...     markdown_content=markdown_text,
        ...     output_path="output.pdf",
        ...     title="My Document",
        ...     author="John Doe"
        ... )
        >>> print(f"Conversion successful: {success}")
    """
    try:
        # Create PDF object with specified options
        pdf = MarkdownPdf(toc_level=toc_level, optimize=optimize)

        # Add main content section
        section = Section(markdown_content, toc=include_toc, paper_size=paper_size)

        # Add section to PDF (with custom CSS if provided)
        if custom_css:
            pdf.add_section(section, user_css=custom_css)
        else:
            pdf.add_section(section)

        # Set PDF metadata if provided
        if title:
            pdf.meta["title"] = title
        if author:
            pdf.meta["author"] = author
        if subject:
            pdf.meta["subject"] = subject
        if keywords:
            pdf.meta["keywords"] = keywords

        # Ensure output directory exists
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Save PDF to file
        pdf.save(str(output_file))

        logger.info(f"Successfully converted markdown to PDF: {output_path}")
        return True

    except Exception as e:
        logger.error(f"Error converting markdown to PDF: {str(e)}")
        return False


def convert_markdown_file_to_pdf(
    markdown_file_path: str, output_path: Optional[str] = None, **kwargs
) -> bool:
    """
    Convert a markdown file to PDF.

    Args:
        markdown_file_path (str): Path to the markdown file
        output_path (str, optional): Output PDF path. If None, uses same name as input with .pdf extension
        **kwargs: Additional arguments passed to convert_markdown_to_pdf

    Returns:
        bool: True if conversion successful, False otherwise

    Example:
        >>> success = convert_markdown_file_to_pdf(
        ...     markdown_file_path="document.md",
        ...     title="My Document"
        ... )
    """
    try:
        # Read markdown file
        markdown_path = Path(markdown_file_path)
        if not markdown_path.exists():
            logger.error(f"Markdown file not found: {markdown_file_path}")
            return False

        with open(markdown_path, "r", encoding="utf-8") as file:
            markdown_content = file.read()

        # Determine output path if not provided
        if output_path is None:
            output_path = str(markdown_path.with_suffix(".pdf"))

        # Convert to PDF
        return convert_markdown_to_pdf(
            markdown_content=markdown_content, output_path=output_path, **kwargs
        )

    except Exception as e:
        logger.error(f"Error reading markdown file {markdown_file_path}: {str(e)}")
        return False


def convert_markdown_with_sections(
    sections: list,
    output_path: str,
    title: Optional[str] = None,
    author: Optional[str] = None,
    toc_level: int = 2,
    optimize: bool = True,
) -> bool:
    """
    Convert multiple markdown sections to a single PDF with custom formatting.

    Args:
        sections (list): List of dictionaries with section data. Each dict should contain:
            - 'content' (str): Markdown content
            - 'css' (str, optional): Custom CSS for this section
            - 'paper_size' (str, optional): Paper size for this section
            - 'include_toc' (bool, optional): Whether to include in TOC
        output_path (str): Path where the PDF file will be saved
        title (str, optional): PDF document title
        author (str, optional): PDF document author
        toc_level (int): Table of contents heading level
        optimize (bool): Whether to optimize the PDF

    Returns:
        bool: True if conversion successful, False otherwise

    Example:
        >>> sections = [
        ...     {
        ...         'content': '# Cover Page\n\nWelcome to my document',
        ...         'include_toc': False,
        ...         'css': 'h1 {text-align: center;}'
        ...     },
        ...     {
        ...         'content': '# Chapter 1\n\nThis is the first chapter.',
        ...         'paper_size': 'A4'
        ...     }
        ... ]
        >>> success = convert_markdown_with_sections(
        ...     sections=sections,
        ...     output_path="multi_section.pdf",
        ...     title="Multi-Section Document"
        ... )
    """
    try:
        # Create PDF object
        pdf = MarkdownPdf(toc_level=toc_level, optimize=optimize)

        # Process each section
        for section_data in sections:
            content = section_data.get("content", "")
            custom_css = section_data.get("css", None)
            paper_size = section_data.get("paper_size", "A4")
            include_toc = section_data.get("include_toc", True)

            # Create section
            section = Section(content, toc=include_toc, paper_size=paper_size)

            # Add section with or without custom CSS
            if custom_css:
                pdf.add_section(section, user_css=custom_css)
            else:
                pdf.add_section(section)

        # Set PDF metadata
        if title:
            pdf.meta["title"] = title
        if author:
            pdf.meta["author"] = author

        # Ensure output directory exists
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Save PDF
        pdf.save(str(output_file))

        logger.info(f"Successfully created multi-section PDF: {output_path}")
        return True

    except Exception as e:
        logger.error(f"Error creating multi-section PDF: {str(e)}")
        return False
