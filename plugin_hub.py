# plugin_hub.py
"""
Plugin Hub - Marketplace backend
- Browse, search, filter plugins
- Install from GitHub
- Version management
"""
import os
import json
import zipfile
import shutil
import requests
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime


class PluginHub:
    """Plugin Hub backend"""

    REGISTRY_URL = "https://raw.githubusercontent.com/cognicraft/plugins/main/hub_registry.json"

    def __init__(self, registry_file="hub_registry.json", plugins_dir="plugins"):
        self.registry_file = Path(registry_file)
        self.plugins_dir = Path(plugins_dir)
        self.plugins_dir.mkdir(exist_ok=True)

        self.registry = self._load_registry()
        self.cache_dir = Path(".cache/hub")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ============================================================
    # REGISTRY
    # ============================================================

    def _load_registry(self) -> Dict:
        """Load registry từ file local"""
        if self.registry_file.exists():
            try:
                with open(self.registry_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[Hub] Registry load error: {e}")
        return {"plugins": [], "categories": []}

    def refresh_registry(self) -> bool:
        """Refresh registry từ remote"""
        try:
            response = requests.get(self.REGISTRY_URL, timeout=10)
            if response.status_code == 200:
                data = response.json()
                with open(self.registry_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                self.registry = data
                return True
        except Exception as e:
            print(f"[Hub] Refresh error: {e}")
        return False

    # ============================================================
    # BROWSE
    # ============================================================

    def list_plugins(self, category: str = None, sort_by: str = "downloads") -> List[Dict]:
        """
        List plugins.

        Args:
            category: Filter by category
            sort_by: downloads | rating | name | newest
        """
        plugins = self.registry.get("plugins", [])

        if category:
            plugins = [p for p in plugins if p.get("category") == category]

        if sort_by == "downloads":
            plugins.sort(key=lambda x: x.get("downloads", 0), reverse=True)
        elif sort_by == "rating":
            plugins.sort(key=lambda x: x.get("rating", 0), reverse=True)
        elif sort_by == "name":
            plugins.sort(key=lambda x: x.get("name", "").lower())
        elif sort_by == "newest":
            plugins.sort(key=lambda x: x.get("version", "0"), reverse=True)

        return plugins

    def get_featured(self) -> List[Dict]:
        """Get featured plugins"""
        return [p for p in self.registry.get("plugins", []) if p.get("featured")]

    def get_categories(self) -> List[str]:
        """Get all categories"""
        return self.registry.get("categories", [])

    # ============================================================
    # SEARCH
    # ============================================================

    def search(self, query: str) -> List[Dict]:
        """Search plugins by name/description/tags"""
        if not query:
            return self.list_plugins()

        query = query.lower()
        results = []

        for p in self.registry.get("plugins", []):
            # Search in name
            if query in p.get("name", "").lower():
                results.append(p)
                continue

            # Search in description
            if query in p.get("description", "").lower():
                results.append(p)
                continue

            # Search in tags
            if any(query in tag.lower() for tag in p.get("tags", [])):
                results.append(p)
                continue

        return results

    # ============================================================
    # INSTALL
    # ============================================================

    def is_installed(self, plugin_id: str) -> bool:
        """Check if plugin is installed"""
        return (self.plugins_dir / plugin_id).exists()

    def get_installed_version(self, plugin_id: str) -> Optional[str]:
        """Get installed version"""
        manifest_file = self.plugins_dir / plugin_id / "plugin.json"
        if not manifest_file.exists():
            return None

        try:
            with open(manifest_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("version")
        except Exception:
            return None

    def install(self, plugin_id: str, force: bool = False) -> Dict:
        """
        Install plugin từ Hub.

        Args:
            plugin_id: Plugin ID
            force: Force reinstall

        Returns:
            dict: {success, message, plugin}
        """
        # Find plugin in registry
        plugin = None
        for p in self.registry.get("plugins", []):
            if p["id"] == plugin_id:
                plugin = p
                break

        if not plugin:
            return {"success": False, "message": f"Plugin `{plugin_id}` not found"}

        # Check if already installed
        if self.is_installed(plugin_id) and not force:
            current_version = self.get_installed_version(plugin_id)
            return {
                "success": False,
                "message": f"Đã cài rồi (v{current_version}). Dùng `force=True` để cài lại.",
                "plugin": plugin,
            }

        # Download
               # ✅ Check if plugin exists locally first
        local_path = self.plugins_dir / plugin_id
        if local_path.exists():
            return {
                "success": False,
                "message": f"Plugin đã có trong `plugins/{plugin_id}/`. Xóa trước khi cài lại.",
            }

        # ✅ Check example_plugins folder
        example_path = Path("example_plugins") / plugin_id
        if example_path.exists():
            # Copy from example_plugins
            print(f"[Hub] Copying from example_plugins/{plugin_id}...")
            shutil.copytree(str(example_path), str(local_path))
            return {
                "success": True,
                "message": f"✅ Đã cài {plugin['name']} v{plugin['version']} (từ local)",
                "plugin": plugin,
            }

        # Download từ URL
                # ✅ Check if plugin exists locally first
        local_path = self.plugins_dir / plugin_id
        if local_path.exists():
            return {
                "success": False,
                "message": f"Plugin đã có trong `plugins/{plugin_id}/`. Xóa trước khi cài lại.",
            }

        # ✅ Check example_plugins folder
        example_path = Path("example_plugins") / plugin_id
        if example_path.exists():
            # Copy from example_plugins
            print(f"[Hub] Copying from example_plugins/{plugin_id}...")
            shutil.copytree(str(example_path), str(local_path))
            return {
                "success": True,
                "message": f"✅ Đã cài {plugin['name']} v{plugin['version']} (từ local)",
                "plugin": plugin,
            }

        # Download từ URL
        install_url = plugin.get("install_url")
        if not install_url or install_url.startswith("local://"):
            return {"success": False, "message": "Plugin không có file để cài"}

        try:
            print(f"[Hub] Downloading {plugin_id} from {install_url}...")
            response = requests.get(install_url, timeout=30)

            if response.status_code != 200:
                return {
                    "success": False,
                    "message": f"Download failed: HTTP {response.status_code}",
                }
            # Save zip
            zip_path = self.cache_dir / f"{plugin_id}.zip"
            with open(zip_path, "wb") as f:
                f.write(response.content)

            # Extract
            plugin_dir = self.plugins_dir / plugin_id

            # Backup existing if force
            if plugin_dir.exists() and force:
                backup_dir = self.plugins_dir / f"{plugin_id}.backup"
                if backup_dir.exists():
                    shutil.rmtree(backup_dir)
                shutil.move(str(plugin_dir), str(backup_dir))

            # Extract zip
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(plugin_dir)

            # Validate manifest
            manifest_file = plugin_dir / "plugin.json"
            if not manifest_file.exists():
                shutil.rmtree(plugin_dir)
                return {
                    "success": False,
                    "message": "Invalid plugin: missing plugin.json",
                }

            # Cleanup
            zip_path.unlink(missing_ok=True)

            return {
                "success": True,
                "message": f"✅ Đã cài {plugin['name']} v{plugin['version']}",
                "plugin": plugin,
            }

        except Exception as e:
            return {"success": False, "message": f"Install error: {e}"}

    def uninstall(self, plugin_id: str) -> Dict:
        """Uninstall plugin"""
        plugin_dir = self.plugins_dir / plugin_id

        if not plugin_dir.exists():
            return {"success": False, "message": f"Plugin `{plugin_id}` chưa được cài"}

        try:
            shutil.rmtree(plugin_dir)
            return {"success": True, "message": f"✅ Đã gỡ {plugin_id}"}
        except Exception as e:
            return {"success": False, "message": f"Uninstall error: {e}"}

    # ============================================================
    # UPDATE
    # ============================================================

    def check_updates(self) -> List[Dict]:
        """Check for available updates"""
        updates = []

        for p in self.registry.get("plugins", []):
            plugin_id = p["id"]
            if not self.is_installed(plugin_id):
                continue

            installed_version = self.get_installed_version(plugin_id)
            available_version = p.get("version")

            if installed_version and available_version:
                if self._version_compare(available_version, installed_version) > 0:
                    updates.append({
                        "id": plugin_id,
                        "name": p["name"],
                        "installed": installed_version,
                        "available": available_version,
                    })

        return updates

    def _version_compare(self, v1: str, v2: str) -> int:
        """Compare 2 versions. Returns 1 if v1 > v2, -1 if v1 < v2, 0 if equal."""
        try:
            parts1 = [int(x) for x in v1.split(".")]
            parts2 = [int(x) for x in v2.split(".")]

            # Pad shorter
            while len(parts1) < len(parts2):
                parts1.append(0)
            while len(parts2) < len(parts1):
                parts2.append(0)

            for a, b in zip(parts1, parts2):
                if a > b:
                    return 1
                elif a < b:
                    return -1
            return 0
        except Exception:
            return 0

    # ============================================================
    # STATS
    # ============================================================

    def get_stats(self) -> Dict:
        """Get hub stats"""
        total = len(self.registry.get("plugins", []))
        installed = sum(
            1 for p in self.registry.get("plugins", [])
            if self.is_installed(p["id"])
        )
        categories = len(self.get_categories())

        return {
            "total_plugins": total,
            "installed": installed,
            "available": total - installed,
            "categories": categories,
        }