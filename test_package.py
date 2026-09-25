# test_package.py
"""
Test .cogni packaging — tạo, verify, giải nén
"""
import sys
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from cogni_package.packager import pack_plugin, PackagerError
from cogni_package.unpacker import unpack_plugin, UnpackerError
from cogni_package.manifest import CogniManifest, validate_manifest


def main():
    print("=" * 70)
    print("🏛️  TEST COGNI PACKAGE FORMAT")
    print("=" * 70)
    print()

    # ============================================================
    # TEST 1: Load & validate manifest
    # ============================================================
    print("[TEST 1] Load manifest từ hello_plugin")
    print("-" * 70)

    src = Path("examples/hello_plugin")
    manifest = CogniManifest.from_file(src / "manifest.json")

    print(f"  ID:       {manifest.id}")
    print(f"  Name:     {manifest.name}")
    print(f"  Version:  {manifest.version}")
    print(f"  Author:   {manifest.author}")
    print(f"  Category: {manifest.category}")
    print(f"  Targets:  {', '.join(manifest.targets)}")
    print(f"  Pricing:  {manifest.pricing.type}")

    errors = validate_manifest(manifest)
    if errors:
        print(f"\n  ❌ Manifest errors:")
        for e in errors:
            print(f"     - {e}")
        return 1
    print("  ✅ Manifest hợp lệ")
    print()

    # ============================================================
    # TEST 2: Pack
    # ============================================================
    print("[TEST 2] Đóng gói .cogni")
    print("-" * 70)

    output = Path("dist") / f"{manifest.id}-{manifest.version}.cogni"
    if output.exists():
        output.unlink()

    try:
        cogni_file = pack_plugin(str(src), str(output))
        print(f"  ✅ File: {cogni_file}")
        print(f"  📊 Size: {cogni_file.stat().st_size:,} bytes")
    except PackagerError as e:
        print(f"  ❌ Pack error: {e}")
        return 1
    print()

    # ============================================================
    # TEST 3: Verify .cogni structure
    # ============================================================
    print("[TEST 3] Verify .cogni structure")
    print("-" * 70)

    import zipfile
    with zipfile.ZipFile(cogni_file, "r") as zf:
        files = zf.namelist()
        print(f"  Files trong package ({len(files)}):")
        for f in sorted(files):
            print(f"    - {f}")

        # Check required files
        required = ["manifest.json", "plugin.py"]
        missing = [r for r in required if r not in files]
        if missing:
            print(f"\n  ❌ Thiếu files: {missing}")
            return 1
        print("  ✅ Đủ required files")
    print()

    # ============================================================
    # TEST 4: Unpack
    # ============================================================
    print("[TEST 4] Giải nén .cogni")
    print("-" * 70)

    extract_dir = Path("dist") / "extracted"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)

    try:
        extracted = unpack_plugin(
            str(cogni_file),
            str(extract_dir / manifest.id),
            overwrite=True,
        )
        print(f"  ✅ Đã giải nén: {extracted}")

        # Verify files
        extracted_files = list(extracted.rglob("*"))
        print(f"  📁 {len([f for f in extracted_files if f.is_file()])} files giải nén")
    except UnpackerError as e:
        print(f"  ❌ Unpack error: {e}")
        return 1
    print()

    # ============================================================
    # TEST 5: Load plugin từ extracted folder
    # ============================================================
    print("[TEST 5] Import plugin.py từ extracted folder")
    print("-" * 70)

    sys.path.insert(0, str(extracted))
    try:
        import importlib
        spec = importlib.util.spec_from_file_location(
            "hello_plugin",
            extracted / "plugin.py"
        )
        plugin = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(plugin)

        result = plugin.run("hello", ["Test User"])
        print(f"  run('hello', ['Test User']):")
        print(f"    → {result}")

        result = plugin.run("hello_time")
        print(f"  run('hello_time'):")
        print(f"    → {result}")
    except Exception as e:
        print(f"  ❌ Import error: {e}")
        return 1
    print()

    # ============================================================
    # DONE
    # ============================================================
    print("=" * 70)
    print("✅ ALL TESTS PASSED")
    print("=" * 70)
    print()
    print(f"📦 Package: {cogni_file}")
    print(f"📁 Extracted: {extracted}")
    print()
    print("🎯 Sẵn sàng cho Phase B (Publish API)")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())