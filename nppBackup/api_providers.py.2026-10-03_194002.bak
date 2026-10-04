# api_provider_manager.py
import json
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
from pathlib import Path
from typing import Dict, Any, Optional
import subprocess

# Auto-install dependencies
try:
    import requests
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests


CONFIG_DIR = Path.home() / ".api_provider_manager"
CONFIG_FILE = CONFIG_DIR / "providers.json"
ENCRYPTION_AVAILABLE = False

try:
    import ctypes
    import base64
    ENCRYPTION_AVAILABLE = sys.platform == "win32"
except ImportError:
    pass


class SettingsManager:
    """Reusable settings manager for API providers."""

    PROVIDERS = {
        "OpenRouter": {
            "base_url": "https://openrouter.ai/api/v1",
            "api_key_field": "api_key",
            "supports_models": True,
        },
        "OpenAI": {
            "base_url": "https://api.openai.com/v1",
            "api_key_field": "api_key",
            "supports_models": True,
        },
        "Anthropic": {
            "base_url": "https://api.anthropic.com",
            "api_key_field": "api_key",
            "supports_models": True,
        },
        "Google Gemini": {
            "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
            "api_key_field": "api_key",
            "supports_models": True,
        },
        "Ollama": {
            "base_url": "http://localhost:11434/api",
            "api_key_field": None,
            "supports_models": True,
        },
        "Strata": {
            "base_url": "http://localhost:8000",
            "api_key_field": "api_key",
            "supports_models": True,
        },
        "Custom": {
            "base_url": "",
            "api_key_field": "api_key",
            "supports_models": True,
        },
    }

    def __init__(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load config from file or return defaults."""
        if not CONFIG_FILE.exists():
            return {
                "providers": {},
                "default_provider": None,
                "encrypted": ENCRYPTION_AVAILABLE,
            }
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {
                "providers": {},
                "default_provider": None,
                "encrypted": ENCRYPTION_AVAILABLE,
            }

    def _save_config(self) -> None:
        """Save config to file."""
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(self.config, f, indent=2)
            os.chmod(CONFIG_FILE, 0o600)
        except Exception as e:
            raise Exception(f"Failed to save config: {e}")

    def _encrypt_key(self, key: str) -> str:
        """Encrypt API key using Windows DPAPI if available."""
        if not ENCRYPTION_AVAILABLE or not key:
            return key

        try:
            data = key.encode("utf-8")
            blob = ctypes.create_string_buffer(data)
            data_in = ctypes.wintypes.LPBYTE(blob)
            data_out = ctypes.wintypes.LPBYTE()

            res = ctypes.windll.crypt32.CryptProtectData(
                ctypes.byref(data_in),
                ctypes.c_wchar_p("api_key"),
                None,
                None,
                None,
                0x01,
                ctypes.byref(data_out),
            )

            if res:
                encrypted = bytes(data_out.contents)
                return base64.b64encode(encrypted).decode("utf-8")
        except Exception:
            pass
        return key

    def _decrypt_key(self, encrypted_key: str) -> str:
        """Decrypt API key using Windows DPAPI if available."""
        if not ENCRYPTION_AVAILABLE or not encrypted_key:
            return encrypted_key

        try:
            encrypted = base64.b64decode(encrypted_key.encode("utf-8"))
            blob = ctypes.create_string_buffer(encrypted)
            data_in = ctypes.wintypes.LPBYTE(blob)
            data_out = ctypes.wintypes.LPBYTE()

            res = ctypes.windll.crypt32.CryptUnprotectData(
                ctypes.byref(data_in),
                None,
                None,
                None,
                None,
                0x01,
                ctypes.byref(data_out),
            )

            if res:
                decrypted = bytes(data_out.contents)
                return decrypted.decode("utf-8")
        except Exception:
            pass
        return encrypted_key

    def save_provider(self, name: str, settings: Dict[str, str]) -> None:
        """Save provider settings."""
        if "api_key" in settings and settings["api_key"]:
            settings["api_key"] = self._encrypt_key(settings["api_key"])

        self.config["providers"][name] = settings
        self._save_config()

    def load_provider(self, name: str) -> Optional[Dict[str, str]]:
        """Load provider settings."""
        if name not in self.config["providers"]:
            return None

        settings = self.config["providers"][name].copy()
        if "api_key" in settings and settings["api_key"]:
            settings["api_key"] = self._decrypt_key(settings["api_key"])

        return settings

    def delete_provider(self, name: str) -> None:
        """Delete provider settings."""
        if name in self.config["providers"]:
            del self.config["providers"][name]
        if self.config.get("default_provider") == name:
            self.config["default_provider"] = None
        self._save_config()

    def list_providers(self) -> Dict[str, Dict[str, str]]:
        """List all saved providers."""
        result = {}
        for name, settings in self.config["providers"].items():
            result[name] = self.load_provider(name)
        return result

    def set_default_provider(self, name: str) -> None:
        """Set default provider."""
        if name in self.config["providers"]:
            self.config["default_provider"] = name
            self._save_config()

    def get_default_provider(self) -> Optional[str]:
        """Get default provider."""
        return self.config.get("default_provider")

    def export_settings(self, filepath: str) -> None:
        """Export settings (keys encrypted in export)."""
        export_data = {
            "providers": {},
            "default_provider": self.config.get("default_provider"),
        }
        for name, settings in self.config["providers"].items():
            export_data["providers"][name] = settings.copy()

        with open(filepath, "w") as f:
            json.dump(export_data, f, indent=2)
        os.chmod(filepath, 0o600)

    def import_settings(self, filepath: str, merge: bool = True) -> None:
        """Import settings from file."""
        with open(filepath, "r") as f:
            import_data = json.load(f)

        if not merge:
            self.config["providers"] = {}

        self.config["providers"].update(import_data.get("providers", {}))
        self._save_config()


class APIProviderManagerGUI:
    """Main GUI application."""

    def __init__(self, root):
        self.root = root
        self.root.title("API Provider Manager")
        self.root.geometry("900x700")
        self.root.configure(bg="#1e1e1e")

        self.settings = SettingsManager()
        self.setup_styles()
        self.setup_ui()
        self.refresh_provider_list()

    def setup_styles(self):
        """Setup dark mode theme."""
        style = ttk.Style()
        style.theme_use("clam")

        bg_color = "#1e1e1e"
        fg_color = "#e0e0e0"
        select_color = "#0d47a1"

        style.configure(
            "TFrame",
            background=bg_color,
        )
        style.configure(
            "TLabel",
            background=bg_color,
            foreground=fg_color,
        )
        style.configure(
            "TButton",
            background="#0d47a1",
            foreground=fg_color,
        )
        style.map(
            "TButton",
            background=[("active", "#1565c0")],
        )
        style.configure(
            "TCombobox",
            fieldbackground="#2d2d2d",
            background="#2d2d2d",
            foreground=fg_color,
        )
        style.configure(
            "TEntry",
            fieldbackground="#2d2d2d",
            background="#2d2d2d",
            foreground=fg_color,
        )
        style.configure(
            "TText",
            background="#2d2d2d",
            foreground=fg_color,
        )

    def setup_ui(self):
        """Setup UI components."""
        # Header frame
        header = ttk.Frame(self.root)
        header.pack(fill="x", padx=10, pady=10)

        ttk.Label(header, text="Provider:").pack(side="left", padx=5)
        self.provider_var = tk.StringVar()
        self.provider_dropdown = ttk.Combobox(
            header,
            textvariable=self.provider_var,
            values=list(self.settings.PROVIDERS.keys()),
            state="readonly",
            width=30,
        )
        self.provider_dropdown.pack(side="left", padx=5)
        self.provider_dropdown.bind("<<ComboboxSelected>>", self.on_provider_selected)

        # Main content frame
        content = ttk.Frame(self.root)
        content.pack(fill="both", expand=True, padx=10, pady=10)

        # Settings frame
        settings_frame = ttk.LabelFrame(content, text="Provider Settings")
        settings_frame.pack(fill="x", pady=10)

        ttk.Label(settings_frame, text="Base URL:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.base_url_var = tk.StringVar()
        ttk.Entry(settings_frame, textvariable=self.base_url_var, width=50).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(settings_frame, text="API Key:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        api_key_frame = ttk.Frame(settings_frame)
        api_key_frame.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        self.api_key_var = tk.StringVar()
        self.api_key_entry = ttk.Entry(api_key_frame, textvariable=self.api_key_var, show="•", width=42)
        self.api_key_entry.pack(side="left", fill="x", expand=True)

        self.show_key_var = tk.BooleanVar()
        ttk.Checkbutton(
            api_key_frame,
            text="Show",
            variable=self.show_key_var,
            command=self.toggle_api_key_visibility,
        ).pack(side="left", padx=5)

        ttk.Label(settings_frame, text="Default Model:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        self.default_model_var = tk.StringVar()
        ttk.Entry(settings_frame, textvariable=self.default_model_var, width=50).grid(row=2, column=1, padx=5, pady=5)

        # Buttons frame
        button_frame = ttk.Frame(content)
        button_frame.pack(fill="x", pady=10)

        ttk.Button(button_frame, text="Save", command=self.save_provider).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Test Connection", command=self.test_connection).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Fetch Models", command=self.fetch_models).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Delete", command=self.delete_provider).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Set as Default", command=self.set_default_provider).pack(side="left", padx=5)

        import_export_frame = ttk.Frame(content)
        import_export_frame.pack(fill="x", pady=10)

        ttk.Button(import_export_frame, text="Import Settings", command=self.import_settings).pack(side="left", padx=5)
        ttk.Button(import_export_frame, text="Export Settings", command=self.export_settings).pack(side="left", padx=5)

        # Status log
        log_frame = ttk.LabelFrame(content, text="Status / Output")
        log_frame.pack(fill="both", expand=True, pady=10)

        scrollbar = ttk.Scrollbar(log_frame)
        scrollbar.pack(side="right", fill="y")

        self.log_text = tk.Text(
            log_frame,
            height=15,
            width=80,
            bg="#2d2d2d",
            fg="#e0e0e0",
            yscrollcommand=scrollbar.set,
        )
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)
        scrollbar.config(command=self.log_text.yview)

        # Saved providers frame
        saved_frame = ttk.LabelFrame(content, text="Saved Providers")
        saved_frame.pack(fill="x", pady=10)

        self.saved_providers_var = tk.StringVar()
        ttk.Label(saved_frame, textvariable=self.saved_providers_var).pack(padx=5, pady=5)

    def log(self, message: str):
        """Log message to output panel."""
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.root.update()

    def toggle_api_key_visibility(self):
        """Toggle API key visibility."""
        if self.show_key_var.get():
            self.api_key_entry.config(show="")
        else:
            self.api_key_entry.config(show="•")

    def on_provider_selected(self, event=None):
        """Load provider settings when selected."""
        provider_name = self.provider_var.get()
        if not provider_name:
            return

        saved = self.settings.load_provider(provider_name)
        if saved:
            self.base_url_var.set(saved.get("base_url", ""))
            self.api_key_var.set(saved.get("api_key", ""))
            self.default_model_var.set(saved.get("default_model", ""))
            self.log(f"Loaded settings for {provider_name}")
        else:
            default_settings = self.settings.PROVIDERS.get(provider_name, {})
            self.base_url_var.set(default_settings.get("base_url", ""))
            self.api_key_var.set("")
            self.default_model_var.set("")
            self.log(f"No saved settings for {provider_name}; using defaults")

    def save_provider(self):
        """Save provider settings."""
        provider_name = self.provider_var.get()
        if not provider_name:
            messagebox.showerror("Error", "Please select a provider")
            return

        settings = {
            "base_url": self.base_url_var.get(),
            "api_key": self.api_key_var.get(),
            "default_model": self.default_model_var.get(),
        }

        try:
            self.settings.save_provider(provider_name, settings)
            self.log(f"✓ Saved {provider_name}")
            self.refresh_provider_list()
        except Exception as e:
            self.log(f"✗ Error: {e}")
            messagebox.showerror("Error", f"Failed to save: {e}")

    def delete_provider(self):
        """Delete provider settings."""
        provider_name = self.provider_var.get()
        if not provider_name:
            messagebox.showerror("Error", "Please select a provider")
            return

        if messagebox.askyesno("Confirm", f"Delete {provider_name} settings?"):
            try:
                self.settings.delete_provider(provider_name)
                self.log(f"✓ Deleted {provider_name}")
                self.base_url_var.set("")
                self.api_key_var.set("")
                self.default_model_var.set("")
                self.refresh_provider_list()
            except Exception as e:
                self.log(f"✗ Error: {e}")
                messagebox.showerror("Error", f"Failed to delete: {e}")

    def set_default_provider(self):
        """Set provider as default."""
        provider_name = self.provider_var.get()
        if not provider_name:
            messagebox.showerror("Error", "Please select a provider")
            return

        try:
            self.settings.set_default_provider(provider_name)
            self.log(f"✓ Set {provider_name} as default")
            self.refresh_provider_list()
        except Exception as e:
            self.log(f"✗ Error: {e}")

    def test_connection(self):
        """Test provider connection in background thread."""
        provider_name = self.provider_var.get()
        base_url = self.base_url_var.get()
        api_key = self.api_key_var.get()

        if not provider_name or not base_url:
            messagebox.showerror("Error", "Select provider and set base URL")
            return

        def test():
            try:
                headers = {}
                if api_key:
                    if provider_name in ["OpenRouter", "OpenAI"]:
                        headers["Authorization"] = f"Bearer {api_key}"
                    elif provider_name == "Anthropic":
                        headers["x-api-key"] = api_key
                    elif provider_name == "Google Gemini":
                        headers["x-goog-api-key"] = api_key
                    else:
                        headers["Authorization"] = f"Bearer {api_key}"

                url = f"{base_url.rstrip('/')}/models"
                response = requests.get(url, headers=headers, timeout=5)

                if response.status_code == 200:
                    self.log(f"✓ Connection successful ({response.status_code})")
                else:
                    self.log(f"✗ Connection failed ({response.status_code}): {response.text[:100]}")
            except Exception as e:
                self.log(f"✗ Connection error: {e}")

        thread = threading.Thread(target=test, daemon=True)
        thread.start()

    def fetch_models(self):
        """Fetch available models from provider."""
        provider_name = self.provider_var.get()
        base_url = self.base_url_var.get()
        api_key = self.api_key_var.get()

        if not provider_name or not base_url:
            messagebox.showerror("Error", "Select provider and set base URL")
            return

        def fetch():
            try:
                headers = {}
                if api_key:
                    if provider_name in ["OpenRouter", "OpenAI"]:
                        headers["Authorization"] = f"Bearer {api_key}"
                    elif provider_name == "Anthropic":
                        headers["x-api-key"] = api_key
                    elif provider_name == "Google Gemini":
                        headers["x-goog-api-key"] = api_key
                    else:
                        headers["Authorization"] = f"Bearer {api_key}"

                url = f"{base_url.rstrip('/')}/models"
                response = requests.get(url, headers=headers, timeout=10)

                if response.status_code == 200:
                    data = response.json()
                    models = data.get("data", [])
                    self.log(f"✓ Fetched {len(models)} models:")
                    for model in models[:10]:
                        model_id = model.get("id", model)
                        self.log(f"  - {model_id}")
                    if len(models) > 10:
                        self.log(f"  ... and {len(models) - 10} more")
                else:
                    self.log(f"✗ Failed to fetch models ({response.status_code})")
            except Exception as e:
                self.log(f"✗ Error fetching models: {e}")

        thread = threading.Thread(target=fetch, daemon=True)
        thread.start()

    def import_settings(self):
        """Import settings from file."""
        filepath = filedialog.askopenfilename(
            title="Import Settings",
            filetypes=[("JSON", "*.json"), ("All", "*.*")],
        )
        if not filepath:
            return

        try:
            merge = messagebox.askyesno("Merge?", "Merge with existing settings?")
            self.settings.import_settings(filepath, merge=merge)
            self.log(f"✓ Imported settings from {Path(filepath).name}")
            self.refresh_provider_list()
        except Exception as e:
            self.log(f"✗ Import error: {e}")
            messagebox.showerror("Error", f"Failed to import: {e}")

    def export_settings(self):
        """Export settings to file."""
        filepath = filedialog.asksaveasfilename(
            title="Export Settings",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
        )
        if not filepath:
            return

        try:
            self.settings.export_settings(filepath)
            self.log(f"✓ Exported settings to {Path(filepath).name}")
        except Exception as e:
            self.log(f"✗ Export error: {e}")
            messagebox.showerror("Error", f"Failed to export: {e}")

    def refresh_provider_list(self):
        """Refresh saved providers display."""
        saved = self.settings.list_providers()
        default = self.settings.get_default_provider()

        provider_text = "Saved: "
        if saved:
            names = [f"{'*' if name == default else ''}{name}" for name in saved.keys()]
            provider_text += ", ".join(names)
        else:
            provider_text += "(none)"

        self.saved_providers_var.set(provider_text)


def main():
    root = tk.Tk()
    app = APIProviderManagerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()  
