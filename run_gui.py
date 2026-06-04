#!/usr/bin/env python3
"""Launch the video generator desktop GUI."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.gui import App

if __name__ == "__main__":
    app = App()
    app.mainloop()
