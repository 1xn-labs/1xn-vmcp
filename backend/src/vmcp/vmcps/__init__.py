"""VMCP (Virtual MCP) module for aggregating multiple MCP servers."""

from vmcp.vmcps.models import (
    VMCPCreateRequest,
    VMCPUdateRequest,  # Note: typo in models.py
    VMCPInfo,
    VMCPToolCallRequest,
    VMCPResourceRequest,
    VMCPPromptRequest,
)

# Alias for the typo
VMCPUpdateRequest = VMCPUdateRequest

__all__ = [
    "VMCPCreateRequest",
    "VMCPUpdateRequest",
    "VMCPInfo",
    "VMCPToolCallRequest",
    "VMCPResourceRequest",
    "VMCPPromptRequest",
]
