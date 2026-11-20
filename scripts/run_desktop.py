#!/usr/bin/env python3
"""Run the BASIRA AI desktop application."""
import sys
from pathlib import Path

# Allow running from any working directory: ensure the project root
# (parent of scripts/) is importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from basira.desktop.app import main

if __name__ == "__main__":
    raise SystemExit(main())
