"""Install the package, then run this file. No provider code belongs in the host."""
import tkinter as tk
from api_providers import AIClient
from api_providers.ui.demo import DemoApp

if __name__ == "__main__":
    root = tk.Tk()
    root.title("My app with shared AI settings")
    DemoApp(root, AIClient(app_id="my-app")).pack(fill="both", expand=True)
    root.mainloop()
