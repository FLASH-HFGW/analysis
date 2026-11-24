#!/usr/bin/env python3
"""Compatibility CLI entry point. See examples/tool/plot_saved_fft.py."""
from pathlib import Path
import runpy

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parent / "tool" / "plot_saved_fft.py"), run_name="__main__")
else:
    globals().update({k:v for k,v in runpy.run_path(str(Path(__file__).resolve().parent / "tool" / "plot_saved_fft.py"), run_name="__imported_tool__").items() if not k.startswith("__")})
