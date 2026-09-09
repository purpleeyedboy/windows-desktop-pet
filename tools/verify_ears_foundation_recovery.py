"""Focused shared-state recovery verification using only an isolated temp tree."""
from __future__ import annotations

from copy import deepcopy
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from desktop_pet.foundation.config import BuildInfo
from desktop_pet.foundation.persistence import AtomicJsonStore, TransactionJournal
from desktop_pet.foundation.services import DEFAULT_STATE, SharedState, create_application_services, valid_v21_state
from desktop_pet.window import PetWindow


def main() -> int:
    # The old six-frame actions replace logical endpoints with the padded
    # 640px center. Their physical 512px manifest anchor must not shift it.
    window = object.__new__(PetWindow)
    center = Image.new("RGBA", (640, 768), (50, 60, 70, 255))
    physical = Image.new("RGBA", (512, 768), (50, 60, 70, 255))
    window._closed = False
    window._rendering_available = True
    window._legacy_fallback = False
    window._current_image = physical
    window._presentation_snapshot = None
    window.eye_session = SimpleNamespace(logical_frame=lambda _action, index: center if index in (0, 5) else physical)
    window.animation = SimpleNamespace(sequence=lambda _action: SimpleNamespace(anchor=(256, 768)))
    window._anchor = lambda: (400, 800)
    anchors = []
    window._apply_image = lambda _image, _anchor, **kwargs: anchors.append(kwargs["source_anchor"])
    for index in (0, 1, 5):
        window._show_animation_frame("jump", index)
    assert anchors == [(320, 768), (256, 768), (320, 768)]
    window.frames = {"feature-test": (center,)}
    window._show_animation_frame("feature-test", 0)
    assert anchors[-1] == (256, 768)

    with tempfile.TemporaryDirectory(prefix="ears-foundation-") as directory:
        root = Path(directory)
        legacy = root / "legacy"
        old_store = AtomicJsonStore(legacy / "state.json", schema="desktop-pet-v2.1", version=1)
        original = deepcopy(DEFAULT_STATE)
        original["hunger_anchor_utc_seconds"] = 123
        old_store.save(original)
        old_bytes = old_store.path.read_bytes()
        services = create_application_services(BuildInfo.load_embedded(), root / "current", legacy_root=legacy)
        assert services.load_state() == original
        assert old_store.path.read_bytes() == old_bytes
        assert services.paths.state_backup.name == "state.backup.json"
        handler = next(item for item in services.logger.handlers if isinstance(item, RotatingFileHandler))
        services.logger.warning("synthetic test path C:/synthetic-only/example.txt")
        handler.flush()
        assert "C:/synthetic-only" not in services.log_path.read_text(encoding="utf-8")
        handler.doRollover()
        assert services.log_path.with_name("desktop-pet.log.1").is_file()

        # Window shutdown must preserve newer state, rather than write the
        # startup snapshot over updates received during the session.
        services.update_state(lambda state: state.update(hunger_anchor_utc_seconds=456, recent_operation_ids=["synthetic-operation"]))
        window = object.__new__(PetWindow)
        window.services = services
        window._persisted_state = original
        window._ear_context = None
        window._closed = False
        window._runtime_timer = None
        window.eye_session = None
        window.animation = SimpleNamespace(stop=lambda: None)
        window.bubble = SimpleNamespace(destroy=lambda: None)
        window.root = SimpleNamespace(destroy=lambda: None)
        window._window_rect = SimpleNamespace(x=31, y=42)
        window.display_height = 280
        window.close()
        saved = services.store.load(default=DEFAULT_STATE)
        assert saved["hunger_anchor_utc_seconds"] == 456
        assert saved["recent_operation_ids"] == ["synthetic-operation"]
        assert saved["window"] == {"x": 31, "y": 42, "height": 280}

        store = AtomicJsonStore(root / "backup-case/state.json", schema="desktop-pet-v2.1", version=1,
                                validator=valid_v21_state, backup_path=root / "backup-case/state.backup.json")
        store.save(original)
        store.save(saved)
        store.path.write_text("synthetic corrupt primary", encoding="utf-8")
        assert store.load(default=DEFAULT_STATE) == original and store.last_source == "backup"
        assert any(path.read_bytes() == b"synthetic corrupt primary" for path in store.recovery_dir.iterdir())

        journal = TransactionJournal(root / "journal-case/feed-journal.jsonl")
        journal.append({"operation_id": "synthetic-pending", "phase": "processing",
                        "details": {"path": "C:/synthetic-only/example.txt"}}, durable=True)
        state = SharedState(AtomicJsonStore(root / "journal-case/state.json", schema="desktop-pet-v2.1", version=1,
                                          validator=valid_v21_state), journal)
        pending = state.load()["pending_transaction"]
        assert pending["operation_id"] == "synthetic-pending"
        assert "synthetic-only" not in journal.path.read_text(encoding="utf-8")
    print("Ear shared migration, backup, journal, log and shutdown recovery verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
