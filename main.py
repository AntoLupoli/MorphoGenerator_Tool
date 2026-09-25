"""
MorphoGenerator Tool — Entry point.

Launch with:
    python main.py
"""

import sys
import os

# Ensure the project root is on the path so `app` is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.app import MorphoApp


def main():
    app = MorphoApp()
    app.mainloop()

if __name__ == "__main__":
    main()

