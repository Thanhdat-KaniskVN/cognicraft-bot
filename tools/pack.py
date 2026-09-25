#!/usr/bin/env python
# tools/pack.py
"""
CLI đóng gói plugin thành .cogni

Usage:
    python tools/pack.py <plugin_folder> [output.cogni]
    python tools/pack.py examples/hello_plugin
    python tools/pack.py examples/hello_plugin dist/hello.cogni
"""
import sys
import io
from pathlib import Path

# ✅ Force UTF-8 output (fix Windows encoding)
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add project root to path
_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(_root))

from cogni_package.packager import pack_plugin, PackagerError


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    source = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else None

    print("=" * 60)
    print("🏛️  COGNICRAFT PACKAGER")
    print("=" * 60)

    try:
        result = pack_plugin(source, output)
        print()
        print("=" * 60)
        print(f"✅ Đóng gói thành công!")
        print(f"📄 File: {result}")
        print(f"📊 Size: {result.stat().st_size:,} bytes")
        print("=" * 60)
    except PackagerError as e:
        print(f"\n❌ LỖI: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()