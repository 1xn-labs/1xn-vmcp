#!/usr/bin/env python3
"""
VMCP Configuration Manager Package
===================================

This package contains the modular components of the VMCP Configuration Manager.

The main entry point is the VMCPConfigManager class which coordinates all subsystems.
"""

from .widget_utils import UIWidget, ReadResourceContents, MIME_TYPE
from .config_core import VMCPConfigManager

__all__ = [
    'VMCPConfigManager',
    'UIWidget',
    'ReadResourceContents',
    'MIME_TYPE',
]
