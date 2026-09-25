# cogni_package/packager.py
"""
Packager — đóng gói folder thành file .cogni
"""
import zipfile
import hashlib
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List

from .manifest import (
    CogniManifest,
    validate_manifest,
    ManifestError,
)


class PackagerError(Exception):
    """Lỗi khi đóng gói plugin"""
    pass


# Files/folders không đóng gói vào .cogni
EXCLUDED = {
    ".git", ".gitignore", "__pycache__", ".pytest_cache",
    "node_modules", ".venv", "venv", ".env",
    ".DS_Store", ".idea", ".vscode",
    "*.pyc", "*.pyo", "*.log",
}


def _should_exclude(path: Path) -> bool:
    """Check nếu path cần exclude"""
    parts = set(path.parts)
    for ex in EXCLUDED:
        if ex.startswith("*"):
            if path.name.endswith(ex[1:]):
                return True
        elif ex in parts:
            return True
    return False


def _compute_sha256(file_path: Path) -> str:
    """Tính SHA256 của file"""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def pack_plugin(
    source_dir: str,
    output_path: Optional[str] = None,
    verbose: bool = True,
) -> Path:
    """
    Đóng gói folder plugin thành file .cogni

    Args:
        source_dir: folder chứa plugin
        output_path: nơi lưu .cogni (default: <source_dir>.cogni)
        verbose: in log

    Returns:
        Path tới file .cogni
    """
    src = Path(source_dir).resolve()

    if not src.exists():
        raise PackagerError(f"Folder không tồn tại: {src}")

    if not src.is_dir():
        raise PackagerError(f"Không phải folder: {src}")

    # 1. Check manifest
    manifest_path = src / "manifest.json"
    if not manifest_path.exists():
        raise PackagerError(f"Thiếu manifest.json trong {src}")

    manifest = CogniManifest.from_file(manifest_path)

    # 2. Validate
    errors = validate_manifest(manifest)
    if errors:
        raise PackagerError(
            "Manifest không hợp lệ:\n  - " + "\n  - ".join(errors)
        )

    # 3. Check entry file
    entry_path = src / manifest.entry
    if not entry_path.exists():
        raise PackagerError(
            f"Entry file '{manifest.entry}' không tồn tại trong {src}"
        )

    # 4. Output path
    if output_path is None:
        output_path = src.parent / f"{manifest.id}-{manifest.version}.cogni"
    else:
        output_path = Path(output_path)

    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 5. Collect files
    files_to_pack: List[Path] = []
    for path in src.rglob("*"):
        if path.is_file():
            rel = path.relative_to(src)
            if not _should_exclude(rel):
                files_to_pack.append(path)

    if not files_to_pack:
        raise PackagerError("Không có file nào để đóng gói")

    # 6. Create zip
    if verbose:
        print(f"📦 Đóng gói: {src.name}")
        print(f"   → {output_path.name}")

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        # 6a. Manifest
        zf.writestr("manifest.json", manifest.to_json())

        # 6b. Các file khác
        for f in files_to_pack:
            rel = f.relative_to(src)
            zf.write(f, arcname=str(rel))

        # 6c. Metadata (checksum)
        meta = {
            "packed_at": datetime.utcnow().isoformat() + "Z",
            "file_count": len(files_to_pack),
            "packager_version": "1.0.0",
        }
        zf.writestr(".cogni-meta.json", json.dumps(meta, indent=2))

    # 7. Compute checksum
    checksum = _compute_sha256(output_path)
    size = output_path.stat().st_size

    if verbose:
        print(f"   ✅ {len(files_to_pack)} files, {size:,} bytes")
        print(f"   🔐 SHA256: {checksum[:16]}...")

    return output_path


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m cogni_package.packager <plugin_folder>")
        sys.exit(1)

    try:
        result = pack_plugin(sys.argv[1])
        print(f"\n✅ Done: {result}")
    except PackagerError as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)