#!/usr/bin/env python3
"""
Widget Utilities
================

Utilities for managing UI widgets in vMCP resources and tools.
"""

from dataclasses import dataclass
from typing import Dict, Any
from mcp.types import EmbeddedResource, TextResourceContents


@dataclass
class ReadResourceContents:
    """Contents returned from a read_resource call."""

    content: str | bytes
    mime_type: str | None = None


@dataclass(frozen=True)
class UIWidget:
    """UI Widget metadata with HTML content."""

    identifier: str
    title: str
    template_uri: str
    invoking: str
    invoked: str
    html: str
    response_text: str


MIME_TYPE = "text/html+skybridge"


def _resource_description(widget: UIWidget) -> str:
    """Generate resource description for a widget."""
    return f"{widget.title} widget markup"


def _tool_meta(widget: UIWidget) -> Dict[str, Any]:
    """Generate tool metadata for widget integration with OpenAI."""
    return {
        "openai/outputTemplate": widget.template_uri,
        "openai/toolInvocation/invoking": widget.invoking,
        "openai/toolInvocation/invoked": widget.invoked,
        "openai/widgetAccessible": True,
        "openai/resultCanProduceWidget": True,
        "annotations": {
            "destructiveHint": False,
            "openWorldHint": False,
            "readOnlyHint": True,
        }
    }


def _embedded_widget_resource(widget: UIWidget) -> EmbeddedResource:
    """Create embedded resource from widget."""
    return EmbeddedResource(
        type="resource",
        resource=TextResourceContents(
            uri=widget.template_uri,
            mimeType=MIME_TYPE,
            text=widget.html,
            title=widget.title,
        ),
    )
