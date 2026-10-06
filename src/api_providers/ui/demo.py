"""Tabbed integration playground. Workers never read or mutate Tk widgets."""
import queue
import threading
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from ..client import AIClient
from ..conversation import Conversation
from ..types import AIError
from . import open_settings


class DemoApp(ttk.Frame):
    def __init__(self, parent, client=None):
        super().__init__(parent)
        self.client = client if client is not None else AIClient("integration-demo")
        self.conversation = Conversation()
        self.dirty = False
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.busy = False
        self.closed = False
        self.after_id = None
        self.model_cache = {}
        self.buttons = []
        self.connection_states = {}
        self.profile = tk.StringVar(self)
        self.model = tk.StringVar(self)
        self.status = tk.StringVar(self, value="Select a saved profile and model.")
        self.chat_title = tk.StringVar(self, value="New chat")
        self.connection = tk.StringVar(self, value="Connection not tested")
        self.endpoint = tk.StringVar(self)
        self.provider_name = tk.StringVar(self)
        self.temperature = tk.StringVar(self)
        self.max_tokens = tk.StringVar(self, value="1024")
        self.timeout = tk.StringVar(self, value=str(self.client.timeout))
        self.streaming = tk.BooleanVar(self, value=True)
        prefs = self.client.store.app_preferences(self.client.app_id)
        if prefs.get("temperature") is not None:
            self.temperature.set(str(prefs["temperature"]))
        self.max_tokens.set(str(prefs.get("max_tokens", 1024)))

        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Label(toolbar, text="Profile").pack(side="left")
        self.profile_box = ttk.Combobox(toolbar, textvariable=self.profile, state="readonly", width=22)
        self.profile_box.pack(side="left", padx=5)
        ttk.Label(toolbar, text="Model").pack(side="left")
        self.model_box = ttk.Combobox(toolbar, textvariable=self.model, width=30)
        self.model_box.pack(side="left", padx=5, fill="x", expand=True)
        self.button(toolbar, "Refresh models", self.fetch_models).pack(side="left", padx=3)
        self.button(toolbar, "AI Settings", self.settings).pack(side="left", padx=3)
        self.profile_box.bind("<<ComboboxSelected>>", self.profile_changed)
        self.model_box.bind("<<ComboboxSelected>>", self.model_changed)
        self.model_box.bind("<FocusOut>", self.model_changed)

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True)
        self.chat_tab, self.connection_tab, self.request_tab, self.activity_tab = [ttk.Frame(self.tabs, padding=10) for _ in range(4)]
        for title, tab in zip(("Chat", "Connection Status", "Request Settings", "Activity Log"),
                              (self.chat_tab, self.connection_tab, self.request_tab, self.activity_tab)):
            self.tabs.add(tab, text=title)
        self.build_chat()
        self.build_connection()
        self.build_requests()
        self.build_activity()
        ttk.Label(self, textvariable=self.status, wraplength=780).pack(fill="x", pady=5)
        self.refresh_profiles()
        self.after_id = self.after(50, self.poll)
        self.bind("<Destroy>", self.destroyed, add=True)
        self.log("Playground ready; no provider requests have been sent.")

    def button(self, parent, title, command):
        button = ttk.Button(parent, text=title, command=command)
        self.buttons.append(button)
        return button

    @staticmethod
    def text_area(parent, **kwargs):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        text = tk.Text(frame, wrap="word", **kwargs)
        bar = ttk.Scrollbar(frame, command=text.yview)
        text.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        text.pack(fill="both", expand=True)
        return text

    def build_chat(self):
        controls = ttk.Frame(self.chat_tab)
        controls.pack(fill="x")
        for label, callback in (("New Chat", self.new_chat), ("Clear", self.clear_chat),
                                ("Save Chat", self.save_chat), ("Load Chat", self.load_chat)):
            self.button(controls, label, callback).pack(side="left", padx=3)
        ttk.Label(self.chat_tab, textvariable=self.chat_title).pack(anchor="w", pady=6)
        self.output = self.text_area(self.chat_tab, height=14, width=90, state="disabled")
        self.output.tag_configure("user", foreground="#145da0")
        self.output.tag_configure("assistant", foreground="#176b36")
        self.output.tag_configure("notice", foreground="#8a4b08")
        ttk.Label(self.chat_tab, text="Message — previous completed turns are sent with each follow-up.").pack(anchor="w", pady=(8, 2))
        self.prompt = self.text_area(self.chat_tab, height=4, width=90)
        actions = ttk.Frame(self.chat_tab)
        actions.pack(fill="x", pady=6)
        self.send = self.button(actions, "Send", self.generate)
        self.send.pack(side="left")
        self.cancel_button = ttk.Button(actions, text="Cancel", command=self.cancel_request, state="disabled")
        self.cancel_button.pack(side="left", padx=5)

    def build_connection(self):
        for label, variable in (("Provider", self.provider_name), ("Endpoint", self.endpoint), ("Status", self.connection)):
            ttk.Label(self.connection_tab, text=label).pack(anchor="w", pady=(8, 0))
            ttk.Label(self.connection_tab, textvariable=variable, wraplength=700).pack(anchor="w")
        self.button(self.connection_tab, "Test selected profile", self.test_connection).pack(anchor="w", pady=12)
        self.button(self.connection_tab, "Reload saved profiles", self.refresh_profiles).pack(anchor="w")
        ttk.Label(self.connection_tab, text="The test checks the model endpoint. It does not send a billable generation request.\nSwitching profiles retains this chat's history. Use New Chat to start separate context.", wraplength=700).pack(anchor="w", pady=10)

    def build_requests(self):
        ttk.Label(self.request_tab, text="System instructions").pack(anchor="w")
        self.system = self.text_area(self.request_tab, height=5, width=80)
        fields = ttk.Frame(self.request_tab)
        fields.pack(fill="x", pady=10)
        for row, (label, variable) in enumerate((("Temperature (blank = provider default)", self.temperature),
                                                ("Maximum output tokens", self.max_tokens),
                                                ("Timeout in seconds", self.timeout))):
            ttk.Label(fields, text=label).grid(row=row, column=0, sticky="w", pady=4)
            ttk.Entry(fields, textvariable=variable, width=16).grid(row=row, column=1, sticky="w", padx=10)
        ttk.Checkbutton(self.request_tab, text="Stream response", variable=self.streaming).pack(anchor="w")
        self.button(self.request_tab, "Save request preferences", self.save_request_settings).pack(anchor="w", pady=10)
        ttk.Label(self.request_tab, text="Temperature and token limit are saved for this application ID. System instructions, timeout and streaming are session settings. Some models reject optional parameters.", wraplength=700).pack(anchor="w")

    def build_activity(self):
        ttk.Label(self.activity_tab, text="Activity excludes credentials, prompts and response contents.").pack(anchor="w", pady=5)
        self.activity = self.text_area(self.activity_tab, height=16, width=90, state="disabled")
        ttk.Button(self.activity_tab, text="Clear log", command=self.clear_log).pack(anchor="w", pady=6)

    def log(self, message):
        self.activity.configure(state="normal")
        self.activity.insert("end", datetime.now().astimezone().strftime("%m-%d-%y %I:%M:%S %p") + "  " + message + "\n")
        self.activity.see("end")
        self.activity.configure(state="disabled")

    def clear_log(self):
        self.activity.configure(state="normal")
        self.activity.delete("1.0", "end")
        self.activity.configure(state="disabled")

    def append(self, text, tag=None):
        self.output.configure(state="normal")
        self.output.insert("end", text, (tag,) if tag else ())
        self.output.see("end")
        self.output.configure(state="disabled")

    def render_chat(self):
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")
        for message in self.conversation.messages:
            self.append(message["role"].title() + ":\n", message["role"])
            self.append(message["content"] + "\n\n")
        self.chat_title.set(self.conversation.title)

    def settings(self):
        open_settings(self, self.client, on_saved=lambda client: self.refresh_profiles())

    def refresh_profiles(self):
        if self.busy:
            return
        try:
            profiles = self.client.store.list_profiles()
            self.profile_box.configure(values=list(profiles))
            prefs = self.client.store.app_preferences(self.client.app_id)
            selected = prefs.get("profile")
            if selected not in profiles:
                selected = self.profile.get() if self.profile.get() in profiles else next(iter(profiles), "")
            self.profile.set(selected)
            self.model.set(prefs.get("model", "") if selected == prefs.get("profile") else profiles.get(selected, {}).get("model", ""))
            self.profile_changed(persist=False)
        except Exception as exc:
            self.status.set(str(exc))

    def profile_changed(self, event=None, persist=True):
        if self.busy:
            return
        try:
            config = self.client.store.list_profiles().get(self.profile.get(), {})
            if event is not None:
                prefs = self.client.store.app_preferences(self.client.app_id)
                self.model.set(prefs.get("model", "") if prefs.get("profile") == self.profile.get() else config.get("model", ""))
            self.model_box.configure(values=self.model_cache.get(self.profile.get(), []))
            self.provider_name.set(config.get("provider", ""))
            self.endpoint.set(config.get("base_url", ""))
            self.connection.set(self.connection_states.get(self.profile.get(), "Connection not tested"))
            if persist and self.profile.get():
                self.client.store.set_app_preferences(self.client.app_id, profile=self.profile.get(), model=self.model.get())
            self.status.set("Profile selected; refresh models or enter a model ID.")
        except Exception as exc:
            self.status.set(str(exc))

    def model_changed(self, event=None):
        if not self.busy and self.profile.get():
            try:
                self.client.store.set_app_preferences(self.client.app_id, profile=self.profile.get(), model=self.model.get().strip())
            except Exception as exc:
                self.status.set(str(exc))

    def set_busy(self, value):
        self.busy = value
        for button in self.buttons:
            button.configure(state="disabled" if value else "normal")
        self.profile_box.configure(state="disabled" if value else "readonly")
        self.model_box.configure(state="disabled" if value else "normal")

    def job(self, work, complete):
        if self.busy:
            return
        self.set_busy(True)
        self.status.set("Working...")
        def worker():
            try:
                self.events.put(("job", complete, work(), None))
            except Exception as exc:
                safe = str(exc) if isinstance(exc, AIError) else "Operation failed; check configuration."
                self.events.put(("job", complete, None, safe))
        threading.Thread(target=worker, daemon=True).start()

    def fetch_models(self):
        name = self.profile.get()
        if not name:
            self.status.set("Create a profile in AI Settings first.")
            return
        self.log("Model refresh started.")
        def ready(models):
            ids = [model.id for model in models]
            self.model_cache[name] = ids
            self.model_box.configure(values=ids)
            if not self.model.get() and ids:
                self.model.set(ids[0])
                self.model_changed()
            self.status.set("Found %s models." % len(ids))
            self.log("Model refresh completed: %s models." % len(ids))
        self.job(lambda: self.client.list_models(name), ready)

    def test_connection(self):
        name = self.profile.get()
        self.log("Connection test started.")
        def ready(result):
            message = result.message + " (%.0f ms)" % result.latency_ms
            self.connection_states[name] = message
            self.connection.set(message)
            self.status.set(message)
            self.log("Connection test " + ("passed." if result.ok else "failed."))
        self.job(lambda: self.client.test_connection(name), ready)

    def request_settings(self):
        try:
            temperature = float(self.temperature.get()) if self.temperature.get().strip() else None
            tokens = int(self.max_tokens.get())
            timeout = float(self.timeout.get())
            if temperature is not None and not 0 <= temperature <= 2:
                raise ValueError()
            if tokens <= 0 or not 0 < timeout <= 3600:
                raise ValueError()
            return temperature, tokens, timeout
        except ValueError as exc:
            raise AIError("Use temperature 0–2 or blank, positive tokens, and timeout up to 3600 seconds.", "configuration") from exc

    def save_request_settings(self):
        try:
            temperature, tokens, _ = self.request_settings()
            self.client.store.set_app_preferences(self.client.app_id, temperature=temperature, max_tokens=tokens)
            self.status.set("Request preferences saved for this app.")
        except AIError as exc:
            self.status.set(str(exc))

    def generate(self):
        if self.busy:
            return
        try:
            prompt = self.prompt.get("1.0", "end").strip()
            messages = self.conversation.request_messages(prompt)
            temperature, tokens, timeout = self.request_settings()
            profile, model = self.profile.get(), self.model.get().strip()
            if not profile or not model:
                raise AIError("Select a profile and model first.", "configuration")
            self.client.store.set_app_preferences(self.client.app_id, profile=profile, model=model,
                                                  temperature=temperature, max_tokens=tokens)
            system = self.system.get("1.0", "end").strip()
            streaming = self.streaming.get()
        except AIError as exc:
            self.status.set(str(exc))
            return
        self.render_chat()
        self.append("User:\n", "user")
        self.append(prompt + "\n\n")
        self.append("Assistant:\n", "assistant")
        self.cancel.clear()
        self.set_busy(True)
        self.cancel_button.configure(state="normal")
        self.status.set("Generating...")
        self.log("Generation started with %s context messages." % len(messages))
        # Snapshot all UI state. The worker only sees ordinary Python values.
        worker_client = AIClient(self.client.app_id, self.client.store, timeout, self.client.session)
        def worker():
            chunks = []
            try:
                kwargs = dict(messages=messages, system=system, profile=profile, model=model,
                              temperature=temperature, max_tokens=tokens)
                if streaming:
                    for event in worker_client.stream(cancel=self.cancel, **kwargs):
                        if event.text:
                            chunks.append(event.text)
                            self.events.put(("text", event.text))
                else:
                    if self.cancel.is_set():
                        raise AIError("Request cancelled.", "cancelled")
                    result = worker_client.generate(**kwargs)
                    chunks.append(result.text)
                    self.events.put(("text", result.text))
                if self.cancel.is_set():
                    raise AIError("Request cancelled.", "cancelled")
                if not "".join(chunks).strip():
                    raise AIError("Provider returned no text; turn was not added to context.", "protocol")
                self.events.put(("complete", prompt, "".join(chunks)))
            except Exception as exc:
                safe = str(exc) if isinstance(exc, AIError) else "Generation failed; check provider configuration."
                self.events.put(("error", safe))
        threading.Thread(target=worker, daemon=True).start()

    def cancel_request(self):
        self.cancel.set()
        self.cancel_button.configure(state="disabled")
        self.status.set("Cancelling; waiting for the current network read...")
        self.log("Cancellation requested.")

    def poll(self):
        if self.closed:
            return
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "text":
                    self.append(event[1])
                elif kind == "complete":
                    if self.cancel.is_set():
                        self.finish_error("Request cancelled; turn was not added to context.")
                    else:
                        self.conversation.complete_turn(event[1], event[2])
                        self.dirty = True
                        self.chat_title.set(self.conversation.title)
                        self.prompt.delete("1.0", "end")
                        self.append("\n\n")
                        self.set_busy(False)
                        self.cancel_button.configure(state="disabled")
                        self.status.set("Complete — %s saved conversation turns." % (len(self.conversation.messages) // 2))
                        self.log("Generation completed.")
                elif kind == "error":
                    self.finish_error(event[1])
                elif kind == "job":
                    self.set_busy(False)
                    if event[3]:
                        self.status.set(event[3])
                        self.log(event[3])
                    else:
                        event[1](event[2])
        except queue.Empty:
            pass
        self.after_id = self.after(50, self.poll)

    def finish_error(self, message):
        self.append("\n[" + message + "]\n[This turn is excluded from future context.]\n\n", "notice")
        self.set_busy(False)
        self.cancel_button.configure(state="disabled")
        self.status.set(message)
        self.log(message)

    def allow_replace(self):
        return not self.dirty or messagebox.askyesno("Unsaved chat", "Discard unsaved conversation changes?", parent=self)

    def new_chat(self):
        if not self.busy and self.allow_replace():
            self.conversation = Conversation()
            self.dirty = False
            self.prompt.delete("1.0", "end")
            self.render_chat()
            self.log("New chat started.")

    def clear_chat(self):
        if not self.busy and self.allow_replace():
            self.conversation.clear()
            self.dirty = True
            self.prompt.delete("1.0", "end")
            self.render_chat()
            self.log("Chat history cleared.")

    def save_chat(self):
        if self.busy:
            return
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".json", filetypes=[("Chat JSON", "*.json")])
        if path:
            try:
                self.conversation.save(path)
                self.dirty = False
                self.status.set("Chat saved.")
                self.log("Chat saved; no credentials included.")
            except OSError:
                self.status.set("Could not save chat file.")

    def load_chat(self):
        if self.busy:
            return
        path = filedialog.askopenfilename(parent=self, filetypes=[("Chat JSON", "*.json")])
        if path:
            try:
                chat = Conversation.load(path)
                if not self.allow_replace():
                    return
                self.conversation = chat
                self.dirty = False
                self.prompt.delete("1.0", "end")
                self.render_chat()
                self.status.set("Chat loaded; follow-ups will use this history.")
                self.log("Chat loaded.")
            except AIError as exc:
                self.status.set(str(exc))

    def destroyed(self, event):
        if event.widget is self:
            self.closed = True
            self.cancel.set()
            if self.after_id:
                self.after_cancel(self.after_id)
                self.after_id = None
