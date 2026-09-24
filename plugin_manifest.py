# plugin_manifest.py
"""
Plugin Manifest - Schema cho plugin
- Validate manifest
- Parse metadata
- Check dependencies
"""
import json
import os
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from packaging import version


@dataclass
class PluginManifest:
    """Manifest của 1 plugin"""

    # Required
    name: str
    version: str
    author: str
    description: str

    # Optional
    id: str = ""  # Auto-generated từ name
    category: str = "Other"
    license: str = "MIT"
    homepage: str = ""
    repository: str = ""

    # Dependencies
    requires: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)

    # Permissions
    permissions: List[str] = field(default_factory=list)

    # Commands
    commands: List[Dict] = field(default_factory=list)

    # Hooks
    hooks: Dict[str, str] = field(default_factory=dict)

    # Config schema
    config: Dict = field(default_factory=dict)

    # Entry point
    entry_point: str = "main.py"
    main_class: str = "Plugin"

    def __post_init__(self):
        if not self.id:
            self.id = self._generate_id(self.name)

    def _generate_id(self, name):
        """Generate plugin ID từ name"""
        return re.sub(r"[^a-z0-9_]", "_", name.lower())

    @classmethod
    def from_file(cls, path):
        """Load manifest từ file plugin.yaml hoặc plugin.json"""
        if path.endswith(".json"):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            # YAML
            try:
                import yaml
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
            except ImportError:
                raise ImportError("Cần cài pyyaml: pip install pyyaml")

        return cls(**data)

    def validate(self):
        """Validate manifest"""
        errors = []

        # Check required fields
        if not self.name:
            errors.append("Missing 'name'")
        if not self.version:
            errors.append("Missing 'version'")
        if not self.author:
            errors.append("Missing 'author'")
        if not self.description:
            errors.append("Missing 'description'")

        # Check version format
        try:
            version.parse(self.version)
        except Exception:
            errors.append(f"Invalid version: {self.version}")

        # Check entry point exists
        if not self.entry_point:
            errors.append("Missing entry_point")

        return errors

    def to_dict(self):
        """Convert to dict"""
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "category": self.category,
            "license": self.license,
            "homepage": self.homepage,
            "repository": self.repository,
            "requires": self.requires,
            "conflicts": self.conflicts,
            "permissions": self.permissions,
            "commands": self.commands,
            "hooks": self.hooks,
            "config": self.config,
            "entry_point": self.entry_point,
            "main_class": self.main_class,
        }


# ============================================================
# PERMISSIONS SYSTEM
# ============================================================

class Permissions:
    """Permission constants"""

    # Data permissions
    READ_SCORES = "read:scores"
    WRITE_SCORES = "write:scores"
    READ_INSIGHTS = "read:insights"
    WRITE_INSIGHTS = "write:insights"
    READ_PARTICIPATION = "read:participation"
    READ_ERRORS = "read:errors"
    WRITE_ERRORS = "write:errors"

    # Communication
    SEND_MESSAGES = "send:messages"
    SEND_DM = "send:dm"
    EDIT_MESSAGES = "edit:messages"
    DELETE_MESSAGES = "delete:messages"

    # AI
    CALL_AI = "call:ai"
    READ_CACHE = "read:cache"
    WRITE_CACHE = "write:cache"

    # System
    SCHEDULE_TASKS = "schedule:tasks"
    READ_CONFIG = "read:config"
    WRITE_CONFIG = "write:config"

    # Advanced
    HTTP_REQUESTS = "http:requests"
    FILE_ACCESS = "file:access"
    EXECUTE_CODE = "execute:code"

    ALL = [
        READ_SCORES, WRITE_SCORES,
        READ_INSIGHTS, WRITE_INSIGHTS,
        READ_PARTICIPATION, READ_ERRORS, WRITE_ERRORS,
        SEND_MESSAGES, SEND_DM, EDIT_MESSAGES, DELETE_MESSAGES,
        CALL_AI, READ_CACHE, WRITE_CACHE,
        SCHEDULE_TASKS, READ_CONFIG, WRITE_CONFIG,
        HTTP_REQUESTS, FILE_ACCESS, EXECUTE_CODE,
    ]

    @classmethod
    def validate(cls, permission):
        """Check permission có hợp lệ không"""
        return permission in cls.ALL