"""Windows desktop pet package."""

from pathlib import Path
import os
import sys


def configure_tk_environment() -> None:
    """Restore Tcl/Tk paths lost by some Windows virtual environments."""
    if getattr(sys, "frozen", False):
        return
    tcl_root = Path(sys.base_prefix) / "tcl"
    candidates = {
        "TCL_LIBRARY": (tcl_root / "tcl8.6", "init.tcl"),
        "TK_LIBRARY": (tcl_root / "tk8.6", "tk.tcl"),
    }
    for variable, (path, marker) in candidates.items():
        if variable not in os.environ and (path / marker).is_file():
            os.environ[variable] = str(path)


configure_tk_environment()
