#!/usr/bin/env python3
"""Start Telegram bot for video generation pipeline."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.telegram_bot import main

if __name__ == "__main__":
    main()
