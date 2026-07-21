from pathlib import Path
import sys


def asset_path(*parts: str) -> Path:
    """Resolve bundled assets in source checkouts and PyInstaller builds."""
    bundle_root = getattr(sys, "_MEIPASS", None)
    root = Path(bundle_root) if bundle_root else Path(__file__).resolve().parents[2]
    return root.joinpath(*parts)
