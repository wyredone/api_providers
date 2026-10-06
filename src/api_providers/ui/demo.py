"""Example host: worker threads emit queue events; all widgets stay on the UI thread."""
import queue
import threading
import tkinter as tk
from tkinter import ttk
from ..client import AIClient
from . import open_settings


class DemoApp(ttk.Frame):
    def __init__(self, parent, client=None):
        super().__init__(parent)
        self.client = client if client is not None else AIClient("integration-demo")
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.busy = False
        self.closed = False
        self.after_id = None
        ttk.Button(self, text="AI Settings", command=lambda: open_settings(self, self.client)).pack(anchor="w")
        ttk.Label(self, text="Prompt").pack(anchor="w")
        self.prompt = tk.Text(self, height=5, width=70)
        self.prompt.pack(fill="both", expand=True)
        controls = ttk.Frame(self)
        controls.pack(fill="x", pady=8)
        self.send = ttk.Button(controls, text="Generate", command=self.generate)
        self.send.pack(side="left")
        ttk.Button(controls, text="Cancel", command=self.cancel.set).pack(side="left", padx=8)
        self.output = tk.Text(self, height=15, width=70, state="disabled")
        self.output.pack(fill="both", expand=True)
        self.after_id = self.after(50, self.poll)
        self.bind("<Destroy>", self.destroyed, add=True)

    def append(self, text):
        self.output.configure(state="normal")
        self.output.insert("end", text)
        self.output.see("end")
        self.output.configure(state="disabled")

    def generate(self):
        if self.busy:
            return
        prompt = self.prompt.get("1.0", "end").strip()
        self.cancel.clear()
        self.busy = True
        self.send.configure(state="disabled")
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")
        def worker():
            try:
                for event in self.client.stream(prompt, cancel=self.cancel):
                    if event.text:
                        self.events.put(event.text)
            except Exception as exc:
                self.events.put("\n" + str(exc))
            finally:
                self.events.put(None)
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        if self.closed:
            return
        try:
            while True:
                value = self.events.get_nowait()
                if value is None:
                    self.busy = False
                    self.send.configure(state="normal")
                else:
                    self.append(value)
        except queue.Empty:
            pass
        self.after_id = self.after(50, self.poll)

    def destroyed(self, event):
        if event.widget is self:
            self.closed = True
            self.cancel.set()
            if self.after_id:
                self.after_cancel(self.after_id)
                self.after_id = None
