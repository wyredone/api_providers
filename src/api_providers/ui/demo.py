"""Tabbed integration playground. Workers never read or mutate Tk widgets."""
import queue
import threading
import time
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from ..client import AIClient
from ..conversation import Conversation
from ..types import AIError
from ..execution import RequestOptions, RequestStats, run_request
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
        self.run_started = None
        self.active_stats = None
        self.stats_text = tk.StringVar(self, value="No requests yet.")
        self.comparison_remaining = set()
        self.comparison_started = {}
        self.comparison_stats = {}
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
        self.timeout.set(str(prefs.get("timeout", self.client.timeout)))
        self.streaming.set(prefs.get("streaming", True))

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
        self.comparison_tab = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(self.comparison_tab, text="Model Comparison")
        self.build_comparison()
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
        ttk.Label(self.chat_tab, textvariable=self.stats_text, wraplength=780).pack(fill="x", pady=4)

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
        self.system.insert("1.0", self.client.store.app_preferences(self.client.app_id).get("system", ""))
        fields = ttk.Frame(self.request_tab)
        fields.pack(fill="x", pady=10)
        for row, (label, variable) in enumerate((("Temperature (blank = provider default)", self.temperature),
                                                ("Maximum output tokens", self.max_tokens),
                                                ("Timeout in seconds", self.timeout))):
            ttk.Label(fields, text=label).grid(row=row, column=0, sticky="w", pady=4)
            ttk.Entry(fields, textvariable=variable, width=16).grid(row=row, column=1, sticky="w", padx=10)
        ttk.Checkbutton(self.request_tab, text="Stream response", variable=self.streaming).pack(anchor="w")
        self.button(self.request_tab, "Save request preferences", self.save_request_settings).pack(anchor="w", pady=10)
        ttk.Label(self.request_tab, text="All generation controls are saved for this application ID using Save request preferences. Some models reject optional parameters.", wraplength=700).pack(anchor="w")

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
            if hasattr(self, "compare_profiles"):
                for box in self.compare_profiles:
                    box.configure(values=list(profiles))
                for index, variable in enumerate(self.compare_profile_vars):
                    if variable.get() not in profiles:
                        variable.set(next(iter(profiles), ""))
                    self.compare_profile_changed(index)
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
        if hasattr(self, "compare_profiles"):
            for box in self.compare_profiles:
                box.configure(state="disabled" if value else "readonly")
            for box in self.compare_models:
                box.configure(state="disabled" if value else "normal")

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

    def request_options(self):
        try:
            temperature = float(self.temperature.get()) if self.temperature.get().strip() else None
            tokens = int(self.max_tokens.get())
            timeout = float(self.timeout.get())
        except ValueError as exc:
            raise AIError("Enter numeric generation settings.", "configuration") from exc
        return RequestOptions(self.system.get("1.0", "end").strip(), temperature, tokens,
                              timeout, bool(self.streaming.get())).validate()

    def request_settings(self):
        options = self.request_options()
        return options.temperature, options.max_tokens, options.timeout

    def save_request_settings(self):
        try:
            self.client.store.set_app_preferences(self.client.app_id, **self.request_options().preferences())
            self.status.set("All request preferences saved for this app.")
        except AIError as exc:
            self.status.set(str(exc))

    def generate(self):
        if self.busy:
            return
        try:
            prompt = self.prompt.get("1.0", "end").strip()
            messages = self.conversation.request_messages(prompt)
            options = self.request_options()
            profile, model = self.profile.get(), self.model.get().strip()
            if not profile or not model:
                raise AIError("Select a profile and model first.", "configuration")
            self.client.store.set_app_preferences(self.client.app_id, profile=profile, model=model,
                                                  **options.preferences())
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
        self.run_started = time.monotonic()
        provider = self.client.store.list_profiles().get(profile, {}).get("provider", "")
        self.active_stats = RequestStats(profile, model, provider)
        self.stats_text.set(self.format_stats(self.active_stats))
        def worker():
            result = run_request(self.client, messages, options, profile, model, self.cancel,
                                 on_text=lambda text: self.events.put(("text", text)),
                                 on_stats=lambda stats: self.events.put(("stats", stats)))
            if result.error:
                self.events.put(("error", result.error))
            else:
                self.events.put(("complete", prompt, result.text))
        threading.Thread(target=worker, daemon=True).start()

    @staticmethod
    def format_stats(stats, elapsed=None):
        seconds = stats.elapsed if elapsed is None else elapsed
        first = "" if stats.first_text is None else "%.2f s" % stats.first_text
        tokens = lambda value: "" if value is None else str(value)
        return ("%s | %s / %s | %s | %.2f s | First text: %s | Input: %s | Output: %s | Total: %s"
                % (stats.status.title(), stats.provider, stats.model, stats.profile, seconds, first,
                   tokens(stats.prompt_tokens), tokens(stats.completion_tokens), tokens(stats.total_tokens)))

    def build_comparison(self):
        ttk.Label(self.comparison_tab, text="Run sends two requests using the same prompt and Request Settings. Provider charges may apply to each. Chat history is excluded.", wraplength=780).pack(anchor="w", pady=5)
        self.compare_prompt = self.text_area(self.comparison_tab, height=4, width=90)
        controls = ttk.Frame(self.comparison_tab)
        controls.pack(fill="x", pady=6)
        self.button(controls, "Use chat prompt", self.use_chat_prompt).pack(side="left", padx=3)
        self.button(controls, "Run Comparison (2 requests)", self.run_comparison).pack(side="left", padx=3)
        self.compare_cancel = ttk.Button(controls, text="Cancel both", command=self.cancel_comparison, state="disabled")
        self.compare_cancel.pack(side="left", padx=3)
        columns = ttk.Frame(self.comparison_tab)
        columns.pack(fill="both", expand=True)
        self.compare_profile_vars, self.compare_model_vars = [], []
        self.compare_profiles, self.compare_models, self.compare_outputs, self.compare_stats_vars = [], [], [], []
        for index, title in enumerate(("Model A", "Model B")):
            panel = ttk.LabelFrame(columns, text=title, padding=6)
            panel.grid(row=0, column=index, sticky="nsew", padx=4)
            columns.columnconfigure(index, weight=1)
            profile, model = tk.StringVar(self), tk.StringVar(self)
            self.compare_profile_vars.append(profile)
            self.compare_model_vars.append(model)
            ttk.Label(panel, text="Saved profile").pack(anchor="w")
            profile_box = ttk.Combobox(panel, textvariable=profile, state="readonly")
            profile_box.pack(fill="x")
            ttk.Label(panel, text="Model ID").pack(anchor="w", pady=(5, 0))
            model_box = ttk.Combobox(panel, textvariable=model)
            model_box.pack(fill="x")
            self.compare_profiles.append(profile_box)
            self.compare_models.append(model_box)
            profile_box.bind("<<ComboboxSelected>>", lambda event, i=index: self.compare_profile_changed(i))
            self.button(panel, "Refresh models", lambda i=index: self.fetch_compare_models(i)).pack(anchor="w", pady=5)
            stats = tk.StringVar(self, value="No comparison yet.")
            self.compare_stats_vars.append(stats)
            ttk.Label(panel, textvariable=stats, wraplength=365).pack(fill="x", pady=5)
            self.compare_outputs.append(self.text_area(panel, height=12, width=40, state="disabled"))
        columns.rowconfigure(0, weight=1)

    def compare_profile_changed(self, index):
        if self.busy:
            return
        name = self.compare_profile_vars[index].get()
        profile = self.client.store.list_profiles().get(name, {})
        self.compare_model_vars[index].set(profile.get("model", "") or (self.model.get() if name == self.profile.get() else ""))
        self.compare_models[index].configure(values=self.model_cache.get(name, []))

    def fetch_compare_models(self, index):
        name = self.compare_profile_vars[index].get()
        if not name:
            self.status.set("Select a saved comparison profile.")
            return
        def ready(models):
            ids = [model.id for model in models]
            self.model_cache[name] = ids
            self.compare_models[index].configure(values=ids)
            if not self.compare_model_vars[index].get() and ids:
                self.compare_model_vars[index].set(ids[0])
            self.status.set("Found %s models for comparison." % len(ids))
        self.job(lambda: self.client.list_models(name), ready)

    def use_chat_prompt(self):
        if not self.busy:
            self.compare_prompt.delete("1.0", "end")
            self.compare_prompt.insert("1.0", self.prompt.get("1.0", "end").strip())

    def write_comparison(self, index, text):
        widget = self.compare_outputs[index]
        widget.configure(state="normal")
        widget.insert("end", text)
        widget.see("end")
        widget.configure(state="disabled")

    def run_comparison(self):
        if self.busy:
            return
        try:
            prompt = self.compare_prompt.get("1.0", "end").strip()
            if not prompt:
                raise AIError("Enter a comparison prompt.", "configuration")
            options = self.request_options()
            profiles = self.client.store.list_profiles()
            targets = [(self.compare_profile_vars[i].get(), self.compare_model_vars[i].get().strip()) for i in (0, 1)]
            if any(profile not in profiles or not model for profile, model in targets):
                raise AIError("Select a saved profile and model for both sides.", "configuration")
        except AIError as exc:
            self.status.set(str(exc))
            return
        self.cancel.clear()
        self.comparison_remaining = {0, 1}
        self.set_busy(True)
        self.compare_cancel.configure(state="normal")
        self.status.set("Running two comparison requests...")
        self.log("Comparison started: two independent requests.")
        for index, (profile, model) in enumerate(targets):
            widget = self.compare_outputs[index]
            widget.configure(state="normal")
            widget.delete("1.0", "end")
            widget.configure(state="disabled")
            self.comparison_started[index] = time.monotonic()
            self.comparison_stats[index] = RequestStats(profile, model, profiles[profile]["provider"])
            self.compare_stats_vars[index].set(self.format_stats(self.comparison_stats[index]))
            def worker(i=index, name=profile, selected=model):
                # Separate sessions: never share an injected requests.Session across threads.
                client = AIClient(self.client.app_id, self.client.store, options.timeout)
                result = run_request(client, [{"role": "user", "content": prompt}], options, name, selected, self.cancel,
                                     on_text=lambda text: self.events.put(("compare_text", i, text)),
                                     on_stats=lambda stats: self.events.put(("compare_stats", i, stats)))
                self.events.put(("compare_result", i, result))
            threading.Thread(target=worker, daemon=True).start()

    def comparison_ready(self, index, result):
        self.comparison_remaining.discard(index)
        self.comparison_stats[index] = result.stats
        self.compare_stats_vars[index].set(self.format_stats(result.stats))
        if result.error:
            self.write_comparison(index, "\n[" + result.error + "]")
        self.log("Comparison %s: %s." % ("A" if index == 0 else "B", result.stats.status))
        if not self.comparison_remaining:
            self.compare_cancel.configure(state="disabled")
            self.set_busy(False)
            statuses = [self.comparison_stats[i].status for i in (0, 1)]
            self.status.set("Comparison finished — A: %s; B: %s." % tuple(statuses))

    def cancel_comparison(self):
        self.cancel.set()
        self.compare_cancel.configure(state="disabled")
        self.status.set("Cancelling both requests; waiting for network reads...")
        self.log("Comparison cancellation requested.")

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
                if kind == "stats":
                    self.active_stats = event[1]
                    self.stats_text.set(self.format_stats(event[1]))
                elif kind == "compare_text":
                    self.write_comparison(event[1], event[2])
                elif kind == "compare_stats":
                    self.comparison_stats[event[1]] = event[2]
                    self.compare_stats_vars[event[1]].set(self.format_stats(event[2]))
                elif kind == "compare_result":
                    self.comparison_ready(event[1], event[2])
                elif kind == "text":
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
        if getattr(self, "run_started", None) is not None and self.busy and not self.comparison_remaining:
            if self.active_stats and self.active_stats.status == "running":
                self.stats_text.set(self.format_stats(self.active_stats, time.monotonic() - self.run_started))
        for index in getattr(self, "comparison_remaining", set()):
            stats = self.comparison_stats[index]
            self.compare_stats_vars[index].set(self.format_stats(stats, time.monotonic() - self.comparison_started[index]))
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
