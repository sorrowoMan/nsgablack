# -*- coding: utf-8 -*-
"""Thin forwarder for project catalog registration.

Keep root clean; delegate to catalog/project_registry.py.
"""

from __future__ import annotations

from catalog.project_registry import get_project_entries  # re-export

__all__ = ["get_project_entries"]
