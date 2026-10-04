import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
import json
from debug_logger import DebugLogger


class DebugWindow:
    """Debug window showing API requests/responses."""

    def __init__(self, parent, debug_logger: DebugLogger):
        """Initialize debug window."""
        self.parent = parent
        self.debug_logger = debug_logger

        self.window = tk.Toplevel(parent)
        self.window.title("Debug Console")
        self.window.geometry("1200x700")
        self.window.resizable(True, True)

        self.bg_color = "#f5f5f5"
        self.fg_color = "#1a1a1a"
        self.window.configure(bg=self.bg_color)

        self.setup_ui()
        self.refresh_logs()

    def setup_ui(self):
        """Setup user interface."""
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text="API Debug Console", font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(0, 10))

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=5)
        ttk.Button(button_frame, text="Refresh", command=self.refresh_logs).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Clear Logs", command=self.clear_logs).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Export Logs", command=self.export_logs).pack(side=tk.LEFT, padx=2)

        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill=tk.X, pady=5)
        ttk.Label(filter_frame, text="Filter:").pack(side=tk.LEFT, padx=(0, 5))
        self.filter_var = tk.StringVar()
        filter_combo = ttk.Combobox(filter_frame, textvariable=self.filter_var, state="readonly", width=20)
        filter_combo.pack(side=tk.LEFT, padx=(0, 10))
        filter_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_logs())

        ttk.Label(main_frame, text="Request/Response Log").pack(anchor=tk.W, pady=(5, 0))

        paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, pady=5)

        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        scrollbar = ttk.Scrollbar(left_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.log_tree = ttk.Treeview(
            left_frame,
            columns=("Time", "Type", "Provider", "Status"),
            show="headings",
            yscrollcommand=scrollbar.set,
            height=20
        )
        scrollbar.config(command=self.log_tree.yview)

        self.log_tree.column("Time", width=150)
        self.log_tree.column("Type", width=80)
        self.log_tree.column("Provider", width=100)
        self.log_tree.column("Status", width=100)

        self.log_tree.heading("Time", text="Time")
        self.log_tree.heading("Type", text="Type")
        self.log_tree.heading("Provider", text="Provider")
        self.log_tree.heading("Status", text="Status")

        self.log_tree.pack(fill=tk.BOTH, expand=True)
        self.log_tree.bind("<<TreeviewSelect>>", self.on_log_select)

        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=1)

        ttk.Label(right_frame, text="Details", font=("Arial", 10, "bold")).pack(anchor=tk.W)

        detail_scroll = ttk.Scrollbar(right_frame)
        detail_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.detail_text = tk.Text(
            right_frame,
            height=30,
            width=60,
            wrap=tk.WORD,
            yscrollcommand=detail_scroll.set,
            bg="#ffffff",
            fg=self.fg_color,
            font=("Courier", 9)
        )
        detail_scroll.config(command=self.detail_text.yview)
        self.detail_text.pack(fill=tk.BOTH, expand=True)

        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=(5, 0))
        self.status_label = ttk.Label(status_frame, text="Ready")
        self.status_label.pack(anchor=tk.W)

    def refresh_logs(self):
        """Refresh logs display."""
        for item in self.log_tree.get_children():
            self.log_tree.delete(item)

        logs = self.debug_logger.get_logs()
        filter_text = self.filter_var.get()

        providers = set()
        for log in logs:
            providers.add(log["provider"])
        providers = sorted(list(providers))
        self.filter_var.set(filter_text)
        self.filter_combo.config(values=["All"] + providers)
        if filter_text and filter_text != "All":
            logs = [l for l in logs if l["provider"] == filter_text]

        for log in logs:
            timestamp = datetime.fromtimestamp(log["timestamp"]).strftime("%H:%M:%S")
            log_type = log["type"].upper()
            provider = log["provider"]

            if log["type"] == "response":
                status = f"{log.get('status_code', 'N/A')}"
            elif log["type"] == "error":
                status = "ERROR"
            else:
                status = log.get("method", "")

            self.log_tree.insert("", "end", values=(timestamp, log_type, provider, status))

    def on_log_select(self, event):
        """Handle log selection."""
        selection = self.log_tree.selection()
        if not selection:
            return

        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)

        logs = self.debug_logger.get_logs()
        filter_text = self.filter_var.get()
        if filter_text and filter_text != "All":
            logs = [l for l in logs if l["provider"] == filter_text]

        idx = int(selection[0])
        if idx < len(logs):
            log = logs[idx]
            self.display_log_details(log)

    def display_log_details(self, log):
        """Display detailed log information."""
        self.detail_text.insert(tk.END, f"Timestamp: {datetime.fromtimestamp(log['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}\n")
        self.detail_text.insert(tk.END, f"Provider: {log['provider']}\n")
        self.detail_text.insert(tk.END, f"Type: {log['type'].upper()}\n\n")

        if log["type"] == "request":
            self.detail_text.insert(tk.END, "=" * 60 + "\n")
            self.detail_text.insert(tk.END, "REQUEST\n")
            self.detail_text.insert(tk.END, "=" * 60 + "\n\n")
            self.detail_text.insert(tk.END, f"Method: {log.get('method', 'N/A')}\n")
            self.detail_text.insert(tk.END, f"URL: {log.get('url', 'N/A')}\n\n")

            self.detail_text.insert(tk.END, "Headers:\n")
            headers = log.get("headers", {})
            for key, value in headers.items():
                if key.lower() == "authorization":
                    self.detail_text.insert(tk.END, f"  {key}: Bearer ***\n")
                else:
                    self.detail_text.insert(tk.END, f"  {key}: {value}\n")

        elif log["type"] == "response":
            self.detail_text.insert(tk.END, "=" * 60 + "\n")
            self.detail_text.insert(tk.END, "RESPONSE\n")
            self.detail_text.insert(tk.END, "=" * 60 + "\n\n")
            self.detail_text.insert(tk.END, f"Status Code: {log.get('status_code', 'N/A')}\n")
            self.detail_text.insert(tk.END, f"Latency: {log.get('latency', 0):.0f}ms\n\n")

            self.detail_text.insert(tk.END, "Response Body:\n")
            response = log.get("response", "")
            if isinstance(response, dict):
                self.detail_text.insert(tk.END, json.dumps(response, indent=2))
            else:
                self.detail_text.insert(tk.END, str(response)[:1000])

        elif log["type"] == "error":
            self.detail_text.insert(tk.END, "=" * 60 + "\n")
            self.detail_text.insert(tk.END, "ERROR\n")
            self.detail_text.insert(tk.END, "=" * 60 + "\n\n")
            self.detail_text.insert(tk.END, log.get("error", "Unknown error"))

        self.detail_text.config(state=tk.DISABLED)

    def clear_logs(self):
        """Clear logs."""
        if messagebox.askyesno("Clear Logs", "Clear all debug logs?"):
            self.debug_logger.clear_logs()
            self.refresh_logs()
            self.status_label.config(text="Logs cleared")
            self.window.after(3000, lambda: self.status_label.config(text="Ready"))

    def export_logs(self):
        """Export logs to file."""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filepath:
            if self.debug_logger.export_logs(filepath):
                messagebox.showinfo("Success", f"Logs exported to:\n{filepath}")
                self.status_label.config(text="Logs exported")
                self.window.after(3000, lambda: self.status_label.config(text="Ready"))
            else:
                messagebox.showerror("Error", "Could not export logs")
