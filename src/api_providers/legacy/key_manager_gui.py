import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
import pyperclip
from .key_manager import KeyManager


class KeyManagerWindow:
    """GUI window for managing API keys."""

    def __init__(self, parent):
        """Initialize key manager window."""
        self.parent = parent
        self.key_manager = KeyManager()
        self.key_visibility = {}

        self.window = tk.Toplevel(parent)
        self.window.title("API Key Manager")
        self.window.geometry("1000x600")
        self.window.resizable(True, True)

        self.bg_color = "#f5f5f5"
        self.fg_color = "#1a1a1a"
        self.window.configure(bg=self.bg_color)

        self.setup_ui()
        self.refresh_keys_list()

    def setup_ui(self):
        """Setup user interface."""
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text="API Key Manager", font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(0, 10))

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=5)
        ttk.Button(button_frame, text="Refresh", command=self.refresh_keys_list).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Export All Keys", command=self.export_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Import Keys", command=self.import_keys).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Backup All", command=self.backup_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Restore Backup", command=self.restore_backup).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="View Backups", command=self.view_backups).pack(side=tk.LEFT, padx=2)

        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill=tk.X, pady=5)
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=40)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.search_var.trace("w", self.filter_keys)

        ttk.Label(main_frame, text="Saved API Keys").pack(anchor=tk.W, pady=(10, 5))

        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(tree_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree = ttk.Treeview(
            tree_frame,
            columns=("Provider", "Saved", "Notes", "Actions"),
            show="headings",
            height=15,
            yscrollcommand=scrollbar.set
        )
        scrollbar.config(command=self.tree.yview)

        self.tree.column("Provider", width=150)
        self.tree.column("Saved", width=150)
        self.tree.column("Notes", width=300)
        self.tree.column("Actions", width=250)

        self.tree.heading("Provider", text="Provider")
        self.tree.heading("Saved", text="Saved")
        self.tree.heading("Notes", text="Notes")
        self.tree.heading("Actions", text="Actions")

        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<Button-1>", self.on_tree_click)

        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=(5, 0))
        self.status_label = ttk.Label(status_frame, text="Ready")
        self.status_label.pack(anchor=tk.W)

    def refresh_keys_list(self):
        """Refresh the keys list from disk."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        keys = self.key_manager.list_keys()
        self.all_keys = keys

        for key_data in keys:
            provider = key_data["provider"]
            saved = datetime.fromtimestamp(key_data["saved_at"]).strftime("%Y-%m-%d %H:%M")
            notes = key_data["notes"][:30] + "..." if len(key_data["notes"]) > 30 else key_data["notes"]

            self.tree.insert("", "end", iid=provider, values=(provider, saved, notes, ""))

    def filter_keys(self, *args):
        """Filter keys based on search."""
        search_text = self.search_var.get().lower()
        for item in self.tree.get_children():
            self.tree.delete(item)

        for key_data in self.all_keys:
            if search_text in key_data["provider"].lower() or search_text in key_data["notes"].lower():
                provider = key_data["provider"]
                saved = datetime.fromtimestamp(key_data["saved_at"]).strftime("%Y-%m-%d %H:%M")
                notes = key_data["notes"][:30] + "..." if len(key_data["notes"]) > 30 else key_data["notes"]
                self.tree.insert("", "end", iid=provider, values=(provider, saved, notes, ""))

    def on_tree_click(self, event):
        """Handle clicks on tree items."""
        item = self.tree.identify("item", event.x, event.y)
        if not item:
            return

        column = self.tree.identify_column(event.x)
        if column == "#4":
            self.show_key_menu(item)

    def show_key_menu(self, provider):
        """Show context menu for key."""
        menu = tk.Menu(self.window, tearoff=0)
        menu.add_command(label="View Key", command=lambda: self.view_key(provider))
        menu.add_command(label="Copy Key", command=lambda: self.copy_key(provider))
        menu.add_command(label="Edit Notes", command=lambda: self.edit_notes(provider))
        menu.add_command(label="Delete", command=lambda: self.delete_key(provider))
        menu.post(event.x_root, event.y_root)

    def view_key(self, provider):
        """View the actual API key."""
        key, notes = self.key_manager.get_key(provider)
        if key:
            top = tk.Toplevel(self.window)
            top.title(f"View Key - {provider}")
            top.geometry("500x200")
            top.resizable(False, False)

            ttk.Label(top, text=f"Provider: {provider}", font=("Arial", 10, "bold")).pack(anchor=tk.W, padx=10, pady=(10, 5))

            ttk.Label(top, text="API Key:").pack(anchor=tk.W, padx=10)
            key_text = tk.Text(top, height=4, width=50, wrap=tk.WORD)
            key_text.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)
            key_text.insert("1.0", key)
            key_text.config(state=tk.DISABLED)

            ttk.Label(top, text="Notes:").pack(anchor=tk.W, padx=10)
            notes_text = tk.Text(top, height=3, width=50, wrap=tk.WORD)
            notes_text.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)
            notes_text.insert("1.0", notes)
            notes_text.config(state=tk.DISABLED)

            ttk.Button(top, text="Copy Key", command=lambda: self.copy_to_clipboard(key)).pack(pady=10)
        else:
            messagebox.showerror("Error", "Could not retrieve key")

    def copy_key(self, provider):
        """Copy API key to clipboard."""
        key, _ = self.key_manager.get_key(provider)
        if key:
            try:
                pyperclip.copy(key)
                self.status_label.config(text=f"Copied {provider} key to clipboard")
                self.window.after(3000, lambda: self.status_label.config(text="Ready"))
            except Exception:
                messagebox.showerror("Error", "Could not copy to clipboard (pyperclip not available)")
        else:
            messagebox.showerror("Error", "Could not retrieve key")

    def copy_to_clipboard(self, text):
        """Copy text to clipboard."""
        try:
            pyperclip.copy(text)
            messagebox.showinfo("Success", "Copied to clipboard")
        except Exception:
            messagebox.showerror("Error", "Could not copy to clipboard")

    def edit_notes(self, provider):
        """Edit notes for a key."""
        key, notes = self.key_manager.get_key(provider)
        if not key:
            messagebox.showerror("Error", "Could not retrieve key")
            return

        top = tk.Toplevel(self.window)
        top.title(f"Edit Notes - {provider}")
        top.geometry("400x200")

        ttk.Label(top, text="Notes:").pack(anchor=tk.W, padx=10, pady=(10, 5))
        notes_text = tk.Text(top, height=6, width=40)
        notes_text.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)
        notes_text.insert("1.0", notes)

        def save_notes():
            new_notes = notes_text.get("1.0", tk.END).strip()
            self.key_manager.save_key(provider, key, new_notes)
            self.refresh_keys_list()
            top.destroy()
            self.status_label.config(text=f"Notes updated for {provider}")
            self.window.after(3000, lambda: self.status_label.config(text="Ready"))

        ttk.Button(top, text="Save", command=save_notes).pack(pady=10)

    def delete_key(self, provider):
        """Delete a key."""
        if messagebox.askyesno("Delete Key", f"Delete API key for {provider}?"):
            if self.key_manager.delete_key(provider):
                self.refresh_keys_list()
                self.status_label.config(text=f"Deleted {provider} key")
                self.window.after(3000, lambda: self.status_label.config(text="Ready"))
            else:
                messagebox.showerror("Error", "Could not delete key")

    def export_all(self):
        """Export all keys to file."""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filepath:
            if self.key_manager.export_keys(filepath):
                self.status_label.config(text=f"Exported to {filepath}")
                self.window.after(5000, lambda: self.status_label.config(text="Ready"))
            else:
                messagebox.showerror("Error", "Could not export keys")

    def import_keys(self):
        """Import keys from file."""
        filepath = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filepath:
            success, count, message = self.key_manager.import_keys(filepath, merge=True)
            if success:
                self.refresh_keys_list()
                self.status_label.config(text=message)
                self.window.after(3000, lambda: self.status_label.config(text="Ready"))
            else:
                messagebox.showerror("Error", message)

    def backup_all(self):
        """Create backup of all keys."""
        success, backup_path = self.key_manager.backup_keys()
        if success:
            messagebox.showinfo("Success", f"Backup created:\n{backup_path}")
            self.status_label.config(text="Backup created")
            self.window.after(3000, lambda: self.status_label.config(text="Ready"))
        else:
            messagebox.showerror("Error", "Could not create backup")

    def view_backups(self):
        """View list of backups."""
        backups = self.key_manager.list_backups()
        if not backups:
            messagebox.showinfo("Backups", "No backups found")
            return

        top = tk.Toplevel(self.window)
        top.title("Backup Files")
        top.geometry("600x300")

        tree = ttk.Treeview(top, columns=("Filename", "Size", "Created"), show="headings")
        tree.column("Filename", width=300)
        tree.column("Size", width=100)
        tree.column("Created", width=150)
        tree.heading("Filename", text="Filename")
        tree.heading("Size", text="Size (bytes)")
        tree.heading("Created", text="Created")

        for backup in backups:
            created = datetime.fromtimestamp(backup["created"]).strftime("%Y-%m-%d %H:%M:%S")
            tree.insert("", "end", values=(backup["filename"], backup["size"], created))

        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        def restore_selected():
            selection = tree.selection()
            if selection:
                for backup in backups:
                    if selection[0] == backup["filename"]:
                        success, count, msg = self.key_manager.restore_backup(backup["path"])
                        if success:
                            self.refresh_keys_list()
                            messagebox.showinfo("Success", msg)
                            top.destroy()
                        else:
                            messagebox.showerror("Error", msg)
                        break

        ttk.Button(top, text="Restore Selected", command=restore_selected).pack(pady=10)

    def restore_backup(self):
        """Restore keys from backup file."""
        filepath = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filepath:
            if messagebox.askyesno("Restore Backup", "This will overwrite current keys. Continue?"):
                success, count, message = self.key_manager.restore_backup(filepath)
                if success:
                    self.refresh_keys_list()
                    messagebox.showinfo("Success", message)
                else:
                    messagebox.showerror("Error", message)
