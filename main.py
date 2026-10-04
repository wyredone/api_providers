import tkinter as tk
from gui import APIProviderManagerGUI


if __name__ == "__main__":
    root = tk.Tk()
    app = APIProviderManagerGUI(root)
    root.mainloop()
