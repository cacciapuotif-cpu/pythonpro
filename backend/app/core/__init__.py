"""
============================================================
📦 PACKAGE: core
------------------------------------------------------------
Modulo core contenente le impostazioni centrali, sicurezza,
dipendenze e middleware dell'applicazione.
============================================================
"""

from .settings import Settings, get_settings

__all__ = ["Settings", "get_settings"]
