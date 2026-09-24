# ml_mini/integration/__init__.py
"""
ML Mini Integration Layer
- Bot commands
- Token Optimizer hook
- Switch Board hook
- Sheets sync
"""
from .ml_manager import MLManager, get_ml_manager

__all__ = ["MLManager", "get_ml_manager"]