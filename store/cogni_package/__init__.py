# cogni_package/__init__.py
"""
CogniCraft Plugin Package Format (.cogni)
- Manifest schema + validator
- Packager: create .cogni from folder
- Unpacker: extract .cogni to folder
- Signature: sign/verify cho paid plugins
"""

from .manifest import (
    CogniManifest,
    ManifestPricing,
    ManifestSignature,
    validate_manifest,
    ManifestError,
)
from .packager import pack_plugin, PackagerError
from .unpacker import unpack_plugin, UnpackerError

__version__ = "1.0.0"
__all__ = [
    "CogniManifest",
    "ManifestPricing",
    "ManifestSignature",
    "validate_manifest",
    "ManifestError",
    "pack_plugin",
    "PackagerError",
    "unpack_plugin",
    "UnpackerError",
]