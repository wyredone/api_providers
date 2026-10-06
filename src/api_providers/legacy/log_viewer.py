import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
from .file_logger import FileLogger


class LogViewerWindow:
    """Window for viewing and managing log files."""

    def __init__(self, parent, file_logger: FileLogger):
        """Initialize log viewer window."""
        self.parent = parent
        self.file_logger = file_logger

        self.window = tk.Toplevel(parent)
        self.window.title("Log Viewer")
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

        ttk.Label(main_frame, text="Application Logs", font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(0, 10))

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=5)
        ttk.Button(button_frame, text="Refresh", command=self.refresh_logs).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Recent (50 lines)", command=self.show_recent).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Open in Editor", command=self.open_in_editor).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Export Log", command=self.export_log).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Clear Old Logs", command=self.clear_old_logs).pack(side=tk.LEFT, padx=2)

        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill=tk.X, pady=5)
        self.info_label = ttk.Label(info_frame, text="Loading...")
        self.info_label.pack(anchor=tk.W)

        ttk.Label(main_frame, text="Log Files").pack(anchor=tk.W, pady=(10, 5))

        file_frame = ttk.Frame(main_frame)
        file_frame.pack(fill=tk.X, pady=5)

        scrollbar = ttk.Scrollbar(file_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.file_list = tk.Listbox(
            file_frame,
            height=3,
            bg="#ffffff",
            fg=self.fg_color,
            yscrollcommand=scrollbar.set
        )
        scrollbar.config(command=self.file_list.yview)
        self.file_list.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Log Contents").pack(anchor=tk.W, pady=(10, 5))

        scroll = ttk.Scrollbar(main_frame)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.log_text = tk.Text(
            main_frame,
            height=30,
            wrap=tk.WORD,
            bg="#ffffff",
            fg=self.fg_color,
            font=("Courier", 9),
            yscrollcommand=scroll.set
        )
        scroll.config(command=self.log_text.yview)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=(5, 0))
        self.status_label = ttk.Label(status_frame, text="Ready")
        self.status_label.pack(anchor=tk.W)

    def refresh_logs(self):
        """Refresh log display."""
        self.file_list.delete(0, tk.END)

        log_files = self.file_logger.get_log_files()

        if log_files:
            self.info_label.config(text=f"Found {len(log_files)} log file(s)")

            for log_file in log_files:
                size_kb = log_file["size"] / 1024
                mtime = datetime.fromtimestamp(log_file["mtime"]).strftime("%Y-%m-%d %H:%M:%S")
                self.file_list.insert(tk.END, f"{log_file['name']} ({size_kb:.1f}KB) - {mtime}")

            self.file_list.select_set(0)
            self.show_current_log()
        else:
            self.info_label.config(text="No log files found")
            self.log_text.config(state=tk.NORMAL)
            self.log_text.delete("1.0", tk.END)
            self.log_text.insert(tk.END, "No logs available")
            self.log_text.config(state=tk.DISABLED)

    def show_current_log(self):
        """Show currently selected log file."""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)

        log_content = self.file_logger.read_logs()
        self.log_text.insert(tk.END, log_content)
        self.log_text.config(state=tk.DISABLED)
        self.log_text.see(tk.END)

    def show_recent(self):
        """Show recent 50 lines."""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)

        log_content = self.file_logger.get_recent_logs(50)
        self.log_text.insert(tk.END, log_content)
        self.log_text.config(state=tk.DISABLED)
        self.log_text.see(tk.END)

    def open_in_editor(self):
        """Open log file in default text editor."""
        try:
            import subprocess
            import platform

            log_file = str(self.file_logger.log_file)

            if platform.system() == "Windows":
                subprocess.Popen(["notepad", log_file])
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", "-a", "TextEdit", log_file])
            else:
                subprocess.Popen(["xdg-open", log_file])

            self.status_label.config(text="Opening log in editor...")
            self.window.after(2000, lambda: self.status_label.config(text="Ready"))
        except Exception as e:
            messagebox.showerror("Error", f"Could not open editor: {str(e)}")

    def export_log(self):
        """Export log to file."""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filepath:
            try:
                log_content = self.file_logger.read_logs()
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(log_content)
                messagebox.showinfo("Success", f"Log exported to:\n{filepath}")
                self.status_label.config(text="Log exported")
                self.window.after(3000, lambda: self.status_label.config(text="Ready"))
            except Exception as e:
                messagebox.showerror("Error", f"Could not export log: {str(e)}")

    def clear_old_logs(self):
        """Clear old log backups."""
        if messagebox.askyesno("Clear Old Logs", "Delete all old log backups (keep current)?"):
            self.file_logger.clear_old_logs()
            self.refresh_logs()
            self.status_label.config(text="Old logs deleted")
            self.window.after(3000, lambda: self.status_label.config(text="Ready"))
