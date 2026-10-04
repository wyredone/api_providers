import json
import os
import time
from pathlib import Path
from typing import Dict, List, Tuple
from constants import CONFIG_DIR
from encryption import encrypt_key, decrypt_key


class KeyManager:
    """Manages API keys separately with backup and import/export functionality."""

    def __init__(self):
        """Initialize key manager."""
        self.keys_dir = CONFIG_DIR / "keys"
        self.keys_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir = CONFIG_DIR / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def save_key(self, provider: str, api_key: str, notes: str = "") -> bool:
        """Save an API key with optional notes."""
        try:
            encrypted = encrypt_key(api_key)
            key_data = {
                "provider": provider,
                "key": encrypted,
                "notes": notes,
                "saved_at": time.time(),
                "last_used": None
            }

            key_file = self.keys_dir / f"{provider}.json"
            with open(key_file, 'w') as f:
                json.dump(key_data, f)

            if hasattr(os, 'chmod'):
                os.chmod(key_file, 0o600)

            return True
        except Exception:
            return False

    def get_key(self, provider: str) -> Tuple[str, str]:
        """Get API key and notes for provider. Returns (key, notes)."""
        try:
            key_file = self.keys_dir / f"{provider}.json"
            if key_file.exists():
                with open(key_file, 'r') as f:
                    data = json.load(f)
                decrypted = decrypt_key(data["key"])
                return decrypted, data.get("notes", "")
        except Exception:
            pass
        return "", ""

    def list_keys(self) -> List[Dict]:
        """List all saved keys."""
        keys_list = []
        try:
            for key_file in self.keys_dir.glob("*.json"):
                with open(key_file, 'r') as f:
                    data = json.load(f)
                    keys_list.append({
                        "provider": data["provider"],
                        "saved_at": data.get("saved_at", 0),
                        "notes": data.get("notes", ""),
                        "last_used": data.get("last_used")
                    })
        except Exception:
            pass
        return sorted(keys_list, key=lambda x: x["saved_at"], reverse=True)

    def delete_key(self, provider: str) -> bool:
        """Delete an API key."""
        try:
            key_file = self.keys_dir / f"{provider}.json"
            if key_file.exists():
                key_file.unlink()
                return True
        except Exception:
            pass
        return False

    def export_keys(self, filepath: str, providers: List[str] = None) -> bool:
        """Export keys to file. If providers is None, export all."""
        try:
            export_data = {"keys": {}, "exported_at": time.time()}

            if providers is None:
                providers = [k["provider"] for k in self.list_keys()]

            for provider in providers:
                key_file = self.keys_dir / f"{provider}.json"
                if key_file.exists():
                    with open(key_file, 'r') as f:
                        data = json.load(f)
                        export_data["keys"][provider] = data

            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, 'w') as f:
                json.dump(export_data, f, indent=2)

            if hasattr(os, 'chmod'):
                os.chmod(filepath, 0o600)

            return True
        except Exception:
            return False

    def import_keys(self, filepath: str, merge: bool = True) -> Tuple[bool, int, str]:
        """Import keys from file. Returns (success, count, message)."""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            if "keys" not in data:
                return False, 0, "Invalid file format"

            imported_count = 0
            for provider, key_data in data["keys"].items():
                if not merge and self.key_exists(provider):
                    continue

                try:
                    key_file = self.keys_dir / f"{provider}.json"
                    with open(key_file, 'w') as f:
                        json.dump(key_data, f)
                    if hasattr(os, 'chmod'):
                        os.chmod(key_file, 0o600)
                    imported_count += 1
                except Exception:
                    pass

            return True, imported_count, f"Imported {imported_count} keys"
        except Exception as e:
            return False, 0, f"Error: {str(e)}"

    def backup_keys(self) -> Tuple[bool, str]:
        """Create timestamped backup of all keys. Returns (success, filepath)."""
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_file = self.backup_dir / f"keys_backup_{timestamp}.json"

            success = self.export_keys(str(backup_file))
            return success, str(backup_file) if success else ""
        except Exception:
            return False, ""

    def list_backups(self) -> List[Dict]:
        """List all backup files."""
        backups = []
        try:
            for backup_file in self.backup_dir.glob("keys_backup_*.json"):
                stat = backup_file.stat()
                backups.append({
                    "filename": backup_file.name,
                    "path": str(backup_file),
                    "size": stat.st_size,
                    "created": stat.st_mtime
                })
        except Exception:
            pass
        return sorted(backups, key=lambda x: x["created"], reverse=True)

    def restore_backup(self, backup_path: str) -> Tuple[bool, int, str]:
        """Restore keys from backup file."""
        return self.import_keys(backup_path, merge=False)

    def key_exists(self, provider: str) -> bool:
        """Check if key exists for provider."""
        return (self.keys_dir / f"{provider}.json").exists()

    def update_last_used(self, provider: str) -> bool:
        """Update last used timestamp for a key."""
        try:
            key_file = self.keys_dir / f"{provider}.json"
            if key_file.exists():
                with open(key_file, 'r') as f:
                    data = json.load(f)
                data["last_used"] = time.time()
                with open(key_file, 'w') as f:
                    json.dump(data, f)
                return True
        except Exception:
            pass
        return False
