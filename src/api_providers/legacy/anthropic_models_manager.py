import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from .api_client import APIClient


class AnthropicModelsManager:
    """Manager for updating Anthropic models list."""

    def __init__(self, parent):
        """Initialize models manager window."""
        self.parent = parent
        self.window = tk.Toplevel(parent)
        self.window.title("Update Anthropic Models")
        self.window.geometry("600x400")
        self.window.resizable(True, True)

        self.bg_color = "#f5f5f5"
        self.fg_color = "#1a1a1a"
        self.window.configure(bg=self.bg_color)

        self.setup_ui()
        self.load_current_models()

    def setup_ui(self):
        """Setup user interface."""
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text="Anthropic Models", font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(0, 10))

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=5)
        ttk.Button(button_frame, text="Fetch from URL", command=self.fetch_from_url).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Add Model", command=self.add_model).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Remove Selected", command=self.remove_model).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Reset to Defaults", command=self.reset_defaults).pack(side=tk.LEFT, padx=2)

        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill=tk.X, pady=5)
        self.info_label = ttk.Label(info_frame, text="Loading...")
        self.info_label.pack(anchor=tk.W)

        ttk.Label(main_frame, text="Current Models:").pack(anchor=tk.W, pady=(10, 5))

        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.models_listbox = tk.Listbox(
            list_frame,
            bg="#ffffff",
            fg=self.fg_color,
            yscrollcommand=scrollbar.set,
            selectmode=tk.SINGLE
        )
        scrollbar.config(command=self.models_listbox.yview)
        self.models_listbox.pack(fill=tk.BOTH, expand=True)

        button_frame2 = ttk.Frame(main_frame)
        button_frame2.pack(fill=tk.X, pady=5)
        ttk.Button(button_frame2, text="Save Changes", command=self.save_models).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame2, text="Close", command=self.window.destroy).pack(side=tk.LEFT, padx=2)

    def load_current_models(self):
        """Load current models into listbox."""
        self.models_listbox.delete(0, tk.END)
        models = APIClient.get_anthropic_models()
        for model in models:
            self.models_listbox.insert(tk.END, model)
        self.info_label.config(text=f"Total: {len(models)} models")

    def fetch_from_url(self):
        """Fetch models from a remote URL."""
        url = simpledialog.askstring(
            "Fetch Models",
            "Enter URL to fetch Anthropic models from:\n(should return JSON list or {\"models\": [...]})"
        )
        if not url:
            return

        self.info_label.config(text="Fetching...")
        self.window.update()

        success, message, models = APIClient.fetch_anthropic_models_from_url(url)
        if success:
            self.models_listbox.delete(0, tk.END)
            for model in models:
                self.models_listbox.insert(tk.END, model)
            self.info_label.config(text=f"✓ {message}")
        else:
            self.info_label.config(text=f"✗ {message}")
            messagebox.showerror("Error", f"Failed to fetch models:\n{message}")

    def add_model(self):
        """Add a new model."""
        model_id = simpledialog.askstring("Add Model", "Enter model ID:")
        if model_id:
            self.models_listbox.insert(tk.END, model_id.strip())
            self.info_label.config(text=f"Total: {self.models_listbox.size()} models")

    def remove_model(self):
        """Remove selected model."""
        selection = self.models_listbox.curselection()
        if selection:
            self.models_listbox.delete(selection[0])
            self.info_label.config(text=f"Total: {self.models_listbox.size()} models")

    def reset_defaults(self):
        """Reset to default models."""
        if messagebox.askyesno("Reset", "Reset to default Anthropic models?"):
            from .constants import PROVIDERS
            defaults = PROVIDERS["Anthropic"].get("models", [])
            self.models_listbox.delete(0, tk.END)
            for model in defaults:
                self.models_listbox.insert(tk.END, model)
            self.info_label.config(text=f"Total: {len(defaults)} models (reset to defaults)")

    def save_models(self):
        """Save models to file."""
        models = list(self.models_listbox.get(0, tk.END))
        if not models:
            messagebox.showwarning("Empty", "No models to save")
            return

        success, message = APIClient.save_anthropic_models(models)
        if success:
            self.info_label.config(text=f"✓ {message}")
            messagebox.showinfo("Success", message)
        else:
            self.info_label.config(text=f"✗ {message}")
            messagebox.showerror("Error", message)
