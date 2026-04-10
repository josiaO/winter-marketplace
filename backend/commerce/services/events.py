"""
Commerce facade for domain events — delegates to ``core.events`` (single emitter).
"""
from __future__ import annotations

from core.events import emit_event

__all__ = ['emit_event']
