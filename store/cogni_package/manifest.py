# cogni_package/manifest.py
"""
Manifest schema + validator cho .cogni package
"""
import re
import json
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from pathlib import Path


class ManifestError(Exception):
    """Lỗi khi manifest không hợp lệ"""
    pass


# ============================================================
# CONSTANTS
# ============================================================

VALID_PRICING_TYPES = {"free", "paid", "freemium"}
VALID_TARGETS = {"code_room", "vscode", "discord_bot", "desktop", "web"}
VALID_CATEGORIES = {
    "ai", "tools", "themes", "plugins",
    "lms", "analytics", "games", "utility"
}
VALID_PERMISSIONS = {
    "file_read", "file_write", "network",
    "discord", "ai_call", "db_access",
    "system", "gpu"
}

SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{1,48}$")
SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+(-[a-z0-9.]+)?$")


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class ManifestPricing:
    """Pricing config"""
    type: str = "free"                 # free | paid | freemium
    price_usd: float = 0.0
    trial_days: int = 0
    features_locked: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "price_usd": self.price_usd,
            "trial_days": self.trial_days,
            "features_locked": self.features_locked,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ManifestPricing":
        return cls(
            type=data.get("type", "free"),
            price_usd=float(data.get("price_usd", 0.0)),
            trial_days=int(data.get("trial_days", 0)),
            features_locked=list(data.get("features_locked", [])),
        )


@dataclass
class ManifestSignature:
    """Digital signature cho paid plugins"""
    algorithm: str = "RS256"
    public_key_id: str = ""
    signature: str = ""
    signed_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "algorithm": self.algorithm,
            "public_key_id": self.public_key_id,
            "signature": self.signature,
            "signed_at": self.signed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ManifestSignature":
        return cls(
            algorithm=data.get("algorithm", "RS256"),
            public_key_id=data.get("public_key_id", ""),
            signature=data.get("signature", ""),
            signed_at=data.get("signed_at", ""),
        )


@dataclass
class CogniManifest:
    """
    Main manifest schema cho .cogni package
    """
    # Required
    id: str
    name: str
    version: str
    author: str
    description: str
    entry: str = "plugin.py"

    # Optional — display
    long_description: str = ""
    icon: str = "📦"
    homepage: str = ""
    repository: str = ""
    license: str = "MIT"
    changelog: str = ""
    tags: List[str] = field(default_factory=list)
    screenshots: List[str] = field(default_factory=list)

    # Optional — tech
    category: str = "tools"
    targets: List[str] = field(default_factory=lambda: ["code_room", "vscode"])
    permissions: List[str] = field(default_factory=list)
    requirements: List[str] = field(default_factory=list)
    min_engine: str = "1.0.0"

    # Pricing
    pricing: ManifestPricing = field(default_factory=ManifestPricing)

    # Signature (chỉ có ở paid plugin đã publish)
    signature: Optional[ManifestSignature] = None

    # Internal
    manifest_version: str = "1"

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "manifest_version": self.manifest_version,
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "entry": self.entry,
            "long_description": self.long_description,
            "icon": self.icon,
            "homepage": self.homepage,
            "repository": self.repository,
            "license": self.license,
            "changelog": self.changelog,
            "tags": self.tags,
            "screenshots": self.screenshots,
            "category": self.category,
            "targets": self.targets,
            "permissions": self.permissions,
            "requirements": self.requirements,
            "min_engine": self.min_engine,
            "pricing": self.pricing.to_dict(),
        }
        if self.signature:
            d["signature"] = self.signature.to_dict()
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CogniManifest":
        return cls(
            manifest_version=data.get("manifest_version", "1"),
            id=data["id"],
            name=data["name"],
            version=data["version"],
            author=data["author"],
            description=data["description"],
            entry=data.get("entry", "plugin.py"),
            long_description=data.get("long_description", ""),
            icon=data.get("icon", "📦"),
            homepage=data.get("homepage", ""),
            repository=data.get("repository", ""),
            license=data.get("license", "MIT"),
            changelog=data.get("changelog", ""),
            tags=list(data.get("tags", [])),
            screenshots=list(data.get("screenshots", [])),
            category=data.get("category", "tools"),
            targets=list(data.get("targets", ["code_room", "vscode"])),
            permissions=list(data.get("permissions", [])),
            requirements=list(data.get("requirements", [])),
            min_engine=data.get("min_engine", "1.0.0"),
            pricing=ManifestPricing.from_dict(data.get("pricing", {})),
            signature=(
                ManifestSignature.from_dict(data["signature"])
                if data.get("signature")
                else None
            ),
        )

    @classmethod
    def from_file(cls, path: Path) -> "CogniManifest":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


# ============================================================
# VALIDATOR
# ============================================================

def validate_manifest(manifest: CogniManifest) -> List[str]:
    """
    Validate manifest, trả về list errors (rỗng = OK)
    """
    errors = []

    # ID
    if not manifest.id or not SLUG_PATTERN.match(manifest.id):
        errors.append(
            f"ID '{manifest.id}' không hợp lệ. "
            "Chỉ dùng a-z, 0-9, -, _ (2-49 ký tự, bắt đầu bằng chữ/số)"
        )

    # Name
    if not manifest.name or len(manifest.name) < 2:
        errors.append("Name phải có ít nhất 2 ký tự")
    if len(manifest.name) > 100:
        errors.append("Name không quá 100 ký tự")

    # Version
    if not SEMVER_PATTERN.match(manifest.version):
        errors.append(f"Version '{manifest.version}' không theo semver (x.y.z)")

    # Author
    if not manifest.author or len(manifest.author) < 2:
        errors.append("Author phải có ít nhất 2 ký tự")

    # Description
    if not manifest.description:
        errors.append("Description không được rỗng")
    if len(manifest.description) > 500:
        errors.append("Description không quá 500 ký tự")

    # Entry
    if not manifest.entry.endswith(".py"):
        errors.append("Entry phải là file .py")

    # Category
    if manifest.category not in VALID_CATEGORIES:
        errors.append(
            f"Category '{manifest.category}' không hợp lệ. "
            f"Chọn: {', '.join(sorted(VALID_CATEGORIES))}"
        )

    # Targets
    if not manifest.targets:
        errors.append("Phải có ít nhất 1 target")
    for t in manifest.targets:
        if t not in VALID_TARGETS:
            errors.append(
                f"Target '{t}' không hợp lệ. "
                f"Chọn: {', '.join(sorted(VALID_TARGETS))}"
            )

    # Permissions
    for p in manifest.permissions:
        if p not in VALID_PERMISSIONS:
            errors.append(
                f"Permission '{p}' không hợp lệ. "
                f"Chọn: {', '.join(sorted(VALID_PERMISSIONS))}"
            )

    # Pricing
    if manifest.pricing.type not in VALID_PRICING_TYPES:
        errors.append(
            f"Pricing type '{manifest.pricing.type}' không hợp lệ. "
            f"Chọn: {', '.join(VALID_PRICING_TYPES)}"
        )

    if manifest.pricing.type == "paid" and manifest.pricing.price_usd <= 0:
        errors.append("Paid plugin phải có price_usd > 0")

    if manifest.pricing.type == "free" and manifest.pricing.price_usd != 0:
        errors.append("Free plugin không được set price_usd > 0")

    if manifest.pricing.type == "freemium" and not manifest.pricing.features_locked:
        errors.append("Freemium plugin phải có features_locked")

    return errors


# ============================================================
# CLI TEST
# ============================================================

if __name__ == "__main__":
    # Test manifest
    m = CogniManifest(
        id="hello-plugin",
        name="Hello Plugin",
        version="1.0.0",
        author="Thanhdat",
        description="Plugin chào hỏi",
        category="tools",
        targets=["code_room", "vscode", "discord_bot"],
        pricing=ManifestPricing(type="free"),
    )

    print("=" * 60)
    print("MANIFEST TEST")
    print("=" * 60)
    print(m.to_json())

    errors = validate_manifest(m)
    if errors:
        print("\n❌ ERRORS:")
        for e in errors:
            print(f"  - {e}")
    else:
        print("\n✅ Manifest hợp lệ!")