#!/usr/bin/env python
# tools/unpack.py
"""
CLI giải nén .cogni

Usage:
    python tools/unpack.py <file.cogni> [dest_folder]
"""
import sys
import io
from pathlib import Path

# ✅ Force UTF-8 output (fix Windows encoding)
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(_root))

from cogni_package.unpacker import unpack_plugin, UnpackerError


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cogni = sys.argv[1]
    dest = sys.argv[2] if len(sys.argv) > 2 else None

    print("=" * 60)
    print("🏛️  COGNICRAFT UNPACKER")
    print("=" * 60)

    try:
        result = unpack_plugin(cogni, dest, overwrite=True)
        print()
        print("=" * 60)
        print(f"✅ Giải nén thành công!")
        print(f"📁 Folder: {result}")
        print("=" * 60)
    except UnpackerError as e:
        print(f"\n❌ LỖI: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()