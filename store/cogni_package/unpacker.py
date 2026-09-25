# cogni_package/unpacker.py
"""
Unpacker — giải nén .cogni ra folder
"""
import zipfile
import json
import shutil
from pathlib import Path
from typing import Optional

from .manifest import CogniManifest


class UnpackerError(Exception):
    """Lỗi khi giải nén plugin"""
    pass


def unpack_plugin(
    cogni_path: str,
    dest_dir: Optional[str] = None,
    overwrite: bool = False,
    verbose: bool = True,
) -> Path:
    """
    Giải nén .cogni ra folder

    Args:
        cogni_path: đường dẫn file .cogni
        dest_dir: thư mục đích (default: cùng tên với file)
        overwrite: ghi đè nếu đã tồn tại
        verbose: in log

    Returns:
        Path tới folder chứa plugin
    """
    src = Path(cogni_path).resolve()

    if not src.exists():
        raise UnpackerError(f"File không tồn tại: {src}")

    if not src.is_file():
        raise UnpackerError(f"Không phải file: {src}")

    if not zipfile.is_zipfile(src):
        raise UnpackerError(f"Không phải file .cogni hợp lệ: {src}")

    # 1. Read manifest
    with zipfile.ZipFile(src, "r") as zf:
        if "manifest.json" not in zf.namelist():
            raise UnpackerError("Thiếu manifest.json trong .cogni")

        manifest = CogniManifest.from_dict(
            json.loads(zf.read("manifest.json"))
        )

        # 2. Destination
        if dest_dir is None:
            dest_dir = src.parent / manifest.id
        dest = Path(dest_dir).resolve()

        if dest.exists() and not overwrite:
            raise UnpackerError(
                f"Destination đã tồn tại: {dest}\n"
                "Dùng overwrite=True hoặc xóa folder trước"
            )

        if dest.exists() and overwrite:
            shutil.rmtree(dest)

        dest.mkdir(parents=True, exist_ok=True)

        # 3. Extract — bảo vệ zip slip
        for member in zf.namelist():
            # Skip meta files
            if member == ".cogni-meta.json":
                continue

            # Bảo vệ path traversal
            member_path = (dest / member).resolve()
            if not str(member_path).startswith(str(dest)):
                raise UnpackerError(
                    f"Phát hiện path traversal: {member}"
                )

            zf.extract(member, dest)

    if verbose:
        print(f"📦 Đã giải nén: {src.name}")
        print(f"   → {dest}")
        print(f"   Plugin: {manifest.name} v{manifest.version}")
        print(f"   Author: {manifest.author}")

    return dest


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m cogni_package.unpacker <file.cogni> [dest]")
        sys.exit(1)

    dest = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        result = unpack_plugin(sys.argv[1], dest, overwrite=True)
        print(f"\n✅ Done: {result}")
    except UnpackerError as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)