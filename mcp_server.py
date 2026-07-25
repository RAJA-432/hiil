"""
Thin launcher — re-exports the `mcp` FastMCP instance from the mcp_server package.

Allows:
  python mcp_server.py
  mcp dev mcp_server.py
"""

import os
import sys

_dir = os.path.dirname(os.path.abspath(__file__))
sys.path = [p for p in sys.path if os.path.abspath(p) != _dir]

from mcp_server.main import mcp

if __name__ == "__main__":
    mcp.run()
