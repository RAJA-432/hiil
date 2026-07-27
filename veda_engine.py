"""
Thin launcher — re-exports the `mcp` FastMCP instance from the veda_engine package.

Allows:
  python veda_engine.py
  mcp dev veda_engine.py
"""

import os
import sys

_dir = os.path.dirname(os.path.abspath(__file__))
sys.path = [p for p in sys.path if os.path.abspath(p) != _dir]

from veda_engine.main import mcp

if __name__ == "__main__":
    mcp.run()
