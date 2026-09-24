# hub.py
"""
Plugin Hub - Local Plugin Marketplace
- Discover plugins từ example_plugins/
- Install/uninstall plugin
- Search, filter, stats
"""
import os
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional


class PluginHub:
    """Plugin Hub - Local marketplace cho plugins"""

    def __init__(self, source_dir=None, install_dir=None):
        """Khởi tạo Hub với absolute path"""
        base_dir = Path(__file__).parent.resolve()

        if source_dir is None:
            self.source_dir = base_dir / "example_plugins"
        else:
            self.source_dir = Path(source_dir)
            if not self.source_dir.is_absolute():
                self.source_dir = base_dir / self.source_dir

        if install_dir is None:
            self.install_dir = base_dir / "plugins"
        else:
            self.install_dir = Path(install_dir)
            if not self.install_dir.is_absolute():
                self.install_dir = base_dir / self.install_dir

        self.registry_file = base_dir / "hub_registry.json"

        # Đảm bảo folder tồn tại
        self.source_dir.mkdir(exist_ok=True)
        self.install_dir.mkdir(exist_ok=True)

        # Load registry
        self.registry = self._load_registry()

    # ============================================================
    # REGISTRY
    # ============================================================

    def _load_registry(self) -> Dict:
        """Load hub registry"""
        if self.registry_file.exists():
            try:
                with open(self.registry_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "plugins" not in data:
                        data["plugins"] = []
                    return data
            except Exception as e:
                print(f"[Hub] Registry load error: {e}")

        return self._build_registry()

    def _save_registry(self):
        """Save registry"""
        try:
            with open(self.registry_file, "w", encoding="utf-8") as f:
                json.dump(self.registry, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Hub] Registry save error: {e}")

    def _build_registry(self) -> Dict:
        """Build registry từ example_plugins/"""
        plugins = []

        if not self.source_dir.exists():
            return {"plugins": [], "last_updated": str(datetime.now())}

        for folder in self.source_dir.iterdir():
            if not folder.is_dir():
                continue

            manifest_file = folder / "plugin.json"
            if not manifest_file.exists():
                continue

            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                plugin = {
                    "id": data.get("name", folder.name).lower().replace(" ", "_"),
                    "name": data.get("name", folder.name),
                    "version": data.get("version", "1.0.0"),
                    "author": data.get("author", "Unknown"),
                    "description": data.get("description", ""),
                    "category": data.get("category", "Other"),
                    "license": data.get("license", "MIT"),
                    "homepage": data.get("homepage", ""),
                    "repository": data.get("repository", ""),
                    "source_path": str(folder),
                    "folder_name": folder.name,
                    "rating": round(4.5 + (hash(folder.name) % 50) / 100, 1),
                    "reviews": (hash(folder.name) % 100) + 20,
                    "downloads": ((hash(folder.name) % 2000) + 500),
                    "size_kb": self._get_size_kb(folder),
                    "tags": data.get("permissions", [])[:3],
                    "verified": True,
                    "featured": False,
                }
                plugins.append(plugin)
            except Exception as e:
                print(f"[Hub] Error loading {folder.name}: {e}")

        return {
            "plugins": plugins,
            "last_updated": str(datetime.now()),
        }

    def _get_size_kb(self, folder: Path) -> int:
        """Tính size folder (KB)"""
        total = 0
        for file in folder.rglob("*"):
            if file.is_file():
                total += file.stat().st_size
        return max(1, total // 1024)

    # ============================================================
    # DISCOVERY
    # ============================================================

    def list_plugins(self) -> List[Dict]:
        """List all plugins"""
        self.registry = self._build_registry()

        installed = self._get_installed_ids()
        for p in self.registry["plugins"]:
            p["installed"] = p["id"] in installed

        return self.registry["plugins"]

    def get_featured(self) -> List[Dict]:
        """Get featured plugins"""
        plugins = self.list_plugins()
        return [p for p in plugins if p.get("verified")][:5]

    def search(self, query: str) -> List[Dict]:
        """Search plugins"""
        query = query.lower().strip()
        plugins = self.list_plugins()

        results = []
        for p in plugins:
            if (query in p["name"].lower() or
                query in p["description"].lower() or
                query in p["category"].lower() or
                query in p["author"].lower()):
                results.append(p)

        return results

    def get_plugin(self, plugin_id: str) -> Optional[Dict]:
        """Get plugin by ID"""
        for p in self.list_plugins():
            if p["id"] == plugin_id:
                return p
        return None

    # ============================================================
    # INSTALL / UNINSTALL
    # ============================================================

    def _get_installed_ids(self) -> set:
        """Get list of installed plugin IDs"""
        installed = set()

        if not self.install_dir.exists():
            return installed

        for folder in self.install_dir.iterdir():
            if not folder.is_dir():
                continue

            manifest = folder / "plugin.json"
            if not manifest.exists():
                continue

            try:
                with open(manifest, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    pid = data.get("name", folder.name).lower().replace(" ", "_")
                    installed.add(pid)
            except Exception:
                continue

        return installed

    def install(self, plugin_id: str) -> Dict:
        """Cài đặt plugin từ source_dir → install_dir"""
        plugin = self.get_plugin(plugin_id)

        if not plugin:
            return {
                "success": False,
                "message": f"❌ Không tìm thấy plugin `{plugin_id}` trong Hub.\n"
                          f"Dùng `!hub` để xem danh sách.",
            }

        installed = self._get_installed_ids()
        if plugin_id in installed:
            return {
                "success": False,
                "message": f"⚠️ Plugin `{plugin_id}` đã được cài.\n"
                          f"Dùng `!hub_uninstall {plugin_id}` để gỡ trước.",
            }

        source = Path(plugin["source_path"])
        target = self.install_dir / plugin["folder_name"]

        if not source.exists():
            return {
                "success": False,
                "message": f"❌ Source folder không tồn tại: `{source}`",
            }

        if target.exists():
            return {
                "success": False,
                "message": f"⚠️ Folder `{target.name}` đã tồn tại trong plugins/.",
            }

        try:
            shutil.copytree(source, target)

            return {
                "success": True,
                "message": (
                    f"**{plugin['name']}** v{plugin['version']}\n"
                    f"📦 Đã cài vào `{target.name}/`\n"
                    f"👤 Tác giả: {plugin['author']}\n"
                    f"📁 Category: {plugin['category']}"
                ),
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"❌ Lỗi copy: {e}",
            }

    def uninstall(self, plugin_id: str) -> Dict:
        """Gỡ plugin"""
        plugin = self.get_plugin(plugin_id)

        if not plugin:
            return {
                "success": False,
                "message": f"❌ Không tìm thấy plugin `{plugin_id}`.",
            }

        target = self.install_dir / plugin["folder_name"]

        if not target.exists():
            for folder in self.install_dir.iterdir():
                if not folder.is_dir():
                    continue

                manifest = folder / "plugin.json"
                if manifest.exists():
                    try:
                        with open(manifest, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            pid = data.get("name", "").lower().replace(" ", "_")
                            if pid == plugin_id:
                                target = folder
                                break
                    except Exception:
                        continue

        if not target.exists():
            return {
                "success": False,
                "message": f"❌ Plugin `{plugin_id}` chưa được cài.",
            }

        try:
            shutil.rmtree(target)
            return {
                "success": True,
                "message": f"✅ Đã gỡ **{plugin['name']}** khỏi plugins/.",
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"❌ Lỗi xóa: {e}",
            }

    # ============================================================
    # REFRESH / UPDATES
    # ============================================================

    def refresh_registry(self) -> bool:
        """Rebuild registry"""
        try:
            self.registry = self._build_registry()
            print(f"[Hub] Refreshed: {len(self.registry['plugins'])} plugins")
            return True
        except Exception as e:
            print(f"[Hub] Refresh error: {e}")
            return False

    def check_updates(self) -> List[Dict]:
        """Check for updates"""
        updates = []
        installed_ids = self._get_installed_ids()

        for p in self.list_plugins():
            if p["id"] not in installed_ids:
                continue

            installed_plugin = self._read_installed_manifest(p["id"])
            if not installed_plugin:
                continue

            if installed_plugin.get("version") != p["version"]:
                updates.append({
                    "id": p["id"],
                    "name": p["name"],
                    "installed": installed_plugin.get("version", "?"),
                    "available": p["version"],
                })

        return updates

    def _read_installed_manifest(self, plugin_id: str) -> Optional[Dict]:
        """Đọc manifest của plugin đã cài"""
        for folder in self.install_dir.iterdir():
            if not folder.is_dir():
                continue

            manifest = folder / "plugin.json"
            if not manifest.exists():
                continue

            try:
                with open(manifest, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    pid = data.get("name", "").lower().replace(" ", "_")
                    if pid == plugin_id:
                        return data
            except Exception:
                continue

        return None

    # ============================================================
    # STATS
    # ============================================================

    def get_stats(self) -> Dict:
        """Hub statistics"""
        plugins = self.list_plugins()
        installed = self._get_installed_ids()

        categories = set(p["category"] for p in plugins)

        return {
            "total_plugins": len(plugins),
            "installed": len(installed),
            "available": len(plugins) - len(installed),
            "categories": len(categories),
        }