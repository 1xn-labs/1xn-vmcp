"""
Models for custom tool engines.

This module contains Pydantic models used for structured output
from dynamic tools and sandbox execution.
"""

from pydantic import BaseModel
from typing import Any, Dict


class DynamicToolOutput(BaseModel):
    """Tool call result, stdout and stderr"""
    result: Any  # Can be any type: int, dict, list, str, etc.
    stdout: str
    stderr: str

