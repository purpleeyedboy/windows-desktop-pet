"""Application entry point with opt-in isolated startup diagnostics for CI."""
import os
from pathlib import Path
import traceback


if __name__ == "__main__":
    try:
        from desktop_pet.main import main
        raise SystemExit(main())
    except Exception:
        destination = os.environ.get("DESKTOP_PET_STARTUP_DIAGNOSTICS")
        if destination:
            diagnostic = Path(destination)
            diagnostic.parent.mkdir(parents=True, exist_ok=True)
            diagnostic.write_text(traceback.format_exc(), encoding="utf-8")
        raise
