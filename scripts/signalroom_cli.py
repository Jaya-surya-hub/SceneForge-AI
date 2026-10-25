#!/usr/bin/env python
"""Direct launcher for Signal Room Typer CLI."""

import os
import sys

# Ensure src is on python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from signalroom.cli.main import app

if __name__ == "__main__":
    app()
