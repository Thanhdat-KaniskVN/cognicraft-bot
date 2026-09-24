# plugin_loader.py
"""
Plugin Loader - Load, validate, và manage plugins
- Discover plugins
- Resolve dependencies
- Load into sandbox
- Register hooks & commands
"""
import os
import json
import importlib.util
import traceback
from pathlib import Path
from typing import Dict, List, Optional
from plugin_manifest import PluginManifest, Permissions


class PluginLoader:
    """Load và manage plugins"""

    def __init__(self, plugins_dir="plugins"):
        self.plugins_dir = Path(plugins_dir)
        self.plugins_dir.mkdir(exist_ok=True)

        # Loaded plugins: {plugin_id: {"manifest": ..., "instance": ..., "module": ...}}
        self.loaded_plugins = {}

        # Plugin registry
        self.registry_file = self.plugins_dir / "registry.json"
        self.registry = self._load_registry()

    # ============================================================
    # REGISTRY
    # ============================================================

    def _load_registry(self):
        """Load plugin registry"""
        if self.registry_file.exists():
            with open(self.registry_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"plugins": {}}

    def _save_registry(self):
        """Save registry"""
        with open(self.registry_file, "w", encoding="utf-8") as f:
            json.dump(self.registry, f, ensure_ascii=False, indent=2)

    # ============================================================
    # DISCOVERY
    # ============================================================

    def discover_plugins(self):
        """
        Discover tất cả plugins trong plugins_dir.

        Returns:
            list of PluginManifest
        """
        plugins = []

        for plugin_dir in self.plugins_dir.iterdir():
            if not plugin_dir.is_dir():
                continue

            # Check manifest
            manifest_file = None
            for filename in ["plugin.json", "plugin.yaml", "plugin.yml"]:
                path = plugin_dir / filename
                if path.exists():
                    manifest_file = path
                    break

            if not manifest_file:
                print(f"[PluginLoader] No manifest in {plugin_dir.name}")
                continue

            try:
                manifest = PluginManifest.from_file(str(manifest_file))

                # Validate
                errors = manifest.validate()
                if errors:
                    print(f"[PluginLoader] Invalid manifest {plugin_dir.name}: {errors}")
                    continue

                # Check entry point exists
                entry_path = plugin_dir / manifest.entry_point
                if not entry_path.exists():
                    print(f"[PluginLoader] Entry point not found: {entry_path}")
                    continue

                plugins.append(manifest)

            except Exception as e:
                print(f"[PluginLoader] Error loading {plugin_dir.name}: {e}")
                traceback.print_exc()

        return plugins

    # ============================================================
    # DEPENDENCY RESOLUTION
    # ============================================================

       # Core services – không cần check dependencies
    CORE_SERVICES = [
        "cognicraft-core",
        "ai-service",
        "data-service",
        "discord-service",
    ]

    def resolve_dependencies(self, manifest):
        """Check dependencies của plugin"""
        missing = []

        for req in manifest.requires:
            # Parse "plugin-name>=1.0.0"
            if ">=" in req:
                name, ver = req.split(">=")
                name = name.strip()
                ver = ver.strip()
            elif "==" in req:
                name, ver = req.split("==")
                name = name.strip()
                ver = ver.strip()
            else:
                name = req.strip()
                ver = None

            # ✅ Bỏ qua core services
            if name in self.CORE_SERVICES:
                continue

            # Check if loaded
            if name not in self.loaded_plugins:
                # Check if available locally
                available = False
                for p in self.discover_plugins():
                    if p.name == name or p.id == name:
                        available = True
                        break

                if not available:
                    missing.append(req)

        return len(missing) == 0, missing

    def check_conflicts(self, manifest):
        """Check conflicts"""
        conflicts = []

        for conflict in manifest.conflicts:
            if conflict in self.loaded_plugins:
                conflicts.append(conflict)

        return len(conflicts) == 0, conflicts

    # ============================================================
    # LOADING
    # ============================================================

    def load_plugin(self, plugin_id, config=None):
        """
        Load plugin vào memory.

        Args:
            plugin_id: Plugin ID hoặc name
            config: Dict config cho plugin

        Returns:
            (success: bool, message: str)
        """
        if plugin_id in self.loaded_plugins:
            return False, f"Plugin {plugin_id} đã được load"

        # Find plugin
        plugin_dir = None
        manifest = None

        for p in self.discover_plugins():
            if p.id == plugin_id or p.name == plugin_id:
                plugin_dir = self.plugins_dir / p.id
                manifest = p
                break

        if not manifest:
            return False, f"Plugin {plugin_id} không tìm thấy"

        # Check dependencies
        ok, missing = self.resolve_dependencies(manifest)
        if not ok:
            return False, f"Missing dependencies: {missing}"

        # Check conflicts
        ok, conflicts = self.check_conflicts(manifest)
        if not ok:
            return False, f"Conflicts with: {conflicts}"

        # Load module
        try:
            entry_path = plugin_dir / manifest.entry_point
            spec = importlib.util.spec_from_file_location(
                f"plugin_{manifest.id}", str(entry_path)
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Get plugin class
            plugin_class = getattr(module, manifest.main_class, None)
            if not plugin_class:
                return False, f"Class {manifest.main_class} not found"

            # Instantiate
            plugin_instance = plugin_class(
                manifest=manifest,
                config=config or {},
                core_api=self._get_core_api(),
            )

            # Register
            self.loaded_plugins[manifest.id] = {
                "manifest": manifest,
                "instance": plugin_instance,
                "module": module,
            }

            # Save registry
            self.registry["plugins"][manifest.id] = manifest.to_dict()
            self._save_registry()

            # Call on_load hook
            if hasattr(plugin_instance, "on_load"):
                plugin_instance.on_load()

            return True, f"✅ Loaded {manifest.name} v{manifest.version}"

        except Exception as e:
            traceback.print_exc()
            return False, f"Error loading plugin: {e}"

    def unload_plugin(self, plugin_id):
        """Unload plugin"""
        if plugin_id not in self.loaded_plugins:
            return False, f"Plugin {plugin_id} chưa được load"

        try:
            plugin = self.loaded_plugins[plugin_id]

            # Call on_unload hook
            if hasattr(plugin["instance"], "on_unload"):
                plugin["instance"].on_unload()

            # Remove
            del self.loaded_plugins[plugin_id]

            # Update registry
            if plugin_id in self.registry["plugins"]:
                del self.registry["plugins"][plugin_id]
                self._save_registry()

            return True, f"✅ Unloaded {plugin_id}"

        except Exception as e:
            return False, f"Error unloading: {e}"

    # ============================================================
    # CORE API BRIDGE
    # ============================================================

    def _get_core_api(self):
        """
        Get Core API để plugins có thể gọi.

        Returns:
            CoreAPI instance
        """
        # Sẽ được inject từ bot.py
        return getattr(self, "_core_api", None)

    def set_core_api(self, core_api):
        """Set Core API (gọi từ bot.py)"""
        self._core_api = core_api

    # ============================================================
    # HOOKS
    # ============================================================

    def get_hooks(self, hook_name):
        """
        Get all handlers for a hook.

        Args:
            hook_name: Tên hook (VD: "on_score_complete")

        Returns:
            List of handlers
        """
        handlers = []

        for plugin_id, plugin in self.loaded_plugins.items():
            manifest = plugin["manifest"]
            instance = plugin["instance"]

            if hook_name in manifest.hooks:
                method_name = manifest.hooks[hook_name]
                handler = getattr(instance, method_name, None)
                if handler:
                    handlers.append({
                        "plugin_id": plugin_id,
                        "handler": handler,
                    })

        return handlers

    async def call_hooks(self, hook_name, **kwargs):
        """Call all handlers for a hook"""
        handlers = self.get_hooks(hook_name)

        results = []
        for h in handlers:
            try:
                result = await h["handler"](**kwargs)
                results.append({
                    "plugin_id": h["plugin_id"],
                    "result": result,
                })
            except Exception as e:
                print(f"[PluginLoader] Hook error in {h['plugin_id']}: {e}")
                results.append({
                    "plugin_id": h["plugin_id"],
                    "error": str(e),
                })

        return results

    # ============================================================
    # COMMANDS
    # ============================================================

    def get_commands(self):
        """
        Get all commands from loaded plugins.

        Returns:
            list of {plugin_id, name, description, handler}
        """
        commands = []

        for plugin_id, plugin in self.loaded_plugins.items():
            manifest = plugin["manifest"]
            instance = plugin["instance"]

            for cmd in manifest.commands:
                name = cmd.get("name")
                description = cmd.get("description", "")
                handler_path = cmd.get("handler", "")

                # Parse "main.start_socratic"
                if "." in handler_path:
                    module_name, method_name = handler_path.split(".", 1)
                    handler = getattr(instance, method_name, None)
                else:
                    handler = getattr(instance, handler_path, None)

                if handler:
                    commands.append({
                        "plugin_id": plugin_id,
                        "name": name,
                        "description": description,
                        "handler": handler,
                        "config": cmd,
                    })

        return commands

    # ============================================================
    # UTILS
    # ============================================================

    def list_loaded(self):
        """List all loaded plugins"""
        return [
            {
                "id": pid,
                "name": p["manifest"].name,
                "version": p["manifest"].version,
                "author": p["manifest"].author,
            }
            for pid, p in self.loaded_plugins.items()
        ]

    def get_plugin_info(self, plugin_id):
        """Get detailed info về plugin"""
        if plugin_id not in self.loaded_plugins:
            return None

        p = self.loaded_plugins[plugin_id]
        return {
            "manifest": p["manifest"].to_dict(),
            "loaded": True,
        }