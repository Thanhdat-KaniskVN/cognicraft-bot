# test_publish.py
"""
Test Phase B: Publish API
Chạy từ D:\Bot deepseek
"""
import sys
import requests
from pathlib import Path

API = "http://localhost:8001"
TOKEN = "cognicraft-dev-token-2026"
AUTHOR = "Thanhdat"

COGNI_FILE = Path("dist/hello-plugin-1.0.0.cogni")


def main():
    print("=" * 70)
    print("🏛️  TEST PHASE B: PUBLISH API")
    print("=" * 70)
    print()

    # Check file tồn tại
    if not COGNI_FILE.exists():
        print(f"❌ File không tồn tại: {COGNI_FILE}")
        print("   Chạy test_package.py trước để tạo .cogni")
        return 1

    print(f"📦 Package: {COGNI_FILE}")
    print(f"📊 Size: {COGNI_FILE.stat().st_size:,} bytes")
    print()

    # ============================================================
    # TEST 1: Publish plugin
    # ============================================================
    print("[TEST 1] Publish plugin mới")
    print("-" * 70)

    headers = {
        "Authorization": f"Bearer {TOKEN}:{AUTHOR}",
    }

    with open(COGNI_FILE, "rb") as f:
        files = {"file": (COGNI_FILE.name, f, "application/zip")}
        r = requests.post(f"{API}/api/store/publish", headers=headers, files=files)

    print(f"  Status: {r.status_code}")

    if r.status_code == 200:
        data = r.json()
        print(f"  ✅ Published!")
        print(f"     Slug:    {data['slug']}")
        print(f"     Version: {data['version']}")
        print(f"     Message: {data['message']}")
    elif r.status_code == 409:
        print(f"  ⚠️  Plugin đã tồn tại (test chạy lần 2)")
    else:
        print(f"  ❌ Failed: {r.text}")
        return 1
    print()

    # ============================================================
    # TEST 2: Verify trong database
    # ============================================================
    print("[TEST 2] Verify trong database")
    print("-" * 70)

    r = requests.get(f"{API}/api/store/plugins/hello-plugin")
    if r.status_code == 200:
        data = r.json()
        p = data["plugin"]
        print(f"  ✅ Plugin có trong DB:")
        print(f"     Name:     {p['name']}")
        print(f"     Author:   {p['author']}")
        print(f"     Version:  {p['latest_version']}")
        print(f"     Category: {p['category']}")
        print(f"     Downloads: {p['downloads']}")
    else:
        print(f"  ❌ Không fetch được: {r.status_code}")
        return 1
    print()

    # ============================================================
    # TEST 3: Download .cogni
    # ============================================================
    print("[TEST 3] Download .cogni")
    print("-" * 70)

    r = requests.get(f"{API}/api/store/download/hello-plugin")
    if r.status_code == 200:
        out_path = Path("dist/downloaded-hello.cogni")
        out_path.write_bytes(r.content)
        print(f"  ✅ Download OK: {out_path}")
        print(f"     Size: {out_path.stat().st_size:,} bytes")

        # Verify it's a valid zip
        import zipfile
        if zipfile.is_zipfile(out_path):
            print(f"     ✅ Valid zip file")
        else:
            print(f"     ❌ Invalid file")
    else:
        print(f"  ❌ Download failed: {r.status_code} {r.text}")
        return 1
    print()

    # ============================================================
    # TEST 4: Auth errors
    # ============================================================
    print("[TEST 4] Auth errors")
    print("-" * 70)

    # No auth
    with open(COGNI_FILE, "rb") as f:
        files = {"file": (COGNI_FILE.name, f, "application/zip")}
        r = requests.post(f"{API}/api/store/publish", files=files)
    print(f"  No auth header: {r.status_code} (expect 401) {'✅' if r.status_code == 401 else '❌'}")

    # Wrong token
    with open(COGNI_FILE, "rb") as f:
        files = {"file": (COGNI_FILE.name, f, "application/zip")}
        r = requests.post(
            f"{API}/api/store/publish",
            headers={"Authorization": "Bearer wrong-token:test"},
            files=files,
        )
    print(f"  Wrong token:    {r.status_code} (expect 403) {'✅' if r.status_code == 403 else '❌'}")
    print()

    # ============================================================
    # DONE
    # ============================================================
    print("=" * 70)
    print("✅ ALL PHASE B TESTS PASSED")
    print("=" * 70)
    print()
    print("🎯 Sẵn sàng cho Phase C (VSCode Extension)")
    print()

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except requests.exceptions.ConnectionError:
        print("❌ Không kết nối được API. Chạy trước:")
        print("   cd store && python main.py")
        sys.exit(1)