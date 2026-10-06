import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import re
import atexit
from .constants import PROVIDERS
from .settings_manager import SettingsManager
from .api_client import APIClient
from .key_manager_gui import KeyManagerWindow
from .debug_logger import DebugLogger
from .debug_gui import DebugWindow
from .file_logger import FileLogger
from .log_viewer import LogViewerWindow
from .anthropic_models_manager import AnthropicModelsManager


class APIProviderManagerGUI:
    """Main GUI application for managing API providers."""

    def __init__(self, root):
        """Initialize GUI application."""
        self.root = root
        self.root.title("API Provider Manager")
        self.root.geometry("900x1000")
        self.root.resizable(True, True)

        self.file_logger = FileLogger()
        self.settings_manager = SettingsManager()
        self.debug_logger = DebugLogger()
        APIClient.set_debug_logger(self.debug_logger)
        APIClient.set_file_logger(self.file_logger)
        self.current_models = []
        self.filtered_models = []
        self.last_latency = 0.0
        self.sync_thread = None

        self.file_logger.log_info("Application started")
        atexit.register(self.on_shutdown)

        self.setup_styles()
        self.setup_ui()
        self.bind_shortcuts()
        self.start_background_sync()

    def setup_styles(self):
        """Configure application theme."""
        self.bg_color = "#f5f5f5"
        self.fg_color = "#1a1a1a"
        self.accent_color = "#0066cc"
        self.input_bg = "#ffffff"

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=self.bg_color)
        style.configure("TLabel", background=self.bg_color, foreground=self.fg_color)
        style.configure("TButton", background=self.bg_color, foreground=self.fg_color)
        style.configure("TCombobox", fieldbackground=self.input_bg, background=self.input_bg)
        style.configure("Custom.TLabel", background=self.bg_color, foreground=self.fg_color, font=("Arial", 10, "bold"))

        self.root.configure(bg=self.bg_color)

    def setup_ui(self):
        """Setup user interface."""
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text="API Provider Manager", style="Custom.TLabel").pack(anchor=tk.W, pady=(0, 10))

        provider_frame = ttk.Frame(main_frame)
        provider_frame.pack(fill=tk.X, pady=5)
        ttk.Label(provider_frame, text="Provider:").pack(side=tk.LEFT, padx=(0, 5))
        self.provider_var = tk.StringVar(value=list(PROVIDERS.keys())[0])
        provider_combo = ttk.Combobox(provider_frame, textvariable=self.provider_var, values=list(PROVIDERS.keys()), state="readonly", width=20)
        provider_combo.pack(side=tk.LEFT)
        provider_combo.bind("<<ComboboxSelected>>", self.on_provider_changed)

        base_url_frame = ttk.Frame(main_frame)
        base_url_frame.pack(fill=tk.X, pady=5)
        ttk.Label(base_url_frame, text="Base URL:").pack(side=tk.LEFT, padx=(0, 5))
        self.base_url_var = tk.StringVar()
        base_url_entry = ttk.Entry(base_url_frame, textvariable=self.base_url_var, width=50)
        base_url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        api_key_frame = ttk.Frame(main_frame)
        api_key_frame.pack(fill=tk.X, pady=5)
        ttk.Label(api_key_frame, text="API Key:").pack(side=tk.LEFT, padx=(0, 5))
        self.api_key_var = tk.StringVar()
        self.api_key_entry = ttk.Entry(api_key_frame, textvariable=self.api_key_var, width=40, show="•")
        self.api_key_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.show_key_button = ttk.Button(api_key_frame, text="Show", command=self.toggle_show_key)
        self.show_key_button.pack(side=tk.LEFT)

        model_frame = ttk.Frame(main_frame)
        model_frame.pack(fill=tk.X, pady=5)
        ttk.Label(model_frame, text="Default Model:").pack(side=tk.LEFT, padx=(0, 5))
        self.default_model_var = tk.StringVar()
        self.model_combo = ttk.Combobox(model_frame, textvariable=self.default_model_var, width=45, state="readonly")
        self.model_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)

        recently_frame = ttk.Frame(main_frame)
        recently_frame.pack(fill=tk.X, pady=5)
        ttk.Label(recently_frame, text="Recently Used:").pack(side=tk.LEFT, padx=(0, 5))
        self.recent_combo = ttk.Combobox(recently_frame, width=45, state="readonly")
        self.recent_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.recent_combo.bind("<<ComboboxSelected>>", self.on_recent_selected)

        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill=tk.X, pady=5)
        ttk.Label(search_frame, text="Search Models:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=50)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.search_var.trace("w", self.filter_models)

        models_label = ttk.Label(main_frame, text="Available Models (click to select) • Keyboard: Ctrl+F search, Ctrl+S save, Ctrl+T test")
        models_label.pack(anchor=tk.W, pady=(10, 2))

        self.models_text = tk.Text(main_frame, height=15, width=90, bg=self.input_bg, fg=self.fg_color, wrap=tk.WORD)
        self.models_text.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        self.models_text.bind("<Button-1>", self.on_model_click)

        scrollbar = ttk.Scrollbar(self.models_text)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.models_text.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.models_text.yview)

        button_frame1 = ttk.Frame(main_frame)
        button_frame1.pack(fill=tk.X, pady=5)
        ttk.Button(button_frame1, text="Save (Ctrl+S)", command=self.save_provider).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame1, text="Test (Ctrl+T)", command=self.test_connection).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame1, text="Fetch Models", command=self.fetch_models).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame1, text="Delete", command=self.delete_provider).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame1, text="Set as Default", command=self.set_as_default).pack(side=tk.LEFT, padx=2)

        button_frame2 = ttk.Frame(main_frame)
        button_frame2.pack(fill=tk.X, pady=5)
        ttk.Button(button_frame2, text="Import Settings", command=self.import_settings).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame2, text="Export Settings", command=self.export_settings).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame2, text="Export Favorites", command=self.export_favorites).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame2, text="Delete All", command=self.delete_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame2, text="🔑 Key Manager", command=self.open_key_manager).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame2, text="🐛 Debug Console", command=self.open_debug_console).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame2, text="📋 View Logs", command=self.open_log_viewer).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame2, text="🔄 Update Anthropic Models", command=self.open_anthropic_models).pack(side=tk.LEFT, padx=2)

        self.status_label = ttk.Label(main_frame, text="Ready", foreground="#008000")
        self.status_label.pack(anchor=tk.W, pady=5)

        self.update_provider_display()

    def bind_shortcuts(self):
        """Bind keyboard shortcuts."""
        self.root.bind("<Control-s>", lambda e: self.save_provider())
        self.root.bind("<Control-t>", lambda e: self.test_connection())
        self.root.bind("<Control-f>", lambda e: self.search_var.set(""))

    def on_provider_changed(self, event=None):
        """Handle provider selection change."""
        provider = self.provider_var.get()
        provider_config = PROVIDERS.get(provider, {})
        self.base_url_var.set(provider_config.get("base_url", ""))

        saved = self.settings_manager.load_provider(provider)
        if saved:
            self.base_url_var.set(saved.get("base_url", provider_config.get("base_url", "")))
            self.api_key_var.set(saved.get("api_key", ""))
            self.default_model_var.set(saved.get("default_model", ""))
        else:
            self.api_key_var.set("")
            self.default_model_var.set("")
            self.model_combo.config(values=[])

        self.current_models = []
        self.filtered_models = []
        self.models_text.delete("1.0", tk.END)
        self.update_recently_used()

        cached = self.settings_manager.get_cached_models(provider)
        if cached:
            self.current_models = cached
            self.filtered_models = cached
            self.display_models()
            self.update_model_dropdown()
            self.update_status("Models loaded from cache", "#0066cc")

    def on_recent_selected(self, event=None):
        """Handle recently used model selection."""
        selected = self.recent_combo.get()
        if selected:
            self.default_model_var.set(selected)

    def toggle_show_key(self):
        """Toggle API key visibility."""
        if self.api_key_entry.cget("show") == "•":
            self.api_key_entry.config(show="")
            self.show_key_button.config(text="Hide")
        else:
            self.api_key_entry.config(show="•")
            self.show_key_button.config(text="Show")

    def validate_inputs(self) -> bool:
        """Validate user inputs before saving."""
        base_url = self.base_url_var.get().strip()
        api_key = self.api_key_var.get().strip()

        if not base_url:
            messagebox.showerror("Validation Error", "Base URL cannot be empty")
            return False

        if not re.match(r"^https?://", base_url):
            messagebox.showerror("Validation Error", "Base URL must start with http:// or https://")
            return False

        if not api_key:
            messagebox.showerror("Validation Error", "API Key cannot be empty")
            return False

        if len(api_key) < 5:
            messagebox.showerror("Validation Error", "API Key appears too short (min 5 characters)")
            return False

        return True

    def save_provider(self):
        """Save current provider settings."""
        if not self.validate_inputs():
            return

        provider = self.provider_var.get()
        settings = {
            "base_url": self.base_url_var.get().strip(),
            "api_key": self.api_key_var.get().strip(),
            "default_model": self.default_model_var.get()
        }
        self.settings_manager.save_provider(provider, settings)
        self.file_logger.log_provider_saved(provider)
        self.update_status("Provider saved", "#008000")

    def test_connection(self):
        """Test connection in background thread."""
        provider = self.provider_var.get()
        base_url = self.base_url_var.get()
        api_key = self.api_key_var.get()

        if not api_key or not base_url:
            self.update_status("Missing API key or base URL", "#ff0000")
            return

        self.update_status("Testing connection...", "#0066cc")
        thread = threading.Thread(target=self._test_connection_bg, args=(base_url, api_key), daemon=True)
        thread.start()

    def _test_connection_bg(self, base_url, api_key):
        """Background thread for connection testing."""
        provider = self.provider_var.get()
        success, message, latency = APIClient.test_connection(base_url, api_key, provider)
        self.last_latency = latency
        status_color = "#008000" if success else "#ff0000"
        self.update_status(message, status_color)

    def fetch_models(self):
        """Fetch models in background thread."""
        base_url = self.base_url_var.get()
        api_key = self.api_key_var.get()

        if not api_key or not base_url:
            self.update_status("Missing API key or base URL", "#ff0000")
            return

        self.update_status("Fetching models...", "#0066cc")
        thread = threading.Thread(target=self._fetch_models_bg, args=(base_url, api_key), daemon=True)
        thread.start()

    def _fetch_models_bg(self, base_url, api_key):
        """Background thread for model fetching."""
        provider = self.provider_var.get()
        models, error, latency = APIClient.fetch_models(base_url, api_key, provider)
        self.last_latency = latency
        self.current_models = models
        self.filtered_models = models

        if models:
            self.settings_manager.cache_models(provider, models)

        self.display_models()
        self.update_model_dropdown()

        if error:
            self.update_status(f"Error: {error}", "#ff0000")
        else:
            self.update_status(f"Fetched {len(models)} models ({latency:.0f}ms)", "#008000")

    def filter_models(self, *args):
        """Filter models based on search."""
        search_text = self.search_var.get().lower()
        if search_text:
            self.filtered_models = [m for m in self.current_models if search_text in m["id"].lower()]
        else:
            self.filtered_models = self.current_models
        self.display_models()

    def display_models(self):
        """Display filtered models in text widget."""
        self.models_text.config(state=tk.NORMAL)
        self.models_text.delete("1.0", tk.END)
        for model in self.filtered_models:
            self.models_text.insert(tk.END, model["id"] + "\n")
        self.models_text.config(state=tk.NORMAL)

    def on_model_click(self, event):
        """Handle model selection from text widget."""
        try:
            line_num = int(self.models_text.index(tk.CURRENT).split('.')[0])
            line_text = self.models_text.get(f"{line_num}.0", f"{line_num}.end").strip()
            if line_text:
                self.default_model_var.set(line_text)
                provider = self.provider_var.get()
                self.settings_manager.add_recently_used_model(provider, line_text)
                self.update_recently_used()
        except Exception:
            pass

    def update_model_dropdown(self):
        """Update model dropdown with current models."""
        model_ids = [m["id"] for m in self.current_models]
        self.model_combo.config(values=model_ids)

    def update_recently_used(self):
        """Update recently used models dropdown."""
        provider = self.provider_var.get()
        recent = self.settings_manager.get_recently_used_models(provider)
        self.recent_combo.config(values=recent)

    def delete_provider(self):
        """Delete current provider."""
        provider = self.provider_var.get()
        if messagebox.askyesno("Delete Provider", f"Delete {provider}?"):
            self.settings_manager.delete_provider(provider)
            self.update_status(f"Provider {provider} deleted", "#008000")

    def delete_all(self):
        """Delete all providers."""
        if messagebox.askyesno("Delete All", "Delete ALL saved providers? This cannot be undone."):
            self.settings_manager.delete_all_providers()
            self.update_status("All providers deleted", "#008000")

    def set_as_default(self):
        """Set current provider as default."""
        provider = self.provider_var.get()
        self.settings_manager.set_default_provider(provider)
        self.update_status(f"Default provider set to {provider}", "#008000")

    def import_settings(self):
        """Import settings from file."""
        filepath = filedialog.askopenfilename(filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if filepath:
            self.settings_manager.import_settings(filepath, merge=True)
            self.update_status("Settings imported", "#008000")
            self.update_provider_display()

    def export_settings(self):
        """Export settings to file."""
        filepath = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if filepath:
            self.settings_manager.export_settings(filepath)
            self.update_status("Settings exported", "#008000")

    def export_favorites(self):
        """Export selected providers only."""
        providers = self.settings_manager.list_providers()
        if not providers:
            messagebox.showwarning("No Providers", "No providers to export")
            return

        from tkinter.simpledialog import askstring
        from tkinter import Listbox, Scrollbar

        top = tk.Toplevel(self.root)
        top.title("Select Favorites to Export")
        top.geometry("300x300")

        listbox = Listbox(top, selectmode="multiple")
        listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        for provider in providers:
            listbox.insert(tk.END, provider)

        def save_favorites():
            selected = [providers[i] for i in listbox.curselection()]
            if not selected:
                messagebox.showwarning("None Selected", "Select at least one provider")
                return
            filepath = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
            if filepath:
                self.settings_manager.export_favorites(filepath, selected)
                self.update_status(f"Exported {len(selected)} providers", "#008000")
            top.destroy()

        ttk.Button(top, text="Export Selected", command=save_favorites).pack(pady=5)

    def update_provider_display(self):
        """Update display when provider changes."""
        self.on_provider_changed()

    def update_status(self, message, color):
        """Update status label."""
        self.status_label.config(text=message, foreground=color)
        self.root.after(5000, lambda: self.status_label.config(text="Ready", foreground="#008000"))

    def start_background_sync(self):
        """Start background sync of models every 15 minutes."""
        def sync_loop():
            import time
            while True:
                try:
                    time.sleep(900)
                    provider = self.provider_var.get()
                    base_url = self.base_url_var.get()
                    api_key = self.api_key_var.get()
                    if base_url and api_key:
                        models, error, latency = APIClient.fetch_models(base_url, api_key, provider)
                        if models:
                            self.current_models = models
                            self.filtered_models = models
                            self.settings_manager.cache_models(provider, models)
                except Exception:
                    pass

        self.sync_thread = threading.Thread(target=sync_loop, daemon=True)
        self.sync_thread.start()

    def open_key_manager(self):
        """Open the key manager window."""
        KeyManagerWindow(self.root)

    def open_debug_console(self):
        """Open the debug console window."""
        DebugWindow(self.root, self.debug_logger)

    def open_log_viewer(self):
        """Open the log viewer window."""
        LogViewerWindow(self.root, self.file_logger)

    def open_anthropic_models(self):
        """Open the Anthropic models manager window."""
        AnthropicModelsManager(self.root)

    def on_shutdown(self):
        """Handle app shutdown."""
        self.file_logger.log_info("Application closing")
        self.file_logger.shutdown()
