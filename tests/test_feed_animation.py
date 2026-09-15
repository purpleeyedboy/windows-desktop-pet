import hashlib
import json
from pathlib import Path

from PIL import Image

from desktop_pet.feed_animation import FEED_POSE_SEQUENCE, FeedAnimationPlayer
from tools.build_feed_frames import build_feed_assets


class Scheduler:
    def __init__(self):
        self.pending = []
        self.cancelled = []

    def __call__(self, delay, callback):
        token = object()
        self.pending.append((token, delay, callback))
        return token

    def cancel(self, token):
        self.cancelled.append(token)

    def run_all(self):
        while self.pending:
            token, _, callback = self.pending.pop(0)
            if token not in self.cancelled:
                callback()


def test_requested_sequence_uses_all_art_and_has_three_large_chews_then_lick():
    assert FEED_POSE_SEQUENCE == (0, 1, 2, 3, 2, 1, 2, 4, 5)
    assert set(FEED_POSE_SEQUENCE) == set(range(6))


def test_player_displays_real_frames_and_restores_latest_pose():
    scheduler = Scheduler()
    frames = tuple(object() for _ in range(6))
    original = object()
    latest = [original]
    displayed = []
    player = FeedAnimationPlayer(
        frames, scheduler, scheduler.cancel, displayed.append, lambda: latest[0]
    )

    assert player.play() is True
    latest[0] = "newest-pose"
    scheduler.run_all()

    assert displayed[:-1] == [frames[index] for index in FEED_POSE_SEQUENCE]
    assert displayed[-1] == "newest-pose"
    assert player.busy is False


def test_player_rejects_overlap_and_interrupt_restores_latest_pose():
    scheduler = Scheduler()
    displayed = []
    latest = ["start"]
    player = FeedAnimationPlayer(
        tuple(object() for _ in range(6)),
        scheduler,
        scheduler.cancel,
        displayed.append,
        lambda: latest[0],
    )
    assert player.play() is True
    assert player.play() is False
    latest[0] = "interrupted-latest"
    assert player.interrupt() is True
    assert displayed[-1] == "interrupted-latest"
    scheduler.run_all()
    assert displayed[-1] == "interrupted-latest"


def test_legacy_feed_frames_match_approved_canvas_and_rgba_contract(tmp_path):
    # This checks packaging integrity, not acceptance of whole-cat animation art.
    manifest_path = Path("assets/feed/v1/manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["canonical"]["canvas"] == [640, 768]
    root = tmp_path / "feed"
    built = build_feed_assets(manifest_path, root)
    assert len(built) == 6
    frames = []
    for path in sorted(root.glob("*.png")):
        with Image.open(path) as opened:
            frames.append(opened.copy())
    assert len(frames) == 6
    assert all(frame.mode == "RGBA" and frame.size == (640, 768) for frame in frames)
    assert hashlib.sha256(frames[0].tobytes()).hexdigest() == manifest["canonical"]["neutral_rgba_sha256"]
    assert all(frame.getchannel("A").getextrema() == (0, 255) for frame in frames)
    # Color richness alone does not prove full-cat redraw or visual consistency.
    assert all(len(frame.getcolors(maxcolors=1_000_000) or ()) > 10_000 for frame in frames)
