#!/usr/bin/env python3
"""Claw — AI Coding Assistant. Run this script to start the interactive REPL."""
import sys
from pathlib import Path

# Ensure the project root is on the Python path
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.main import main

if __name__ == '__main__':
    raise SystemExit(main())
