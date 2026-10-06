"""Optional Tkinter integration; host owns styles and the event loop."""
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from ..client import AIClient
from ..providers import DEFAULTS, REGISTRY


class ProviderSettingsPanel(ttk.Frame):
    def __init__(self, parent, client, on_saved=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.client, self.on_saved = client, on_saved
        self.results = queue.Queue()
        self.closed = False
        self.busy = False
        self.after_id = None
        self.profile = tk.StringVar(self)
        self.provider = tk.StringVar(self, value="OpenRouter")
        self.url = tk.StringVar(self, value=DEFAULTS["OpenRouter"])
        self.key = tk.StringVar(self)
        self.model = tk.StringVar(self)
        self.status = tk.StringVar(self, value="Shared credentials; model selection applies to this app.")
        self.profile_box = self._row(0, "Profile name", self.profile, combo=True)
        self.provider_box = self._row(1, "Provider", self.provider, combo=True, values=list(REGISTRY))
        self.provider_box.configure(state="readonly")
        self._row(2, "Base URL", self.url)
        self.key_entry = self._row(3, "API key", self.key)
        self.key_entry.configure(show="*")
        self.model_box = self._row(4, "Model for this app", self.model, combo=True)
        ttk.Label(self, text="Leave the key blank to keep a saved credential. Local servers may need no key.",
                  wraplength=500).grid(row=5, column=0, columnspan=2, sticky="w", pady=5)
        buttons = ttk.Frame(self)
        buttons.grid(row=6, column=0, columnspan=2, sticky="ew", pady=8)
        self.actions = []
        for label, action in (("Save", self.save), ("Fetch models", self.fetch_models),
                              ("Test", self.test), ("Import", self.import_settings),
                              ("Export", self.export_settings), ("Migrate old settings", self.migrate)):
            button = ttk.Button(buttons, text=label, command=action)
            button.pack(side="left", padx=2)
            self.actions.append(button)
        ttk.Label(self, textvariable=self.status, wraplength=560).grid(row=7, column=0, columnspan=2, sticky="w")
        self.columnconfigure(1, weight=1)
        self.profile_box.bind("<<ComboboxSelected>>", self.load)
        self.provider_box.bind("<<ComboboxSelected>>", self.change_provider)
        self.refresh()
        self.after_id = self.after(50, self.poll)
        self.bind("<Destroy>", self.destroyed, add=True)

    def _row(self, row, label, variable, combo=False, values=()):
        ttk.Label(self, text=label).grid(row=row, column=0, sticky="w", padx=5, pady=5)
        widget = ttk.Combobox(self, textvariable=variable, values=values) if combo else ttk.Entry(self, textvariable=variable)
        widget.grid(row=row, column=1, sticky="ew", padx=5, pady=5)
        return widget

    def refresh(self):
        try:
            profiles = self.client.store.list_profiles()
            self.profile_box.configure(values=list(profiles))
            prefs = self.client.store.app_preferences(self.client.app_id)
            name = prefs.get("profile")
            if name in profiles:
                self.profile.set(name)
                self.load()
        except Exception as exc:
            self.status.set(str(exc))

    def load(self, event=None):
        # Loading metadata does not expose the key in the UI or require a secret backend.
        profile = self.client.store.list_profiles().get(self.profile.get())
        if profile:
            self.provider.set(profile["provider"])
            self.url.set(profile["base_url"])
            prefs = self.client.store.app_preferences(self.client.app_id)
            self.model.set(prefs.get("model", profile.get("model", "")) if prefs.get("profile") == self.profile.get() else profile.get("model", ""))
            self.key.set("")
            self.model_box.configure(values=())

    def change_provider(self, event=None):
        self.url.set(DEFAULTS[self.provider.get()])
        self.key.set("")
        self.model.set("")
        self.model_box.configure(values=())

    def save(self):
        try:
            name = self.profile.get().strip() or self.provider.get()
            if not self.url.get().strip():
                raise ValueError("Base URL is required.")
            # Validate URL without contacting a provider or retrieving secrets.
            adapter = REGISTRY[self.provider.get()](self.provider.get(), self.url.get().strip())
            adapter.close()
            self.client.store.save_profile(name, self.provider.get(), self.url.get().strip(),
                                           self.key.get().strip() or None)
            self.client.store.set_app_preferences(self.client.app_id, profile=name, model=self.model.get().strip())
            self.profile.set(name)
            self.key.set("")
            self.profile_box.configure(values=list(self.client.store.list_profiles()))
            self.status.set("Saved settings for " + self.client.app_id)
            if self.on_saved:
                self.on_saved(self.client)
            return True
        except Exception as exc:
            self.status.set(str(exc))
            return False

    def run_job(self, work, complete):
        if self.busy:
            return
        self.busy = True
        for button in self.actions:
            button.configure(state="disabled")
        self.status.set("Working...")
        def worker():
            try:
                self.results.put((complete, work(), None))
            except Exception as exc:
                self.results.put((complete, None, str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def fetch_models(self):
        if self.save():
            name = self.profile.get()
            self.run_job(lambda: self.client.list_models(name), self.models_ready)

    def models_ready(self, models):
        ids = [model.id for model in models]
        self.model_box.configure(values=ids)
        self.status.set("Found %s models. Select one and save." % len(ids))

    def test(self):
        if self.save():
            name = self.profile.get()
            self.run_job(lambda: self.client.test_connection(name),
                         lambda result: self.status.set(result.message))

    def poll(self):
        if self.closed:
            return
        try:
            while True:
                complete, value, error = self.results.get_nowait()
                self.busy = False
                for button in self.actions:
                    button.configure(state="normal")
                if error:
                    self.status.set(error)
                else:
                    complete(value)
        except queue.Empty:
            pass
        self.after_id = self.after(50, self.poll)

    def import_settings(self):
        path = filedialog.askopenfilename(parent=self, filetypes=[("Settings JSON", "*.json")])
        if path:
            try:
                self.client.store.import_settings(path)
                self.refresh()
                self.status.set("Imported profiles. Credentials are kept locally.")
            except Exception as exc:
                self.status.set(str(exc))

    def export_settings(self):
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".json", filetypes=[("Settings JSON", "*.json")])
        if path:
            try:
                self.client.store.export_settings(path)
                self.status.set("Exported settings without credentials.")
            except Exception as exc:
                self.status.set(str(exc))

    def migrate(self):
        self.run_job(self.client.store.migrate_legacy, self.migrated)

    def migrated(self, count):
        self.refresh()
        self.status.set("Migrated %s profiles. Original settings retained." % count)

    def destroyed(self, event):
        if event.widget is self:
            self.closed = True
            if self.after_id:
                self.after_cancel(self.after_id)
                self.after_id = None


def open_settings(parent, client=None, on_saved=None):
    """Open a child window; never create a root or start a nested mainloop."""
    client = client if client is not None else AIClient()
    window = tk.Toplevel(parent)
    window.title("AI Settings — " + client.app_id)
    ProviderSettingsPanel(window, client, on_saved).pack(fill="both", expand=True, padx=12, pady=12)
    return window
