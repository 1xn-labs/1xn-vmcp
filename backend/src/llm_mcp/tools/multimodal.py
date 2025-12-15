"""
Multimodal tools for image and document analysis.
"""

import base64
import io
import json
from typing import Optional

import litellm

from llm_mcp.config import get_settings, DEFAULT_MODELS
from llm_mcp.models import AnalyzeImageInput, AnalyzePDFInput, AnalyzeDocumentInput
from llm_mcp.utils import handle_litellm_error, format_error_response


def is_url(s: str) -> bool:
    """Check if string is a URL."""
    return s.startswith("http://") or s.startswith("https://")


def is_base64(s: str) -> bool:
    """Check if string looks like base64 data."""
    # Remove data URL prefix if present
    if s.startswith("data:"):
        return True
    # Check if it's long enough and contains valid base64 chars
    if len(s) > 100:
        try:
            base64.b64decode(s[:100])
            return True
        except Exception:
            pass
    return False


def format_image_content(image: str) -> dict:
    """Format image for LiteLLM vision API."""
    if is_url(image):
        return {
            "type": "image_url",
            "image_url": {"url": image},
        }
    elif image.startswith("data:"):
        # Already formatted as data URL
        return {
            "type": "image_url",
            "image_url": {"url": image},
        }
    else:
        # Assume base64, add data URL prefix
        # Try to detect image type from first bytes
        try:
            decoded = base64.b64decode(image[:20])
            if decoded[:8] == b"\x89PNG\r\n\x1a\n":
                mime_type = "image/png"
            elif decoded[:2] == b"\xff\xd8":
                mime_type = "image/jpeg"
            elif decoded[:6] in (b"GIF87a", b"GIF89a"):
                mime_type = "image/gif"
            elif decoded[:4] == b"RIFF" and decoded[8:12] == b"WEBP":
                mime_type = "image/webp"
            else:
                mime_type = "image/png"  # Default
        except Exception:
            mime_type = "image/png"

        return {
            "type": "image_url",
            "image_url": {"url": f"data:{mime_type};base64,{image}"},
        }


async def analyze_image(params: AnalyzeImageInput) -> str:
    """
    Analyze an image using a vision-capable LLM.

    This tool sends an image to a vision model for analysis based on
    the provided prompt.

    Args:
        params: Input parameters including:
            - image: Base64-encoded image or URL
            - prompt: What to analyze about the image
            - model: Vision-capable model to use

    Returns:
        Analysis of the image based on the prompt.
    """
    settings = get_settings()
    model = params.model or DEFAULT_MODELS.get("vision", "openai/gpt-4o")

    try:
        # Build message with image
        image_content = format_image_content(params.image)

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": params.prompt},
                    image_content,
                ],
            }
        ]

        response = await litellm.acompletion(
            model=model,
            messages=messages,
            temperature=0.3,
        )

        content = response.choices[0].message.content

        result = {
            "analysis": content,
            "model": response.model,
        }

        if response.usage:
            result["usage"] = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return json.dumps(result, indent=2)

    except Exception as e:
        error = handle_litellm_error(e, model)
        return format_error_response(error)


async def describe_image(image: str, model: Optional[str] = None) -> str:
    """
    Generate a detailed description of an image.

    This is a simplified wrapper around analyze_image for generating
    image descriptions.

    Args:
        image: Base64-encoded image or URL
        model: Vision-capable model to use

    Returns:
        Detailed description of the image.
    """
    params = AnalyzeImageInput(
        image=image,
        prompt="Describe this image in detail. Include the main subjects, colors, composition, and any text or notable elements visible.",
        model=model,
    )
    return await analyze_image(params)


async def extract_text_from_image(image: str, model: Optional[str] = None) -> str:
    """
    Extract text from an image (OCR).

    This tool uses a vision model to extract any text visible in an image.

    Args:
        image: Base64-encoded image or URL
        model: Vision-capable model to use

    Returns:
        Extracted text from the image.
    """
    params = AnalyzeImageInput(
        image=image,
        prompt="""Extract ALL text visible in this image. 
Include:
- Main text content
- Labels and captions
- Numbers and dates
- Any other readable text

Preserve the original formatting as much as possible (line breaks, paragraphs).
If no text is visible, say "No text found in image."

Extracted text:""",
        model=model,
    )
    return await analyze_image(params)


async def analyze_pdf(params: AnalyzePDFInput) -> str:
    """
    Analyze a PDF document.

    This tool extracts text from a PDF and analyzes it based on the prompt.
    For PDFs with images, it can optionally analyze those as well.

    Args:
        params: Input parameters including:
            - pdf_content: Base64-encoded PDF content
            - prompt: What to analyze about the PDF
            - extract_images: Whether to analyze images
            - model: Model to use

    Returns:
        Analysis of the PDF content.
    """
    settings = get_settings()
    model = params.model or settings.default_model

    try:
        # Try to import pypdf
        try:
            from pypdf import PdfReader
        except ImportError:
            return json.dumps(
                {
                    "error": True,
                    "message": "PDF analysis requires pypdf. Install with: pip install pypdf",
                },
                indent=2,
            )

        # Decode PDF
        try:
            pdf_bytes = base64.b64decode(params.pdf_content)
            pdf_file = io.BytesIO(pdf_bytes)
            reader = PdfReader(pdf_file)
        except Exception as e:
            return json.dumps(
                {
                    "error": True,
                    "message": f"Failed to parse PDF: {str(e)}",
                },
                indent=2,
            )

        # Extract text from all pages
        text_content = []
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                text_content.append(f"--- Page {i + 1} ---\n{page_text}")

        if not text_content:
            return json.dumps(
                {
                    "error": True,
                    "message": "No text could be extracted from the PDF. It may be image-based.",
                    "suggestion": "For scanned PDFs, use llm_analyze_image with individual page images.",
                },
                indent=2,
            )

        full_text = "\n\n".join(text_content)

        # Truncate if too long
        max_chars = 50000
        if len(full_text) > max_chars:
            full_text = full_text[:max_chars] + "\n\n[Content truncated due to length...]"

        # Analyze with LLM
        analysis_prompt = f"""{params.prompt}

PDF Content ({len(reader.pages)} pages):
---
{full_text}
---

Analysis:"""

        response = await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": analysis_prompt}],
            temperature=0.3,
        )

        content = response.choices[0].message.content

        result = {
            "analysis": content,
            "metadata": {
                "pages": len(reader.pages),
                "characters_extracted": len(full_text),
            },
            "model": response.model,
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        error = handle_litellm_error(e, model)
        return format_error_response(error)


async def compare_images(
    images: list[str],
    prompt: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """
    Compare multiple images.

    This tool analyzes and compares multiple images, highlighting
    similarities and differences.

    Args:
        images: List of base64-encoded images or URLs
        prompt: Specific comparison criteria (optional)
        model: Vision-capable model to use

    Returns:
        Comparison analysis of the images.
    """
    settings = get_settings()
    model = model or DEFAULT_MODELS.get("vision", "openai/gpt-4o")

    if len(images) < 2:
        return json.dumps(
            {
                "error": True,
                "message": "At least 2 images are required for comparison",
            },
            indent=2,
        )

    if len(images) > 4:
        return json.dumps(
            {
                "error": True,
                "message": "Maximum 4 images can be compared at once",
            },
            indent=2,
        )

    default_prompt = """Compare these images and provide:
1. Key similarities between the images
2. Key differences between the images
3. A summary of what each image shows"""

    comparison_prompt = prompt or default_prompt

    try:
        # Build message with all images
        content = [{"type": "text", "text": comparison_prompt}]
        for i, img in enumerate(images):
            image_content = format_image_content(img)
            content.append(image_content)

        messages = [{"role": "user", "content": content}]

        response = await litellm.acompletion(
            model=model,
            messages=messages,
            temperature=0.3,
        )

        result_content = response.choices[0].message.content

        result = {
            "comparison": result_content,
            "images_compared": len(images),
            "model": response.model,
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        error = handle_litellm_error(e, model)
        return format_error_response(error)


async def analyze_document(params: AnalyzeDocumentInput) -> str:
    """
    Universal document analyzer that auto-detects document type.

    This tool automatically detects whether the input is:
    - Plain text
    - A PDF (base64-encoded)
    - An image (base64-encoded or URL)

    Then routes to the appropriate analyzer.

    Args:
        params: Input parameters including:
            - document: Document content (text, PDF, or image)
            - prompt: Optional analysis prompt
            - model: Optional model to use

    Returns:
        Analysis results with detected document type.
    """
    document = params.document.strip()
    prompt = params.prompt or "Analyze this document and provide a comprehensive summary."

    # Detect document type
    doc_type = None
    is_pdf = False
    is_image = False
    is_text = False

    # Check if it's a URL (likely an image)
    if is_url(document):
        doc_type = "image_url"
        is_image = True
    # Check if it's base64 PDF (starts with PDF magic bytes when decoded)
    elif len(document) > 100:
        try:
            # Try to decode first bytes
            decoded = base64.b64decode(document[:100])
            # PDF magic bytes: %PDF
            if decoded[:4] == b"%PDF":
                doc_type = "pdf"
                is_pdf = True
            # Image magic bytes
            elif decoded[:8] == b"\x89PNG\r\n\x1a\n":  # PNG
                doc_type = "image_png"
                is_image = True
            elif decoded[:2] == b"\xff\xd8":  # JPEG
                doc_type = "image_jpeg"
                is_image = True
            elif decoded[:6] in (b"GIF87a", b"GIF89a"):  # GIF
                doc_type = "image_gif"
                is_image = True
            elif decoded[:4] == b"RIFF" and decoded[8:12] == b"WEBP":  # WebP
                doc_type = "image_webp"
                is_image = True
            elif document.startswith("data:image"):
                doc_type = "image_data_url"
                is_image = True
            elif document.startswith("data:application/pdf"):
                doc_type = "pdf_data_url"
                is_pdf = True
            else:
                # Assume text if it's not clearly binary
                doc_type = "text"
                is_text = True
        except Exception:
            # If decoding fails, assume it's text
            doc_type = "text"
            is_text = True
    else:
        # Short string, assume text
        doc_type = "text"
        is_text = True

    result = {
        "detected_type": doc_type,
        "analysis": None,
    }

    try:
        if is_pdf:
            # Route to PDF analyzer
            pdf_content = document
            if document.startswith("data:application/pdf"):
                pdf_content = document.split(",", 1)[1]
            pdf_params = AnalyzePDFInput(
                pdf_content=pdf_content,
                prompt=prompt,
                model=params.model,
            )
            pdf_result = await analyze_pdf(pdf_params)
            result["analysis"] = json.loads(pdf_result)
            result["method"] = "pdf_analysis"

        elif is_image:
            # Route to image analyzer
            image_params = AnalyzeImageInput(
                image=document,
                prompt=prompt,
                model=params.model,
            )
            image_result = await analyze_image(image_params)
            result["analysis"] = json.loads(image_result)
            result["method"] = "image_analysis"

        else:
            # Route to text analyzer
            from llm_mcp.tools.analysis import analyze_text
            from llm_mcp.models import AnalyzeTextInput, AnalysisType

            text_params = AnalyzeTextInput(
                text=document,
                analysis_type=AnalysisType.ALL,
                model=params.model,
            )
            text_result = await analyze_text(text_params)
            result["analysis"] = json.loads(text_result)
            result["method"] = "text_analysis"

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps(
            {
                "error": True,
                "message": f"Failed to analyze document: {str(e)}",
                "detected_type": doc_type,
            },
            indent=2,
        )
