#!/usr/bin/env python3
"""Compatibility CLI entry point. See examples/tool/fft_viewer.py."""
from pathlib import Path
import runpy

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parent / "tool" / "fft_viewer.py"), run_name="__main__")
