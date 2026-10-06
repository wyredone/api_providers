"""Standalone manager using the same components as host applications."""
def main():
    import argparse
    parser = argparse.ArgumentParser(description="AI provider settings manager")
    parser.add_argument("--demo", action="store_true", help="Open the integration demo")
    parser.add_argument("--legacy", action="store_true", help="Open the archived v1 interface")
    args = parser.parse_args()
    import tkinter as tk
    root = tk.Tk()
    if args.legacy:
        from .legacy.gui import APIProviderManagerGUI
        APIProviderManagerGUI(root)
    elif args.demo:
        from .ui.demo import DemoApp
        root.title("API Providers integration demo")
        DemoApp(root).pack(fill="both", expand=True, padx=12, pady=12)
    else:
        from .client import AIClient
        from .ui import ProviderSettingsPanel
        root.title("API Provider Manager")
        ProviderSettingsPanel(root, AIClient("manager")).pack(fill="both", expand=True, padx=12, pady=12)
    root.mainloop()
